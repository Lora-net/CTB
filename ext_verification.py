#file      ext_verification.py

#brief      passed/failed test verification functions definition     

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

import mpld3
import json
from datetime import datetime
import numpy as np
import matplotlib.pyplot as plt

from lib_base import datrLUT


def generate_passed_table(result):

    html = '<html><table border="1"><tr>'
    for key in ["Criteria", "Result", "Passed"]:
        html += "<th>" + key + "</th>"
    html += "</tr>"
    
    passed = True
    for i in range(len(result)):
        html += "<td>{}</td>".format(result[i][0])
        html += "<td>{}</td>".format(result[i][1])
        html += "<td>{}</td>".format(result[i][2])
        html += "</tr>"
        
        passed = passed and result[i][2]
        
    html += "</table></html>"
    
    return html, passed


def verify_join_deny(packets, response):
    html = ""

    dev_nonce = []
    toa = 0
    datr = []
    
    passed_tests = 0
    
    packets = [packet for packet in packets if packet["json"]["MType"] == "000"]
    
    if not packets:
        return "Device already joined <hr>", -2
        
    html_table = '<html><table border="1"><tr>'
    for key in ["DevNonce", "JoinEUI", "Time", "freq", "datr", "toa"]:
        html_table += "<th>" + key + "</th>"
    html_table += "</tr>"

    freq_125 = []
    for packet in packets:
        if packet["json"]["MType"] == "000":
            html_table += "<tr>"
            for key in ["DevNonce", "JoinEUI", "Time", "freq", "datr", "toa"]:
                if key in ["Time"]:
                    html_table += "<td>{}</td>".format(str(datetime.fromtimestamp(packet["time"]))[:-7])
                if key in ["freq", "datr", "toa"]:
                    html_table += "<td>{}</td>".format(str(packet[key]))
                if key in ["DevNonce", "JoinEUI"]:
                    html_table += "<td>{}</td>".format(str(packet["json"][key]))

            dev_nonce.append(packet["json"]["DevNonce"])
            datr.append(packet["datr"])
            toa += packet["toa"]
            
            if packet["datr"].find("125") >= 0 and packet["freq"] not in freq_125:
                freq_125.append(packet["freq"])
            
            html_table += "</tr>"
    html_table += "</table></html>"
    
    Different_DevNonce = len(list(set(dev_nonce))) >= 1
    Duplicate_DevNonce = len(list(set(dev_nonce))) != len(dev_nonce)
    if len(packets) > 1:
        dc = toa / (packets[-1]["time"] - packets[0]["time"]) * 100
    else:
        dc = 100
    bw500_Used = ("SF8BW500" in datr)
    multiple_bw125 = len(freq_125) > 1

    if packets:
        if packets[0]["json"]["region"] == "US":
            html, passed = generate_passed_table([("Different DevNonce", Different_DevNonce, Different_DevNonce),
                                                  ("Duplicate DevNonce", Duplicate_DevNonce, not Duplicate_DevNonce),
                                                  ("Duty cycle", dc, True),
                                                  ("500kHz channel Used", bw500_Used, bw500_Used),
                                                  ("Multiple 125kHz channel used", multiple_bw125, multiple_bw125)])
        else:
            html, passed = generate_passed_table([("Different DevNonce", Different_DevNonce, Different_DevNonce),
                                                  ("Duplicate DevNonce", Duplicate_DevNonce, not Duplicate_DevNonce),
                                                  ("Duty cycle", dc, True),
                                                  ("Multiple 125kHz channel used", multiple_bw125, multiple_bw125)])
    else:
        html, passed = "", -1


    html += "<br>Details<br>"
    html += html_table
    html += "<hr>"

    return html, int(passed)*2-1


def verify_join_mic(packets, response):
    if response["CurrentPara"] == 0:
        return "Device already joined <hr>", -2

    suc = True
    for packet in packets:
        if packet["json"]["MType"] in ["010", "100", "101", "011"]:
            suc = False
    html, passed = generate_passed_table([("Deny join accept with wrong MIC", suc, suc)])
    
    html += "<hr>"
    return html, 2*int(passed) - 1
    
    
def verify_join_rx2(packets, response):
    if response["CurrentPara"] == 0:
        return "Device already joined <hr>", -2

    suc = True
    previous_mtype = None
    for packet in packets:
        if previous_mtype == "010":
            if packet["json"]["MType"] not in ["010", "100"]:
                suc = False
        previous_mtype = packet["json"]["MType"]
    
    html, passed = generate_passed_table([("Join accept with wrong MIC", suc, suc)])
    
    html += "<hr>"
    return html, 2*int(passed) - 1


