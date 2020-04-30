#file      proxy.py

#brief      set of functions to process packets between NS, tst controller and gateway

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
import time
import sqlite3
import random
import logging

import lib_packet
from lib_base import addr_ns, addr_tc, gw_mac, DB_FILE_PROXY, addr_pf, reliable_run, deduplication_threshold
from lib_packet import get_toa
from lib_db import recover_db_proxy, create_db_tables_proxy

buffer = {}

def run_proxy():
    create_db_tables_proxy()
    recover_db_proxy()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(deduplication_threshold/10)

    sock.bind(("", addr_pf[1]))

    addr_push = ()
    addr_pull = ()

    gw_mac_tmp = ''

    conn = sqlite3.connect(DB_FILE_PROXY, timeout=60)
    conn.row_factory = sqlite3.Row

    t = 0

    while True:

        to_be_removed = []
        for pl in buffer:
            pkt = buffer[pl]["pkt"]
            if time.time() - buffer[pl]["time"] > deduplication_threshold:
                pkt["json"] = lib_packet.decode_uplink(pkt, conn)

                logging.info("Received from GW")
                for line in json.dumps(pkt, indent=4, sort_keys=True).split("\n"):
                    logging.info(line)

                byte_data = bytes([2, random.randint(0, 255), random.randint(0, 255), 6]) + \
                            json.dumps({"rxpk": pkt}).encode()
                sock.sendto(byte_data, addr_tc)                

                conn.execute("INSERT INTO packet (tmst, chan, rfch, freq, stat, modu, datr, \
                             codr, lsnr, rssi, size, data, time, direction, json, toa) \
                             VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                             (pkt['tmst'], pkt['chan'], pkt['rfch'], pkt['freq'], 0, pkt['modu'], pkt['datr'],
                              pkt['codr'], pkt['lsnr'], pkt['rssi'], pkt['size'], pkt['data'], time.time(), 'up',
                              json.dumps(pkt["json"]), get_toa(pkt['size'], pkt['datr'])))

                token = list(byte_data[1:3])
                conn.execute("INSERT INTO delay (token, time_gen, dst) VALUES (?, ?, ?)",
                             ("%02x%02x" % (token[0], token[1]), time.time(), "tc"))
                conn.commit()

                to_be_removed.append(pl)

        for pl in to_be_removed:
            del buffer[pl]

        try:
            byte_data, addr = sock.recvfrom(10240)
        except socket.timeout:
            continue
        except ConnectionResetError:
            logging.error("ConnectionResetError, check test controller")
            continue
        
        if list(byte_data)[3] in [6]:
            logging.debug(str(list(byte_data)[3]) + " controller -> proxy")
        if list(byte_data)[3] in [0, 2, 5]:
            logging.debug(str(list(byte_data)[3]) + " Packetforwarder -> proxy")
        if list(byte_data)[3] in [1, 3, 4]:
            logging.debug(str(list(byte_data)[3]) + " NS -> proxy")
        
        if list(byte_data)[3] == 0:  # PUSH_DATA from the gateway, uplink packets
            original_token = byte_data[1:3]

            addr_push = addr
            gw_mac_tmp = byte_data[4:12]

            json_data = json.loads(byte_data[12:].decode())

            if 'rxpk' in json_data:
                for pkt in json_data['rxpk']:
                    if pkt["data"] not in buffer:
                        buffer[pkt["data"]] = {"pkt": pkt, "time": time.time()}
                    else:
                        logging.info("duplicate packet received. ")
                        if int(pkt["rssi"]) > int(buffer[pkt["data"]]["pkt"]["rssi"]):
                            buffer[pkt["data"]]["pkt"] = pkt
            else:
                byte_data = byte_data[0:4] + gw_mac + byte_data[12:]
                sock.sendto(byte_data, addr_ns)

                token = list(original_token)
                conn.execute("INSERT INTO delay (token, time_gen, dst) VALUES (?, ?, ?)",
                             ("%02x%02x" % (token[0], token[1]), time.time(), "ns"))
                conn.commit()

            byte_data = bytes([2]) + original_token + bytes([1])
            sock.sendto(byte_data, addr_push)

            continue

        if list(byte_data)[3] == 1:  # PUSH_ACT from the ns

            token = list(byte_data[1:3])
            conn.execute("UPDATE delay SET time_ack = (?) where rowid = \
                         (SELECT rowid FROM delay WHERE token = (?) AND dst = (?) ORDER BY time_gen DESC LIMIT 1)",
                         (time.time(), "%02x%02x" % (token[0], token[1]), "ns"))
            conn.commit()

            continue

        if list(byte_data)[3] == 2:  # PULL_DATA from the gateway
            gw_mac_tmp = byte_data[4:12]
            addr_pull = addr
            
            byte_data = byte_data[0:4] + gw_mac + byte_data[12:]
            
            sock.sendto(byte_data, addr_ns)
            token = list(byte_data[1:3])

            conn.execute("INSERT INTO delay (token, time_gen, dst) VALUES (?, ?, ?)",
                         ("%02x%02x" % (token[0], token[1]), time.time(), "ns"))
            conn.commit()

            byte_data = list(byte_data[:4])
            byte_data[3] = 4
            byte_data = bytes(byte_data)

            byte_data = byte_data[0:4]
            sock.sendto(byte_data, addr_pull)

            continue

        if list(byte_data)[3] == 4: # PULL_ACK from the ns
            token = list(byte_data[1:3])
            conn.execute("UPDATE delay SET time_ack = (?) where rowid = \
                         (SELECT rowid FROM delay WHERE token = (?) AND dst = (?) ORDER BY time_gen DESC LIMIT 1)",
                         (time.time(), "%02x%02x" % (token[0], token[1]), "ns"))
            conn.commit()

            continue

        if list(byte_data)[3] == 3:  # PULL_RSP from the ns, downlink packets
            original_token = byte_data[1:3]

            json_data = json.loads(byte_data[4:].decode())
            if 'txpk' in json_data:
                pkt = json_data['txpk']
                
                pkt["json"] = lib_packet.decode_downlink(pkt, conn)

                logging.info("Received from NS")
                for line in json.dumps(pkt, indent=4, sort_keys=True).split("\n"):
                    logging.info(line)

                byte_data = bytes([2, random.randint(0, 255), random.randint(0, 255), 6]) + \
                           json.dumps({"txpk": pkt}).encode()

                sock.sendto(byte_data, addr_tc)
                
                if "fdev" not in pkt:
                    pkt["fdev"] = None
                if "prea" not in pkt:
                    pkt["prea"] = 8

                conn.execute("INSERT INTO packet \
                             (tmst, rfch, freq, stat, modu, datr, codr, size, data, \
                             time, powe, direction, fdev, prea, json, toa) \
                             VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                             (pkt['tmst'], pkt['rfch'], pkt['freq'], 0, pkt['modu'], pkt['datr'],
                              pkt['codr'], pkt['size'], pkt['data'], time.time(), pkt['powe'], 'down', pkt['fdev'],
                              pkt['prea'], json.dumps(pkt["json"]), get_toa(pkt['size'], pkt['datr'])))
                token = list(byte_data[1:3])
                conn.execute("INSERT INTO delay (token, time_gen, dst) VALUES (?, ?, ?)",
                                 ("%02x%02x" % (token[0], token[1]), time.time(), "tc"))
                conn.commit()
            else:
                token = list(byte_data[1:3])
                conn.execute("INSERT INTO delay (token, time_gen, dst) VALUES (?, ?, ?)",
                             ("%02x%02x"%(token[0], token[1]), time.time(), "gw"))
                conn.commit()
                sock.sendto(byte_data, addr_pull)

            if gw_mac:
                byte_data = list(byte_data[:4])
                byte_data[3] = 5
                byte_data = bytes([2]) + original_token + bytes([5]) + gw_mac
                sock.sendto(byte_data, addr_ns)
            continue

        if list(byte_data)[3] == 5:  # TX_ACK from the gw
            gw_mac_tmp = byte_data[4:12]
            addr_pull = addr

            token = list(byte_data[1:3])
            conn.execute(
                "UPDATE delay SET time_ack = (?) where rowid = \
                (SELECT rowid FROM delay WHERE token = (?) AND dst = (?) ORDER BY time_gen DESC LIMIT 1)",
                (time.time(), "%02x%02x" % (token[0], token[1]), "gw"))
            conn.commit()
            continue

        # interface for test controller
        if list(byte_data)[3] == 6:
            json_data = json.loads(byte_data[4:].decode())

            if 'rxpk' in json_data:
                token = list(byte_data[1:3])
                conn.execute(
                    "UPDATE delay SET time_ack = (?) where rowid = \
                    (SELECT rowid FROM delay WHERE token = (?) AND dst = (?) ORDER BY time_gen DESC LIMIT 1)",
                    (time.time(), "%02x%02x" % (token[0], token[1]), "tc"))
                conn.commit()

                pkt = json_data["rxpk"]

                if not pkt:
                    continue

                logging.info("Received from TC, send to NS")
                for line in json.dumps(pkt, indent=4, sort_keys=True).split("\n"):
                    logging.info(line)


                if pkt["size"] < 0:
                    pkt["data"], pkt["size"] = lib_packet.encode_uplink(pkt["json"], conn)

                if "test" not in pkt:
                    pkt["test"] = None

                pkt_copy = pkt.copy()

                if "json" in pkt_copy:
                    del pkt_copy["json"]
                if "test" in pkt_copy:
                    del pkt_copy["test"]

                byte_data = bytes([2, token[0], token[1], 0]) + gw_mac + json.dumps({"rxpk": [pkt_copy]}).encode()

                sock.sendto(byte_data, addr_ns)

                conn.execute("INSERT INTO packet (tmst, chan, rfch, freq, stat, modu, datr, \
                             codr, lsnr, rssi, size, data, time, direction, json, test, toa) \
                             VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                             (pkt['tmst'], pkt['chan'], pkt['rfch'], pkt['freq'], 1, pkt['modu'], pkt['datr'],
                              pkt['codr'], pkt['lsnr'], pkt['rssi'], pkt['size'], pkt['data'], time.time(), 'up',
                              json.dumps(pkt["json"]), json.dumps(pkt["test"]), get_toa(pkt['size'], pkt['datr'])))
                token = list(byte_data[1:3])
                conn.execute("INSERT INTO delay (token, time_gen, dst) VALUES (?, ?, ?)",
                             ("%02x%02x" % (token[0], token[1]), time.time(), "ns"))
                conn.commit()

                continue
            if 'txpk' in json_data:
                token = list(byte_data[1:3])
                conn.execute(
                    "UPDATE delay SET time_ack = (?) where rowid = \
                    (SELECT rowid FROM delay WHERE token = (?) AND dst = (?) ORDER BY time_gen DESC LIMIT 1)",
                    (time.time(), "%02x%02x" % (token[0], token[1]), "tc"))
                conn.commit()
                
                if addr_pull:
                    pkt = json_data["txpk"]

                    if not pkt:
                        continue

                    if json_data["txpk"]["size"] < 0:
                        pkt["data"], pkt["size"] = lib_packet.encode_downlink(pkt["json"], conn)
                    
                    logging.info("Received from TC, send to GW")
                    for line in json.dumps(pkt, indent=4, sort_keys=True).split("\n"):
                        logging.info(line)

                    if "test" not in pkt:
                        pkt["test"] = None

                    pkt["powe"] = min([pkt["powe"], 21])

                    pkt_copy = pkt.copy()

                    if "json" in pkt_copy:
                        del pkt_copy["json"]
                    if "test" in pkt_copy:
                        del pkt_copy["test"]
                    if "time" in pkt_copy:
                        del pkt_copy["time"]
                        
                    data = json.dumps({"txpk": pkt_copy})
                    byte_data = bytes([2, token[0], token[1], 3]) + data.encode()
                    sock.sendto(byte_data, addr_pull)
                    
                    if "fdev" not in pkt:
                        pkt["fdev"] = None
                    if "prea" not in pkt:
                        pkt["prea"] = 8
                    conn.execute("INSERT INTO packet \
                                 (tmst, rfch, freq, stat, modu, datr, codr, size, data, \
                                 time, powe, direction, fdev, prea, json, test, toa) \
                                 VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                                 (pkt['tmst'], pkt['rfch'], pkt['freq'], 1, pkt['modu'], pkt['datr'],
                                  pkt['codr'], pkt['size'], pkt['data'], time.time(), pkt['powe'], 'down', pkt['fdev'],
                                  pkt['prea'], json.dumps(pkt["json"]), json.dumps(pkt["test"]),
                                  get_toa(pkt['size'], pkt['datr'])))
                    token = list(byte_data[1:3])
                    conn.execute("INSERT INTO delay (token, time_gen, dst) VALUES (?, ?, ?)",
                                 ("%02x%02x" % (token[0], token[1]), time.time(), "gw"))
                    conn.commit()
                continue

        logging.error("Error UDP identifier:" + str(byte_data[2]))


if __name__== "__main__":
    reliable_run(run_proxy, loop = True)
