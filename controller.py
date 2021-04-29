#Revised BSD License

#Copyright Semtech Corporation 2021. All rights reserved.

#Redistribution and use in source and binary forms, with or without
#modification, are permitted provided that the following conditions are met:
#Redistributions of source code must retain the above copyright
#notice, this list of conditions and the following disclaimer.
#Redistributions in binary form must reproduce the above copyright
#notice, this list of conditions and the following disclaimer in the
#documentation and/or other materials provided with the distribution.
#Neither the name of the Semtech corporation nor the
#names of its contributors may be used to endorse or promote products
#derived from this software without specific prior written permission.


#THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
#AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
#IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
#ARE DISCLAIMED. IN NO EVENT SHALL SEMTECH CORPORATION. BE LIABLE FOR ANY DIRECT,
#INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
#(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
#LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
#ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
#(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
#SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import socket
import json
import threading
import sqlite3
import time
import logging
from web_result import generate_cache
import os, sys
import pytest
import multiprocessing
from importlib import import_module

from lib_base import FILE_PC_CONTEXT, addr_pc, log_time, reliable_run, config_logger,\
    config_console, PROC_MSG, DB_FILE_BACKUP, POWER_TB_BACKUP_INTERVAL
from lib_db import create_db_tables_tc, backup_db_pm

sys.path.append("pytest_dir")

PC_STATE = {
    'IDLE': 0,
    'WAIT_RSP': 1,
    'RUNNING': 2
}


def get_all_devices():
    conn = sqlite3.connect(DB_FILE_BACKUP, timeout=60)
    conn.row_factory = sqlite3.Row
    response = conn.execute("SELECT * from device").fetchall()
    conn.close()
    devices = []
    for device in response:
        devices.append(dict(device))
    return devices


def is_deveui_under_test(deveui, devices):
    for device in devices:
        if deveui == device['DevEui']:
            return True
    return False


