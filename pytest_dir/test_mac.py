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

import logging
import time
from datetime import datetime
import sys

sys.path.append("..")
import lib_base as lib
from web_result import generate_passed_table

def verify_ack(packets, req, ack):
    suc = True
    previous_mac_commands = []
    for packet in packets:
        if packet["json"]["MType"] in [lib.UNCONFIRMED_DATA_UP, lib.CONFIRMED_DATA_UP]:
            sent = False
            for previous_mac_command in previous_mac_commands:
                if req in previous_mac_command:
                    sent = True
            acked = False
            if sent:
                for mac_command in packet["json"]["MAC Commands"]:
                    if ack in mac_command and mac_command[ack]:
                        acked = True
                if not acked:
                    suc = False
        if not suc:
            break
        if packet["json"]["MType"] in [lib.UNCONFIRMED_DATA_DOWN, lib.CONFIRMED_DATA_DOWN,
                                       lib.UNCONFIRMED_DATA_UP, lib.CONFIRMED_DATA_UP]:
            previous_mac_commands = packet["json"]["MAC Commands"]
    return suc

def verify_mac_status(tc):
    packets = tc.get_all_packets()
    suc1 = verify_ack(packets, "DevStatusReq", "Battery")
    tc.veri_msg['verification'] = [("Respond to DevStatusReq", suc1, suc1)]

    assert suc1, "verification failed"

test_mac_status_timeout = 500

def test_mac_status(tc):
    timeout = {
        'step1': 120,
        'step2': 300
    }
    tc.overwrite_params_from_config(timeout)

    test_spec = {
        'criteria': 'count',
        'packet_number': 4
    }
    tc.overwrite_params_from_config(test_spec)

    tc.wait_for_packet([lib.JOIN_ACCEPT], timeout['step1'])
    logging.debug("found join request packet")

    tc.packet_count = 0
    start_time = time.time()
    while tc.packet_count < test_spec['packet_number'] and time.time()-start_time < timeout['step2']:
        pkt = tc.receive()
        if pkt:
            if pkt["json"]["MType"] not in [lib.JOIN_REQUEST, lib.JOIN_ACCEPT]:
                pkt["json"]["MAC Commands"] = []
                pkt["json"]["FOpts"] = ""
                if pkt["json"]["FPort"] == 0:
                    pkt["json"]["FPort"] = -1
                pkt["size"] = -1

                if pkt["json"]["MType"] in [lib.UNCONFIRMED_DATA_UP, lib.CONFIRMED_DATA_UP]:
                    tc.packet_count += 1
                    pkt["json"]["MType"] = lib.CONFIRMED_DATA_UP
                elif pkt["json"]["MType"] in [lib.UNCONFIRMED_DATA_DOWN, lib.CONFIRMED_DATA_DOWN]:
                    pkt["json"]["MAC Commands"] = [{"Command": "DevStatusReq", "DevStatusReq": None}]
                    pkt["json"]["FOpts"] = "06"

            tc.send(pkt)
    assert tc.packet_count == test_spec['packet_number'], "receiving uplink data timed out"

    verify_mac_status(tc)