def verify_downlink_offset(packets, response):
    html = ""
    per0 = 100

    error = False
    if "000" in [packet["json"]["MType"] for packet in packets]:
        html += "Error: Join Request in Log <br>"
        error = True
    if "001" in [packet["json"]["MType"] for packet in packets]:
        html += "Error: Join Accept in Log <br>"
        error = True
    if error:
        return html + "<br><hr>", -1

    data = {}

    previous_uplink_f_cnt = None
    offset = None

    for packet in packets:
        if packet["direction"] == "up":
            if (offset != None) and previous_uplink_f_cnt:
                if offset not in data:
                    data[offset] = []
                if packet["json"]["FCnt"] == previous_uplink_f_cnt + 1:
                    if packet["json"]["ACK"] == "1":
                        data[offset].append(1)
                    else:
                        data[offset].append(0)
            offset = None
            previous_uplink_f_cnt = packet["json"]["FCnt"]
        else:
            try:
                offset = packet["test"]["offset"]
            except:
                offset = None

    x = []
    y = []

    for offset in sorted(data.keys()):
        if data[offset]:
            x.append(offset)
            y.append(1 - np.mean(data[offset]))

    html = '<html><table border="1"><tr>'
    for key in ["Criteria", "Result", "Passed"]:
        html += "<th>" + key + "</th>"
    html += "</tr>"

    y = [m for _,m in sorted(zip(x,y))]
    x = sorted(x)        
    
    if x:
        steps = 1000
        spacing = (x[-1]-x[0])/steps
        
        yp = np.interp(np.linspace(x[-1], x[0], steps), x, y)
        tolerance = np.sum(yp<0.1)*spacing
    else:
        tolerance = 0

    if 0 in data:
        per0 = (1 - np.mean(data[0])) * 100
    else:
        per0 = 100
        
    html, result = generate_passed_table([("PER without Offset", per0, per0 < 0.05), 
                                  ("Tolerance with PER < 10%", tolerance, tolerance > 0)])
    
    fig = plt.figure(figsize=(8.5, 3))
    ax = fig.add_subplot(111)
    ax.plot(x, y, "-o")
    ax.grid()
    ax.set_xlabel("offset")
    ax.set_ylabel("PER")

    plt.tight_layout()
    html += mpld3.fig_to_html(fig)
    plt.close(fig)

    html += "<hr>"

    return html, int(result)*2-1


def verify_downlink_timing(packets, response):
    return verify_downlink_offset(packets, response)


def verify_downlink_freq(packets, response):
    return verify_downlink_offset(packets, response)
    

def veryfy_downlink_with_mac(packets, response, reverse = False):
    html = '<html><table border="1"><tr>'
    for key in ["Time", "Freq", "MType", "ACK", "FCnt", "MAC Commands"]:
        html += "<th>" + key + "</th>"
    
    suc = True
    previous_uplink_f_cnt = 1e9
    previous_mtype = None
    for packet in packets:
        if packet["json"]["MType"] in ["010", "100"] and previous_mtype == "101" and previous_uplink_f_cnt + 1 == packet["json"]["FCnt"]:
            if reverse:
                if packet["json"]["ACK"] == "1":
                    suc = False
            else:
                if packet["json"]["ACK"] == "0":
                    suc = False
        if packet["json"]["MType"] in ["010", "100"]:
            previous_uplink_f_cnt = packet["json"]["FCnt"]
        if packet["json"]["MType"] in ["010", "100", "011", "101"]:
            html += "<tr>"
            html += "<td>" + str(datetime.fromtimestamp(packet["time"]))[:-5] + "</td>"
            html += "<td>" + "%.1f" % packet["freq"] + "</td>"
            html += "<td>" + packet["json"]["MType"] + "</td>"
            html += "<td>" + packet["json"]["ACK"] + "</td>"
            html += "<td>" + "%d" % packet["json"]["FCnt"] + "</td>"
            if packet["json"]["MAC Commands"]:
                html += "<td>" + json.dumps(packet["json"]["MAC Commands"]) + "</td>"
            else:
                html += "<td></td>"
            html += "</tr>"
            
        previous_mtype = packet["json"]["MType"]
    html += "</table></html>"
    return html, suc


