#file      proxy.py

#brief      set of functions to process packets between NS, tst controller and gateway

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

from lib_base import addr_ns, addr_tc, gw_mac, DB_FILE_PROXY, DB_FILE_BACKUP, addr_pf, reliable_run,\
    deduplication_threshold, MAX_TX_POWER, PROC_MSG, reverse_eui
from lib_packet import get_toa, Codec
from lib_db import recover_db_proxy, create_db_tables_proxy

buffer = {}


def append_packet(pkt, packets, test_inst_id, conn):
    packets.append(pkt)
    if pkt["stat"] == 0 and pkt["direction"] == "up":
        logging.debug("[proxy] uplink before tc")
        conn.execute("INSERT INTO packet (TestInstID, tmst, chan, rfch, freq, stat, modu, datr, "
                     "codr, lsnr, rssi, size, data, time, direction, json, toa) "
                     "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                     (test_inst_id, pkt['tmst'], pkt['chan'], pkt['rfch'], pkt['freq'], pkt["stat"], pkt['modu'], pkt['datr'],
                      pkt['codr'], pkt['lsnr'], pkt['rssi'], pkt['size'], pkt['data'], pkt["time"], pkt["direction"],
                      json.dumps(pkt["json"]), get_toa(pkt['size'], pkt['datr'])))
    elif pkt["stat"] == 0 and pkt["direction"] == "down":
        logging.debug("[proxy] downlink before tc")
        conn.execute("INSERT INTO packet "
                     "(TestInstID, tmst, rfch, freq, stat, modu, datr, codr, size, data, "
                     "time, powe, direction, fdev, prea, json, toa) "
                     "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                     (test_inst_id, pkt['tmst'], pkt['rfch'], pkt['freq'], pkt["stat"], pkt['modu'], pkt['datr'],
                      pkt['codr'], pkt['size'], pkt['data'], pkt["time"], pkt['powe'], pkt["direction"], pkt['fdev'],
                      pkt['prea'], json.dumps(pkt["json"]), get_toa(pkt['size'], pkt['datr'])))
    elif pkt["stat"] == 1 and pkt["direction"] == "up":
        logging.debug("[proxy] uplink after tc")
        conn.execute("INSERT INTO packet (TestInstID, tmst, chan, rfch, freq, stat, modu, datr, "
                     "codr, lsnr, rssi, size, data, time, direction, json, toa) "
                     "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                     (test_inst_id, pkt['tmst'], pkt['chan'], pkt['rfch'], pkt['freq'], pkt["stat"], pkt['modu'], pkt['datr'],
                      pkt['codr'], pkt['lsnr'], pkt['rssi'], pkt['size'], pkt['data'], pkt["time"], pkt["direction"],
                      json.dumps(pkt["json"]), get_toa(pkt['size'], pkt['datr'])))
    elif pkt["stat"] == 1 and pkt["direction"] == "down":
        logging.debug("[proxy] downlink after tc")
        conn.execute("INSERT INTO packet "
                     "(TestInstID, tmst, rfch, freq, stat, modu, datr, codr, size, data, "
                     "time, powe, direction, fdev, prea, json, toa) "
                     "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                     (test_inst_id, pkt['tmst'], pkt['rfch'], pkt['freq'], pkt["stat"], pkt['modu'], pkt['datr'],
                      pkt['codr'], pkt['size'], pkt['data'], pkt["time"], pkt['powe'], pkt["direction"], pkt['fdev'],
                      pkt['prea'], json.dumps(pkt["json"]),
                      get_toa(pkt['size'], pkt['datr'])))
    conn.commit()


def append_delay(token, time, dst, delays):
    delay = {}
    delay["token"] = "%02x%02x" % (token[0], token[1])
    delay["time_gen"] = time
    delay["dst"] = dst
    logging.debug("[proxy] append delay: {}".format(delay))
    delays.append(delay)


def update_delay(token, dst, delays, test_inst_id, conn):
    token_tmp = "%02x%02x" % (token[0], token[1])
    for delay in delays[::-1]:
        if delay["token"] == token_tmp and delay["dst"] == dst:
            logging.debug("[proxy] update delay: {}".format(delay))
            if "time_ack" not in delay:
                delay["time_ack"] = time.time()
                conn.execute("INSERT INTO delay (TestInstID, token, time_gen, dst, time_ack) VALUES (?, ?, ?, ?, ?)",
                         (test_inst_id, delay["token"], delay["time_gen"], delay["dst"],
                          delay["time_ack"]))
                conn.commit()
            else:
                logging.warning("Ack has already been received. Remove duplicate")
            break


