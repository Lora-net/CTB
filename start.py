#file      start.py

#brief      small code to initiate test bench and ads driver

#Revised BSD License

#Copyright Semtech Corporation 2020. All rights reserved.

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

import threading
import time
import os
import lib_db
import logging
from logging.handlers import RotatingFileHandler


from proxy import run_proxy
from controller import run_controller
from web_main import run_web
from lib_base import POWER_FOLDER, DB_FOLDER, CACHE_FOLDER, DB_BACKUP_INTERVAL, reliable_run, use_internal_gateway, report_ip


def run_backup():
    lib_db.backup_db_pm()
    lib_db.backup_db_proxy()
    lib_db.backup_db_tc()


def restart_dead_thread(t):
    label = {0: "ADC driver     ", 
             1: "web host       ", 
             2: "test controller", 
             3: "proxy          "}
    
    for _ in range(1, 4):
        alive = t[_].is_alive()
        logging.debug(label[_] + " %d" % alive)
        if not alive:
            t[_].run()
            logging.error(label[_] + " restarted")

            with open("error.log", "a") as f:
                f.write(_ + " restarted\n")


def config_logger():
    if not os.path.exists("log"):
        os.mkdir("log")

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    fh = RotatingFileHandler(os.path.join("log", "ctb.log"), maxBytes=100000, backupCount=128)
    fh.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    logger.addHandler(fh)


if __name__== "__main__":
    config_logger()

    report_ip()

    for folder in [POWER_FOLDER, DB_FOLDER, CACHE_FOLDER]:
        if not os.path.exists(folder):
            os.mkdir(folder)

    lib_db.create_db_tables_proxy()
    lib_db.create_db_tables_tc()
    lib_db.create_db_tables_pm()

    t = []
    t.append(threading.Thread(target=os.system, args=("cd ads1256 && sudo ./ads1256_driver",)))
    t.append(threading.Thread(target=reliable_run, args=(run_web, True)))
    t.append(threading.Thread(target=reliable_run, args=(run_controller, True)))
    t.append(threading.Thread(target=reliable_run, args=(run_proxy, True)))

    if use_internal_gateway:
        t.append(threading.Thread(target=os.system, args=("cd /home/pi/lora-net/picoGW_packet_forwarder/lora_pkt_fwd/ "
                                                          "&& ./lora_pkt_fwd",)))

    time.sleep(10)

    for th in t:
        th.start()
        time.sleep(0.1)

    time.sleep(5)
    
    while True:
        reliable_run(run_backup, loop = False)
        
        for _ in range(int(DB_BACKUP_INTERVAL/10)):
            report_ip()
            restart_dead_thread(t)
            time.sleep(10)