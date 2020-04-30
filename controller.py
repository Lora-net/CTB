#file      controller.py

#brief      general test control code

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
# -*- coding: utf-8 -*-
"""
Created on Mon Oct 15 17:24:14 2018

@author: flu
"""
import socket
import json
import threading
import sqlite3
import time
import ext_sequence
import logging
from web_result import generate_cache

from lib_base import DB_FILE_CONTROLLER, addr_tc, log_time, reliable_run, deduplication_threshold
from lib_db import create_db_tables_tc, recover_db_tc


def sequence(pkt, conn):
    if "error" in pkt["json"]:
        return None

    dev_eui = pkt["json"]["DevEui"]

    conn.execute(
        "UPDATE schedule SET FinishTime=(?) WHERE StartTime is not null and \
        FinishTime is null and Parameter <= CurrentPara and \
        Criteria is 'count' and DevEui=(?)",
        (time.time(), dev_eui))
    conn.commit()

    conn.execute(
        "UPDATE schedule SET FinishTime=(?) WHERE StartTime is not null and \
        FinishTime is null and (StartTime + Parameter) <= (?) and \
        Criteria is 'time' and DevEui=(?)",
        (time.time(), time.time(), dev_eui))
    conn.commit()

    for response in conn.execute("SELECT rowid,* FROM schedule WHERE FinishTime > (?)", (time.time() - 5, )).fetchall():
        response = dict(response)
        threading.Thread(target=generate_cache, args = (response, )).start()

    response = conn.execute(
        'SELECT rowid, * from schedule WHERE devEUI=(?) AND FinishTime IS Null \
        ORDER BY AddTime LIMIT 1', (dev_eui,)).fetchone()
    conn.commit()
    
    # for debug purposes, due to a bug in the fw used to develop test bed
    if pkt["json"]['MType'] in ["010", "100"]:
        if pkt["json"]["FOpts"] == "03050307":
            pkt["json"]["FOpts"] = "03070307"
            pkt["size"] = -1
            logging.debug("NA mote debug modified")

    if not response:
        logging.info("No test queued")
        return pkt
    else:
        pkt["test"] = dict(response)
        if pkt["test"]["Config"]:
            pkt["test"]["Config"] = json.loads(pkt["test"]["Config"])

        logging.info("Sequence information")
        for line in json.dumps(pkt["test"], indent = 4).split("\n"):
            logging.info(line)

        if "FPending" in pkt["test"]["Config"] and pkt["test"]["Config"]["FPending"]:
            if pkt["json"]['MType'] in ["010", "100"]:
                pkt["json"]['MType'] = "100"
                pkt["size"] = -1
                
            if pkt["json"]['MType'] in ["011", "101"]:
                pkt["json"]['FPending'] = "1"
                pkt["size"] = -1
        
        if not response['StartTime']:
            if pkt["json"]['MType'] in ["010", "100", "000", "001"]:
                conn.execute("UPDATE schedule SET StartTime=(?) WHERE rowid=(?)", (time.time(), pkt["test"]['rowid']))
                conn.commit()
            else:
                return pkt
        
        # deduplication
        if pkt["json"]['MType'] in ["010", "100", "000"] and response['UpdateTime']:
            if time.time() - response['UpdateTime'] < deduplication_threshold:
                logging.debug("dedup worked")
                return None

        if pkt["json"]['MType'] in ["010", "100"] and response['UpdateTime'] and "Ignore_interval" in pkt["test"]["Config"]:
            if time.time() - response['UpdateTime'] < float(pkt["test"]["Config"]["Ignore_interval"]):
                return None
        
        if pkt["json"]['MType'] in ["010", "100", "000"]:
            conn.execute("UPDATE schedule SET UpdateTime=(?) WHERE rowid=(?)", (time.time(), pkt["test"]['rowid']))
            conn.commit()

        if pkt["json"]['MType'] in ["011", "101"] and "FPort" in pkt["test"]["Config"] and "FRMPayload" in pkt["test"]["Config"]:
            pkt["json"]["FPort"] = pkt["test"]["Config"]["FPort"]
            pkt["json"]["FRMPayload"] = pkt["test"]["Config"]["FRMPayload"]

        try:
            return eval("ext_sequence.sequence_" + response["Cat"] + "_" + response["SubCat"] + "(pkt, conn)")
        except AttributeError:
            logging.info("sequence_" + response["Cat"] + "_" + response["SubCat"], "not defined")
            return pkt

    return pkt


def run_controller():
    create_db_tables_tc()
    recover_db_tc()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(1)
    sock.bind(("", addr_tc[1]))
    
    logging.info("controller successful start")
    
    addr_proxy = ()

    conn = sqlite3.connect(DB_FILE_CONTROLLER, timeout=60)
    conn.row_factory = sqlite3.Row

    while True:
        try:
            byte_data, addr = sock.recvfrom(10240)
        except socket.timeout:
            continue
        addr_proxy = addr

        json_data = json.loads(byte_data[4:].decode())

        if "rxpk" in json_data:
            pkt = json_data["rxpk"]
            pkt = sequence(pkt, conn)

            byte_data = byte_data[:4] + json.dumps({"rxpk": pkt}).encode()
            sock.sendto(byte_data, addr_proxy)
            continue
        if "txpk" in json_data:
            pkt = json_data["txpk"]
            pkt = sequence(pkt, conn)
            
            byte_data = byte_data[:4] + json.dumps({"txpk": pkt}).encode()
            sock.sendto(byte_data, addr_proxy)
            continue


if __name__ == "__main__":
    reliable_run(run_controller, loop = True)