def get_device(deveui):
    conn = sqlite3.connect(DB_FILE_BACKUP, timeout=60)
    conn.row_factory = sqlite3.Row
    device = conn.execute("SELECT * from device WHERE devEUI = (?)", (deveui,)).fetchone()
    if device:
        device = dict(device)
        device['DevEui'] = reverse_eui(device['DevEui'])
        response = conn.execute("SELECT Region from regionSKU WHERE SkuID = (?)", (device['SkuID'],)).fetchone()
        if response:
            region = dict(response)
            logging.debug("region is {}".format(region))
            device['region'] = region['Region']
        else:
            device = None
            logging.error("Cannot find region information for device: {}".format(deveui))
    else:
        logging.error("Cannot find information for device: {}".format(deveui))
    conn.close()
    return device


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

    packets = []
    delays = []
    is_test_running = False
    test_inst_id = 0
    logging.debug("proxy successfully started")
    t = 0
    codec = Codec(conn, test_inst_id)

    while True:

        to_be_removed = []
        for pl in buffer:
            pkt = buffer[pl]["pkt"]
            if time.time() - buffer[pl]["time"] > deduplication_threshold:
                to_be_removed.append(pl)

                pkt["json"] = codec.decode_uplink(pkt)
                logging.info("Received from GW")
                for line in json.dumps(pkt, indent=4, sort_keys=True).split("\n"):
                    logging.info(line)

                if "error" in pkt["json"]:
                    continue

                pkt["time"] = time.time()
                pkt["direction"] = "up"
                byte_data = bytes([2, random.randint(0, 255), random.randint(0, 255), 6]) + \
                            json.dumps({"rxpk": pkt}).encode()
                sock.sendto(byte_data, addr_tc)

                pkt["stat"] = 0
                token = list(byte_data[1:3])
                if is_test_running:
                    append_packet(pkt, packets, test_inst_id, conn)
                    append_delay(token, buffer[pl]["time"], "tc", delays)

        for pl in to_be_removed:
            del buffer[pl]

        try:
            byte_data, addr = sock.recvfrom(10240)
        except socket.timeout:
            continue
        except ConnectionResetError:
            logging.error("ConnectionResetError, check test controller")
            continue

        time_of_arrival = time.time()
        msg_type = list(byte_data)[3]
        logging.debug("received data: {}, msg_type:{}".format(list(byte_data)[0:5],
                                                              msg_type))
        if msg_type in [PROC_MSG["TC_DATA"]]:
            logging.info(str(msg_type) + " controller -> proxy")
        elif msg_type in [PROC_MSG["GW_PUSH_DATA"], PROC_MSG["GW_PULL_DATA"], PROC_MSG["GW_TX_ACK"]]:
            logging.debug(str(msg_type) + " Packetforwarder -> proxy")
        elif msg_type in [PROC_MSG["NS_PUSH_ACK"], PROC_MSG["NS_PULL_RSP"], PROC_MSG["NS_PULL_ACK"]]:
            logging.debug(str(msg_type) + " NS -> proxy")
        elif msg_type == PROC_MSG["TC_SETUP_TEST"]:
            is_test_running = True
            test_instance = json.loads(byte_data[4:].decode())
            device = get_device(test_instance["DevEui"])
            test_inst_id = test_instance["TestInstID"]
            logging.debug("start new test, device is: {}".format(device))
            codec = Codec(conn, test_inst_id, device)
            packets = []
            delays = []
            continue
        elif msg_type == PROC_MSG["TC_GET_PACKET"]:
            byte_data = json.dumps(packets).encode()
            logging.debug("[proxy] packets length is:{}, dst addr is:{}".format(len(byte_data), addr))
            sock.sendto(byte_data, addr)
            continue
        elif msg_type == PROC_MSG["TC_TEARDOWN_TEST"]:
            logging.debug("[proxy] sent stop response")
            is_test_running = False
            packets = []
            delays = []
            continue

        if msg_type == 0:  # PUSH_DATA from the gateway, uplink packets
            original_token = byte_data[1:3]

            addr_push = addr
            gw_mac_tmp = byte_data[4:12]

            json_data = json.loads(byte_data[12:].decode())

            if 'rxpk' in json_data:
                logging.info("rx packet received from gateway at {}".format(time.time()))
                for pkt in json_data['rxpk']:
                    if pkt["data"] not in buffer:
                        buffer[pkt["data"]] = {"pkt": pkt, "time": time_of_arrival}
                    else:
                        logging.info("duplicate packet received. ")
                        if int(pkt["rssi"]) > int(buffer[pkt["data"]]["pkt"]["rssi"]):
                            buffer[pkt["data"]]["pkt"] = pkt
            else:
                byte_data = byte_data[0:4] + gw_mac + byte_data[12:]
                sock.sendto(byte_data, addr_ns)

                token = list(original_token)
                if is_test_running:
                    append_delay(token, time.time(), "ns", delays)

            byte_data = bytes([2]) + original_token + bytes([1])
            sock.sendto(byte_data, addr_push)

            continue

        if msg_type == 1:  # PUSH_ACK from the ns
            if is_test_running:
                update_delay(token, "ns", delays, test_inst_id, conn)

            continue

        if msg_type == 2:  # PULL_DATA from the gateway
            gw_mac_tmp = byte_data[4:12]
            addr_pull = addr

            byte_data = byte_data[0:4] + gw_mac + byte_data[12:]

            sock.sendto(byte_data, addr_ns)
            token = list(byte_data[1:3])
            if is_test_running:
                append_delay(token, time.time(), "ns", delays)

            byte_data = list(byte_data[:4])
            byte_data[3] = 4
            byte_data = bytes(byte_data)

            byte_data = byte_data[0:4]
            sock.sendto(byte_data, addr_pull)

            continue

        if msg_type == 4: # PULL_ACK from the ns
            if is_test_running:
                update_delay(token, "ns", delays, test_inst_id, conn)
            continue

        if msg_type == 3:  # PULL_RSP from the ns, downlink packets
            original_token = byte_data[1:3]

            json_data = json.loads(byte_data[4:].decode())
            if 'txpk' in json_data:
                pkt = json_data['txpk']
                pkt["json"] = codec.decode_downlink(pkt)
                logging.info("Received from NS")
                for line in json.dumps(pkt, indent=4, sort_keys=True).split("\n"):
                    logging.info(line)

                if "error" in pkt["json"]:
                    continue

                pkt["time"] = time.time()
                pkt["direction"] = "down"
                byte_data = bytes([2, random.randint(0, 255), random.randint(0, 255), 6]) + \
                           json.dumps({"txpk": pkt}).encode()
                sock.sendto(byte_data, addr_tc)

                if "fdev" not in pkt:
                    pkt["fdev"] = None
                if "prea" not in pkt:
                    pkt["prea"] = 8
                pkt["stat"] = 0
                token = list(byte_data[1:3])
                if is_test_running:
                    append_packet(pkt, packets, test_inst_id, conn)
                    append_delay(token, time_of_arrival, "tc", delays)
            else:
                if is_test_running:
                    append_delay(token, time.time(), "gw", delays)
                sock.sendto(byte_data, addr_pull)

            if gw_mac:
                byte_data = list(byte_data[:4])
                byte_data[3] = 5
                byte_data = bytes([2]) + original_token + bytes([5]) + gw_mac
                sock.sendto(byte_data, addr_ns)
            continue

        if msg_type == 5:  # TX_ACK from the gw
            gw_mac_tmp = byte_data[4:12]
            addr_pull = addr

            token = list(byte_data[1:3])
            if is_test_running:
                update_delay(token, "gw", delays, test_inst_id, conn)
            continue

        # interface for test controller
        if msg_type == 6:
            json_data = json.loads(byte_data[4:].decode())

            if 'rxpk' in json_data:
                token = list(byte_data[1:3])

                pkt = json_data["rxpk"]
                logging.info("Received from TC, send to NS")
                for line in json.dumps(pkt, indent=4, sort_keys=True).split("\n"):
                    logging.info(line)

                if not pkt:
                    continue

                if pkt["size"] < 0:
                    pkt["data"], pkt["size"] = codec.encode_uplink(pkt["json"])

                pkt_copy = pkt.copy()
                for key in ("json", "time", "direction"):
                    if key in pkt_copy:
                        del pkt_copy[key]

                byte_data = bytes([2, token[0], token[1], 0]) + gw_mac + json.dumps({"rxpk": [pkt_copy]}).encode()
                sock.sendto(byte_data, addr_ns)

                pkt["stat"] = 1
                pkt["time"] = time.time()
                pkt["direction"] = "up"
                if is_test_running:
                    update_delay(token, "tc", delays, test_inst_id, conn)
                    append_packet(pkt, packets, test_inst_id, conn)
                    append_delay(token, pkt["time"], "ns", delays)

                continue
            if 'txpk' in json_data:
                token = list(byte_data[1:3])

                if addr_pull:
                    pkt = json_data["txpk"]
                    logging.info("Received from TC, send to GW")
                    for line in json.dumps(pkt, indent=4, sort_keys=True).split("\n"):
                        logging.info(line)

                    if not pkt:
                        if is_test_running:
                            update_delay(token, "tc", delays, test_inst_id, conn)
                        continue

                    if json_data["txpk"]["size"] < 0:
                        pkt["data"], pkt["size"] = codec.encode_downlink(pkt["json"])

                    pkt["powe"] = min([pkt["powe"], MAX_TX_POWER])
                    pkt_copy = pkt.copy()
                    for key in ("json", "time", "direction"):
                        if key in pkt_copy:
                            del pkt_copy[key]

                    data = json.dumps({"txpk": pkt_copy})
                    byte_data = bytes([2, token[0], token[1], 3]) + data.encode()
                    sock.sendto(byte_data, addr_pull)

                    if "fdev" not in pkt:
                        pkt["fdev"] = None
                    if "prea" not in pkt:
                        pkt["prea"] = 8

                    pkt["stat"] = 1
                    pkt["time"] = time.time()
                    pkt["direction"] = "down"
                    if is_test_running:
                        update_delay(token, "tc", delays, test_inst_id, conn)
                        append_packet(pkt, packets, test_inst_id, conn)
                        append_delay(token, time.time(), "gw", delays)
                continue

        logging.error("Error UDP identifier:" + str(byte_data[3]))


if __name__== "__main__":
    reliable_run(run_proxy, loop = True)