def verify_downlink_cnt(packets, response):
    html_list, suc = veryfy_downlink_with_mac(packets, response, reverse = True)
    html, result = generate_passed_table([("Deny all downlinks with invalid FCnt", suc, suc)])
    html = html + "<br>" + html_list + "<hr>"
    
    return html, 2*int(result)-1


def verify_downlink_mic(packets, response):
    html_list, suc = veryfy_downlink_with_mac(packets, response, reverse = True)
    html, result = generate_passed_table([("Deny all downlinks with invalid MIC", suc, suc)])
    html = html + "<br>" + html_list + "<hr>"
    
    return html, 2*int(result)-1


def verify_downlink_confirmed(packets, response):
    html_list, suc = veryfy_downlink_with_mac(packets, response)

    html, result = generate_passed_table([("ACK all confirmed downlinks", suc, suc)])
    html = html + "<br>" + html_list + "<hr>"
    
    return html, 2*int(suc)-1


def verify_ack(packets, req, ack):
    suc = True
    previous_mac_commands = []
    for packet in packets:
        if packet["json"]["MType"] in ["010", "100"]:
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
        if packet["json"]["MType"] in ["011", "101", "010", "100"]:
            previous_mac_commands = packet["json"]["MAC Commands"]
    return suc
        
        
def verify_mac_rx_para_rx1dro(packets, response):
    html_list, suc0 = veryfy_downlink_with_mac(packets, response)
    suc1 = verify_ack(packets, "RX1DRoffset", "RX1DRoffset ACK")
    
    html, result = generate_passed_table([("Receive all downlinks", suc0, suc0), 
                                          ("ACK all RX1DRoffset Requests", suc1, suc1)])    
    html = html + "<br>" + html_list + "<hr>"
    return html, 2*int(result)-1
        
        
def verify_mac_rx_para_rx2dr(packets, response):
    html_list, suc0 = veryfy_downlink_with_mac(packets, response)
    suc1 = verify_ack(packets, "RX2DataRate", "RX2 Data rate ACK")
    html, result = generate_passed_table([("Receive all downlinks", suc0, suc0), 
                                          ("ACK all RX2 Data rate requests", suc1, suc1)])    
    html = html + "<br>" + html_list + "<hr>"
    return html, 2*int(result)-1
    
    
def verify_mac_rx_para_rx2freq(packets, response):
    html_list, suc0 = veryfy_downlink_with_mac(packets, response)
    suc1 = verify_ack(packets, "Frequency", "Channel ACK")
    html, result = generate_passed_table([("Receive all downlinks", suc0, suc0), 
                                          ("ACK all RX2 Frequency Requests", suc1, suc1)])    
    html = html + "<br>" + html_list + "<hr>"
    return html, 2*int(result)-1


def verify_mac_rx_timing(packets, response):
    html_list, suc0 = veryfy_downlink_with_mac(packets, response)
    suc1 = verify_ack(packets, "Del", "RXTimingSetupAns")
    html, result = generate_passed_table([("Receive all downlinks", suc0, suc0), 
                                          ("ACK all RX Timing", suc1, suc1)])    
    html = html + "<br>" + html_list + "<hr>"
    return html, 2*int(result)-1


def verify_mac_mask(packets, response, bw = 125):
    suc0 = True

    check_channel = False
    
    previous_mac_commands = []
    for packet in packets:
        if packet["json"]["MType"] in ["011", "101"]:
            if bw == 125:
                for mac_command in packet["json"]["MAC Commands"]:
                    if "ChMask" in mac_command and mac_command["ChMask"] == "0000111100000000":
                        check_channel = True
                    if "ChMask" in mac_command and mac_command["ChMask"] == "1111111100000000":
                        check_channel = False
            else:
                for mac_command in packet["json"]["MAC Commands"]:
                    if "ChMask" in mac_command and mac_command["ChMask"] == "0000000100000000":
                        check_channel = True
                    if "ChMask" in mac_command and mac_command["ChMask"] == "1111111100000000":
                        check_channel = False
        if packet["json"]["MType"] in ["010", "100"]:
            if bw == 125:
                if check_channel and packet["freq"] not in [902.3, 902.5, 902.7, 902.9]:
                    suc0 = False
            else:
                if check_channel and packet["freq"] not in [903]:
                    suc0 = False
    
    suc1 = verify_ack(packets, "ChMask", "Channel mask ACK")
    html, result = generate_passed_table([("Update channels", suc0, suc0), 
                                          ("Ack all channel mask requesets", suc1, suc1)])
                                          
    html1, result1 = veryfy_downlink_with_mac(packets, response)                                      
    html = html + html1 + "<hr>"
    return html, 2*int(result)-1
    