def process_pc_msg(byte_data, addr, pc):
    logging.debug("received data are: {}".format(byte_data))
    cmd = byte_data[0]
    if cmd == PROC_MSG["WB_POST_SEQUENCE"]:
        try:
            schedules = json.loads(byte_data[1:].decode())
            add_time = time.time()
            devices = get_all_devices()
            error_msg = ""

            for schedule in schedules:
                logging.debug("schedule: {}".format(schedule))

                for key in ['DevEui', 'Cat', 'SubCat', 'Criteria', 'Parameter']:
                    if key not in schedule:
                        error_msg += ", {} is not in the sequence {}".format(key, schedule)
                if error_msg != "":
                    continue

                if not is_deveui_under_test(schedule['DevEui'].lower(), devices):
                    error_msg += ", DevEui {} is not in the device list".format(schedule['DevEui'])
                    continue

                schedule["AddTime"] = add_time
                if "Config" not in schedule:
                    schedule["Config"] = {}
                    schedule["Config"] = json.dumps(schedule["Config"])
                pc.test_list.append(schedule)
            pc.dump()
            if error_msg != "":
                error_msg = "Part of the sequence error" + error_msg
                pc.sock.sendto(error_msg.encode("utf-8"), addr)
            else:
                pc.sock.sendto("ok".encode("utf-8"), addr)
        except:
            pc.sock.sendto("error".encode("utf-8"), addr)
    elif cmd == PROC_MSG["WB_GET_SEQUENCE"]:
        logging.debug("sending test_list")
        pc.sock.sendto(json.dumps(pc.test_list).encode(), addr)
    elif cmd == PROC_MSG["WB_DEL_SEQUENCE"]:
        tmp = byte_data[1:].decode()
        logging.debug("delete config, tmp is {}".format(tmp))
        if tmp == "all":
            if len(pc.test_list) > 0:
                pc.test_list = []
                if pc.state != PC_STATE['IDLE']:
                    if pc.process:
                        pc.process.terminate()
                        logging.debug("sending termination")
                        pc.process = None
                    pc.set_state_wait()
                pc.cancel_test_timeout_timer()
                pc.dump()
            pc.sock.sendto("ok".encode("utf-8"), addr)
        else:
            try:
                rows_js = json.loads(tmp)
                rows = [row['rowid'] for row in rows_js]
                rows.sort(reverse=True)
                for row in rows:
                    if row < len(pc.test_list):
                        pc.test_list.pop(row)
                if 0 in rows and pc.state != PC_STATE['IDLE']:
                    if pc.process:
                        pc.process.terminate()
                        pc.process = None
                    pc.cancel_test_timeout_timer()
                    pc.set_state_wait()
                pc.dump()
                pc.sock.sendto("ok".encode("utf-8"), addr)
            except:
                pc.sock.sendto("error".encode("utf-8"), addr)
    elif cmd == PROC_MSG["WB_QUERY_TEST_STATE"]:
        if not pc.test_list:
            pc.sock.sendto("No test running".encode("utf-8"), addr)
        else:
            pc.sock.sendto("Test is running".encode("utf-8"), addr)
    elif cmd == PROC_MSG["TC_SETUP_TEST"]:
        schedule = json.loads(byte_data[1:].decode())
        if pc.state == PC_STATE['WAIT_RSP']:
            pc.test_list[0]["StartTime"] = schedule["StartTime"]
        else:
            pc.start_logger(schedule['Cat']+"_"+schedule['SubCat'])
            logging.debug("Test started from pytest {}".format(schedule))
            pc.test_list.insert(0, schedule)
        pc.start_backup_pm_timer(schedule['TestInstID'])
        pc.state = PC_STATE['RUNNING']
        pc.dump()
        logging.debug("[controller] setup test received, schedule is {}".format(schedule))
    elif cmd == PROC_MSG["TC_TEARDOWN_TEST"]:
        logging.debug("[controller] teardown test received")
        schedule = json.loads(byte_data[1:].decode())
        pc.cancel_test_timeout_timer()
        if pc.state == PC_STATE['RUNNING']:
            pc.state = PC_STATE['IDLE']
            pc.test_list.pop(0)
            pc.dump()
            pc.process = None
        elif pc.state == PC_STATE['WAIT_RSP']:
            pc.state = PC_STATE['IDLE']
        pc.backup_timer.cancel()
        pc.backup_timer = None
        backup_db_pm(schedule['TestInstID'])
        pc.cache_thread = threading.Thread(target=generate_cache, args = (schedule, ))
        pc.cache_thread.start()
        if not pc.test_list:
            pc.start_logger() # switch to default log


class ControllerContext():
    def __init__(self, sock, file):
        self.sock = sock
        self.file = file
        self.process = None
        self.test_list = []
        self.state = PC_STATE['IDLE']
        self.cache_thread = None
        self.timer = None
        self.backup_timer = None

    def set_state_wait(self):
        self.state = PC_STATE['WAIT_RSP']
        self.wait_cnt = 0

    def load(self):
        if os.path.exists(self.file):
            with open(self.file) as js:
                data = json.load(js)
                self.test_list = data["test_list"]
                self.state = data["state"]
        else:
            pass # add loading from database

    def dump(self):
        with open(self.file, 'w') as js:
            json.dump({"test_list": self.test_list, "state": self.state},
                      js)

    def start_logger(self, test_name=None):
        logger = logging.getLogger()
        if isinstance(logger.handlers[-1], logging.handlers.RotatingFileHandler):
            logger.removeHandler(logger.handlers[-1])
            if test_name:
                timestamp = time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime())
                file = os.path.join("log", "test_{}_{}.log".format(test_name, timestamp))
                config_logger(file)
            else:
                config_logger()

    def start_backup_pm_timer(self, test_inst_id):
        if self.backup_timer:
            self.backup_timer.cancel()
        self.backup_timer = threading.Timer(POWER_TB_BACKUP_INTERVAL,
                                            self.backup_handler, args=(test_inst_id,))
        self.backup_timer.start()

    def start_test_timeout_timer(self, test):
        test_name = test['Cat']+"_"+test['SubCat']
        if "timeout" in test and "whole_test" in test['timeout']:
            timeout = test['timeout']['whole_test']
        else:
            try:
                test = import_module("test_{}".format(test['Cat']))
                timeout = eval("test.test_"+test_name+"_timeout")
                logging.debug("test timeout is %d" % timeout)
            except:
                logging.info("No whole test timeout is configured")
                return
        logging.debug("test level time out is {}".format(timeout))
        self.timer = threading.Timer(timeout, self.timeout_handler)
        self.timer.start()

    def cancel_test_timeout_timer(self):
        if self.timer:
            self.timer.cancel()
            self.timer = None

    def timeout_handler(self):
        logging.warning("test timeout is triggered")
        if self.process:
            logging.debug("terminating process")
            self.process.terminate()
            self.process = None
            self.test_list.pop(0)
            self.set_state_wait()
            self.dump()
            self.timer = None

    def backup_handler(self, test_inst_id):
        self.backup_timer = threading.Timer(POWER_TB_BACKUP_INTERVAL,
                                            self.backup_handler, args=(test_inst_id,))
        self.backup_timer.start()
        backup_db_pm(test_inst_id)


