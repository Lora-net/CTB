#file      start.py

#brief      small code to initiate test bench and ads driver

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

import threading, subprocess
import time
import os, sys
import lib_db
import logging


from proxy import run_proxy
from controller import run_controller
from web_main import run_web
from lib_base import POWER_FOLDER, DB_FOLDER, CACHE_FOLDER, PCAP_FOLDER, DB_BACKUP_INTERVAL,\
    FILE_PC_CONTEXT, reliable_run, use_internal_gateway, report_ip, config_console, config_logger,\
    config, gw_mac, NUM_LOG_FILES

import json

LOG_DIR = os.path.join(os.getcwd(), "log")

def run_backup():
    lib_db.backup_db_proxy()
    lib_db.backup_db_tc()


def restart_dead_thread(t):
    label = {0: "web host       ",
             1: "test controller",
             2: "proxy          "}
    
    for _, thread in enumerate(t):
        alive = thread.is_alive()
        try:
            thread_label = label[_]
        except KeyError:
            thread_label = "???            "
        logging.log(logging.NOTSET, thread_label + " %d" % alive)
        if not alive:
            thread.run()
            logging.error(thread_label + " restarted") # should this be checked again?

            with open("error.log", "a") as f:
                f.write(_ + " restarted\n") # uses a counter (_), maybe replace with thread_label

# Limit files in log directory
def dir_file_limiter(log_path, max_files):
    logging.debug("Running file limiter on " + log_path)

    # sort list of files. move to log directory to make easier
    cur_dir = os.getcwd()
    os.chdir(log_path)
    files_sorted = sorted(os.listdir(log_path), key = os.path.getmtime)
    
    # remove oldest files to meet criteria
    for i in range(0, len(files_sorted) - max_files):
        logging.debug("Removing file " + files_sorted[i])
        os.remove(files_sorted[i])
    
    os.chdir(cur_dir)

if __name__== "__main__":
    config_console()
    config_logger()

    report_ip()

    if use_internal_gateway:
        result = subprocess.run(['/home/pi/lora-net/picoGW_hal/util_chip_id/util_chip_id',
                                 '-d', '/dev/ttyACM0'], stdout=subprocess.PIPE)
        config["gateway_id"] = result.stdout.decode('utf-8').strip()
        if "ERROR" in config["gateway_id"]:
            logging.error("getting gw_mac error, %s" % config["gateway_id"])
            sys.exit(1)
        else:
            logging.info("gateway id is " + config["gateway_id"])
            gw_mac = bytes.fromhex(config["gateway_id"])

    for folder in [POWER_FOLDER, DB_FOLDER, CACHE_FOLDER, PCAP_FOLDER]:
        if not os.path.exists(folder):
            os.mkdir(folder)
    if os.path.exists(FILE_PC_CONTEXT):
        os.remove(FILE_PC_CONTEXT)

    lib_db.create_db_tables_backup()
    lib_db.create_db_tables_proxy()
    lib_db.create_db_tables_tc()

    t = []
    t.append(threading.Thread(target=reliable_run, args=(run_web, True)))
    t.append(threading.Thread(target=reliable_run, args=(run_controller, True)))
    t.append(threading.Thread(target=reliable_run, args=(run_proxy, True)))

    for th in t:
        th.start()
        time.sleep(0.1)

    time.sleep(5)

    while True:
        reliable_run(run_backup, loop = False)
        dir_file_limiter(LOG_DIR, NUM_LOG_FILES)

        for _ in range(int(DB_BACKUP_INTERVAL/10)):
            report_ip()
            restart_dead_thread(t)
            time.sleep(10)