def verify_mac_mask_125(packets, response):
    return verify_mac_mask(packets, response, 125)
    
    
def verify_mac_mask_500(packets, response):
    return verify_mac_mask(packets, response, 500)
    
    
def verify_mac_tx_power(packets, response):
    suc1 = verify_ack(packets, "TXPower", "Power ACK")
    
    html, result = generate_passed_table([("Ack all TXPower requesets", suc1, suc1)])
    
    current_power = -1
    data = {}
    for packet in packets:
        if packet["json"]["MType"] in ["010", "100"]:
            if current_power >= 0:
                if current_power not in data:
                    data[current_power] = []
                data[current_power].append(packet["rssi"])
        if packet["json"]["MType"] in ["011", "101"]:
            for mac_command in packet["json"]["MAC Commands"]:
                if "TXPower" in mac_command:
                    current_power = mac_command["TXPower"]
    x = []
    y = []

    for tx_power in sorted(data.keys()):
        if data[tx_power]:
            x.append(tx_power)
            y.append(np.mean(data[tx_power]))
            
    fig = plt.figure(figsize=(8.5, 3))
    ax = fig.add_subplot(111)
    ax.plot(x, y, "-o")
    ax.grid()
    ax.set_xlabel("tx_power")
    ax.set_ylabel("Average rssi")

    plt.tight_layout()
    html += mpld3.fig_to_html(fig)
    plt.close(fig)
   
    html = html + "<hr>"
    
    return html, 2*int(result)-1
    
    
def verify_mac_dr(packets, response):
    suc1 = verify_ack(packets, "DataRate", "Data rate ACK")
    
    check_dr = False
    
    current_dr = -1
    data = {}
    for packet in packets:
        if packet["json"]["MType"] in ["010", "100"]:
            if current_dr >= 0:
                if current_dr not in data:
                    data[current_dr] = []
                data[current_dr].append(datrLUT[packet["json"]["region"]]["up"][packet["datr"]])
        if packet["json"]["MType"] in ["011", "101"]:
            for mac_command in packet["json"]["MAC Commands"]:
                if "DataRate" in mac_command:
                    current_dr = mac_command["DataRate"]
    
    suc0 = True
    for dr in data.keys():
        if data[dr]:
            if np.mean(data[dr]) != dr:
                suc0 = False
    
    html, result = generate_passed_table([("Update daterate", suc0, suc0), 
                                          ("Ack all daterate requesets", suc1, suc1)])
    html += "<hr>"                                      
    return html, 2*int(result)-1
    
    
def verify_mac_redundancy(packets, response):
    check_redundancy = False
    
    current_redundancy = -1
    data = {}
    for packet in packets:
        if packet["json"]["MType"] in ["010", "100"]:
            if current_redundancy >= 0:
                if current_redundancy not in data:
                    data[current_redundancy] = {}
                if packet["json"]["FCnt"] not in data[current_redundancy]:
                    data[current_redundancy][packet["json"]["FCnt"]] = 0
                data[current_redundancy][packet["json"]["FCnt"]] += 1
        if packet["json"]["MType"] in ["011", "101"]:
            for mac_command in packet["json"]["MAC Commands"]:
                if "NbTrans" in mac_command:
                    current_redundancy = mac_command["NbTrans"]
    
    if 0 in data and 3 in data:
        suc0 = True
        for FCnt in data[0]:
            if data[0][FCnt] > 1:
                suc0 = False
 
        suc1 = True
        for FCnt in sorted(data[3].keys(), reverse = True)[1:]:
            if data[3][FCnt] < 3:
                suc1 = False
    else:
        suc0 = False
        suc1 = False
            
    html, result = generate_passed_table([("Update to redundancy 3", suc1, suc1), 
                                          ("Update to no redundancy", suc0, suc0)])
    html += "<hr>"
    return html, 2*int(result)-1


def verify_mac_payload(packets, response):
    suc1 = verify_ack(packets, "DevStatusReq", "DevStatusAns")
    html, result = generate_passed_table([("Respond to DevStatusReq", suc1, suc1)])
    html += "<hr>"
    return html, 2*int(result)-1

    
def verify_mac_status(packets, response):
    suc1 = verify_ack(packets, "DevStatusReq", "Battery")
    html, result = generate_passed_table([("Respond to DevStatusReq", suc1, suc1)])
    html += "<hr>"
    return html, 2*int(result)-1