def run_controller():
    create_db_tables_tc()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(1)
    sock.bind(("", addr_pc[1]))

    pc = ControllerContext(sock, FILE_PC_CONTEXT)
    pc.load()
    logging.info("controller successfully started.")

    while True:
        try:
            byte_data, addr = sock.recvfrom(10240)
            process_pc_msg(byte_data, addr, pc)
        except socket.timeout:
            pass

        if pc.state == PC_STATE['IDLE'] and len(pc.test_list) > 0:
            if pc.cache_thread and pc.cache_thread.is_alive():
                logging.warning("cache_thread is still alive")
                continue

            test = pc.test_list[0]
            test_cmd = []
            test_cmd.append("-s")
            if "pcap" in test and test['pcap'] == 1:
                test_cmd.append("--pcap")
            if "verify_only" in test and test['verify_only'] == 1:
                test_cmd.append("--verify_only")
                if "rowid" in test:
                    test_cmd.append("--rowid={}".format(test["rowid"]))
            test_cmd.append("--deveui={}".format(test["DevEui"]))
            test_cmd.append("--addtime={}".format(test["AddTime"]))
            test_cmd.append("--criteria={}".format(test["Criteria"]))
            test_cmd.append("--parameter={}".format(test["Parameter"]))
            test_cmd.append("--config={}".format(test["Config"]))
            test_cmd.append("test_{}.py::test_{}_{}".format(test["Cat"], test["Cat"], test["SubCat"]))
            pc.start_logger(test["Cat"]+"_"+test["SubCat"])

            logging.info("Pytest controller starts test: {}".format(test_cmd))
            os.chdir("pytest_dir")
            pc.process = multiprocessing.Process(target=pytest.main, args=(test_cmd,))
            pc.process.start()
            os.chdir("..")

            time.sleep(2)
            if not pc.process.is_alive():
                logging.error("Cannot start test_{}_{} properly!".format(test["Cat"], test["SubCat"]))
                pc.test_list.pop(0)
            else:
                logging.debug("test started properly, process is {}".format(pc.process.pid))
                pc.set_state_wait()
                pc.start_test_timeout_timer(test)
                pc.dump()
        elif pc.state == PC_STATE['WAIT_RSP']:
            pc.wait_cnt += 1
            if pc.wait_cnt > 10:
                if pc.process:
                    pc.process.terminate()
                    pc.process = None
                    pc.test_list.pop(0)
                    pc.wait_cnt = 0
                else:
                    pc.state = PC_STATE['IDLE']
                    pc.dump()
                pc.cancel_test_timeout_timer()


if __name__ == "__main__":
    config_console()
    if os.path.exists(FILE_PC_CONTEXT):
        os.remove(FILE_PC_CONTEXT)
    reliable_run(run_controller, loop = True)
