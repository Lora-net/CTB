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
from lib_packet import get_toa


def verify_join_deny(tc):
    packets = tc.get_all_packets()
    dev_nonce = []
    toa = 0
    datr = []

    passed_tests = 0

    packets = [packet for packet in packets if packet["json"]["MType"] == "000"]

    tc.veri_msg['details'] = {'keys': ["DevNonce", "JoinEUI", "Time", "freq", "datr", "toa"],
                              'rows': []}

    freq_125 = []
    for packet in packets:
        if packet["json"]["MType"] == lib.JOIN_REQUEST:
            if 'toa' not in packet:
                packet['toa'] = get_toa(packet['size'], packet['datr'])

            row = []
            for key in tc.veri_msg['details']['keys']:
                if key in ["Time"]:
                    row.append(str(datetime.fromtimestamp(packet["time"]))[:-7])
                elif key in ["freq", "datr", "toa"]:
                    row.append(packet[key])
                elif key in ["DevNonce", "JoinEUI"]:
                    row.append(packet["json"][key])
            tc.veri_msg['details']['rows'].append(row)

            dev_nonce.append(packet["json"]["DevNonce"])
            datr.append(packet["datr"])
            toa += packet["toa"]

            if packet["datr"].find("125") >= 0 and packet["freq"] not in freq_125:
                freq_125.append(packet["freq"])

    Different_DevNonce = len(list(set(dev_nonce))) >= 1
    Duplicate_DevNonce = len(list(set(dev_nonce))) != len(dev_nonce)
    if len(packets) > 1:
        dc = toa / (packets[-1]["time"] - packets[0]["time"]) * 100
    else:
        dc = 100
    bw500_Used = ("SF8BW500" in datr)
    multiple_bw125 = len(freq_125) > 1

    tc.veri_msg['verification'] = [("Different DevNonce", Different_DevNonce, Different_DevNonce),
                                   ("Duplicate DevNonce", Duplicate_DevNonce, not Duplicate_DevNonce),
                                   ("Duty cycle", dc, True),
                                   ("Multiple 125kHz channel used", multiple_bw125, multiple_bw125)]
    if packets[0]["json"]["region"] == "US":
        tc.veri_msg['verification'].append(("500kHz channel Used", bw500_Used, bw500_Used))

    passed = True
    for item in tc.veri_msg['verification']:
        passed = passed and item[2]

    assert passed, "verification failed"

# configuration on timeout in second
test_join_deny_timeout = 500

def test_join_deny(tc):
    if tc.verify_only:
        verify_join_deny(tc)
        return

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

    tc.wait_for_packet([lib.JOIN_REQUEST], timeout['step1'])
    logging.debug("found join request packet")

    tc.packet_count = 0
    start_time = time.time()
    while tc.packet_count < test_spec['packet_number'] and time.time()-start_time < timeout['step2']:
        pkt = tc.receive()
        if pkt:
            if pkt["json"]["MType"] == lib.JOIN_ACCEPT:
                tc.packet_count += 1
                pkt = None
            tc.send(pkt)
    assert tc.packet_count == test_spec['packet_number'], 'receiving "Join Accept" timed out'

    verify_join_deny(tc)


def verify_join_mic(tc):
    packets = tc.get_all_packets()

    suc = True
    for packet in packets:
        if packet["json"]["MType"] in [lib.UNCONFIRMED_DATA_UP, lib.CONFIRMED_DATA_UP,
                                       lib.UNCONFIRMED_DATA_DOWN, lib.CONFIRMED_DATA_DOWN]:
            suc = False
    tc.veri_msg['verification'] = [("Deny join accept with wrong MIC", suc, suc)]

    assert suc, "verification failed"

test_join_mic_timeout = 500

def test_join_mic(tc):
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

    tc.wait_for_packet([lib.JOIN_REQUEST], timeout['step1'])
    logging.debug("found join request packet")

    tc.packet_count = 0
    start_time = time.time()
    while tc.packet_count < test_spec['packet_number'] and time.time()-start_time < timeout['step2']:
        pkt = tc.receive()
        if pkt:
            if pkt["json"]["MType"] == lib.JOIN_ACCEPT:
                tc.packet_count += 1
                pkt['json']['mic'] = 'random'
                pkt['size'] = -1
            tc.send(pkt)
    assert tc.packet_count == test_spec['packet_number'], 'receiving "Join Accept" timed out'

    verify_join_mic(tc)


def verify_join_rx2(tc):
    packets = tc.get_all_packets()

    suc = True
    previous_mtype = None
    for packet in packets:
        if previous_mtype == lib.UNCONFIRMED_DATA_UP:
            if packet["json"]["MType"] not in [lib.UNCONFIRMED_DATA_UP, lib.CONFIRMED_DATA_UP]:
                suc = False
        previous_mtype = packet["json"]["MType"]

    tc.veri_msg['verification'] = [("Join accept with wrong MIC", suc, suc)]

    assert suc, "verification failed"

test_join_rx2_timeout = 500

def test_join_rx2(tc):
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

    tc.wait_for_packet([lib.JOIN_REQUEST], timeout['step1'])
    logging.debug("found join request packet")

    tc.packet_count = 0
    start_time = time.time()
    success = False
    while not success and time.time()-start_time < timeout['step2']:
        pkt = tc.receive()
        if pkt:
            if pkt["json"]["MType"] == lib.JOIN_REQUEST:
                pass
            elif pkt["json"]["MType"] == lib.JOIN_ACCEPT:
                tc.packet_count += 1
                if pkt["json"]["region"] == "US":
                    pkt["tmst"] += 1000000
                    pkt["datr"] = "SF12BW500"
                    pkt["freq"] = 923.3
                if pkt["json"]["region"] == "EU":
                    pkt["tmst"] += 1000000
                    pkt["datr"] = "SF9BW125"
                    pkt["freq"] = 869.525
            else:
                success = True
            tc.send(pkt)
    assert success, "Joining network through Rx2 timed out"

    verify_join_rx2(tc)
