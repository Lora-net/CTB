#file      web_result.py

#brief      web interface functions configuration

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

import matplotlib
import sqlite3
import json
import mpld3
import time
import operator
import os
import lzma
import threading

import ext_verification
import numpy as np
import matplotlib.pyplot as plt
from flask import Blueprint, send_file
from lib_base import datrLUT, DB_FILE_BACKUP, DB_FILE_CONTROLLER, DB_FILE_PM, reverse_eui, CACHE_FOLDER, deduplication_threshold
from lib_db import backup_db_proxy, backup_db_pm
from datetime import datetime

matplotlib.use('Agg')
result_api = Blueprint('result_api', __name__)


def get_all_packets(response):
    cached = False
    if response["UpdateTime"]:
        fileName = CACHE_FOLDER + "/" + response["DevEui"] + "_" + str(response["UpdateTime"]) + "_" + "all_packets" + ".html_xz"
        if os.path.exists(fileName):
            cached = True
        else:
            needs_cache = True

    if not cached:
        conn = sqlite3.connect(DB_FILE_BACKUP, timeout=60)
        conn.row_factory = sqlite3.Row
        
        if not response["FinishTime"]:
            response["FinishTime"] = time.time()
        
        max_time = conn.execute("SELECT MAX(time) FROM packet").fetchone()["MAX(time)"]
        
        if not max_time:
            backup_db_proxy()
        else:
            if max_time < response["FinishTime"]:
                backup_db_proxy()
                
        dev_addrs = conn.execute('SELECT DevAddr FROM session WHERE DevEui=(?) and DevAddr is not null',
                                 (response["DevEui"],)).fetchall()
        dev_addrs = [item["DevAddr"] for item in dev_addrs]
    
        if response["StartTime"]:
            packets_conn = conn.execute('SELECT * FROM packet WHERE time > (?) AND time < (?) ORDER BY time',
                                        (response["StartTime"] - 0.01, response["FinishTime"] + 0.01)).fetchall()
        else:
            packets_conn = []
    
        packets = []
        
        last_up_time = 0
        for packet in packets_conn:
            pkt = dict(packet)
            if pkt["json"]:
                pkt["json"] = json.loads(pkt["json"])
            if pkt["test"]:
                pkt["test"] = json.loads(pkt["test"])
    
            if "error" in pkt["json"]:
                if pkt["json"]["MType"] in ["000"]:
                    if pkt["json"]["DevEui"] == response["DevEui"]:
                        packets.append(pkt)
                else:
                    if "DevAddr" in pkt["json"]:
                        if pkt["json"]["DevAddr"] in dev_addrs:
                            packets.append(pkt)
            else:
                if pkt["json"]["DevEui"] == response["DevEui"] and pkt["direction"] == "up":
                    if "Cat" in response and response["Cat"].lower() == "rf":  # RF testbench needs test information returned for validation
                        if pkt["stat"] == 1:  # dedup happens already, single stat==1 packet can be generated
                            packets.append(pkt)
                    else:
                        if pkt["time"] - last_up_time > deduplication_threshold and pkt["stat"] == 0:
                            packets.append(pkt)
                    last_up_time = pkt["time"]
    
                if pkt["stat"] == 1 and pkt["json"]["DevEui"] == response["DevEui"] and pkt["direction"] == "down":
                    packets.append(pkt)
        
        packets.sort(key=operator.itemgetter("time"))
        
        conn.close()
        
        if response["UpdateTime"]:
            with lzma.open(fileName, "w") as f:
                f.write(json.dumps(packets).encode())
    else:
        with lzma.open(fileName, "r") as f:
            packets = json.loads(f.read().decode())
      
    return packets


def generate_error_log(packets, response):
    cached = False
    if response["UpdateTime"]:
        fileName = CACHE_FOLDER + "/" + response["DevEui"] + "_" + str(response["UpdateTime"]) + "_" + "error_packets" + ".html_xz"
        if os.path.exists(fileName):
            cached = True

    if not cached:
        packets_valid = []
        html = "<font size='5'>Packets Summary</font><br>"
    
        for pkt in packets:
            if "error" in pkt["json"]:
                html += json.dumps(pkt, indent=8, sort_keys=True).replace("\n", "<br>").replace(' ', '&nbsp;') + "<br>"
            else:
                packets_valid.append(pkt)
    
        if not packets_valid:
            html += "No Error Packets <br>"
    
        cnt = {"up": 0,
               "down": 0}
    
        for packet in packets_valid:
            cnt[packet["direction"]] += 1
        for direction in ["up", "down"]:
            html += "Valid " + direction + " Packets: %d <br>" % cnt[direction]
        html += "<hr>"
        
        if response["UpdateTime"]:
            with lzma.open(fileName, "w") as f:
                f.write(json.dumps({"html": html, "packets": packets_valid}).encode())
    else:
        with lzma.open(fileName, "r") as f:
            data = json.loads(f.read().decode())
        html = data["html"]
        packets_valid = data["packets"]
        
    return html, packets_valid


@result_api.route('/result', methods=['GET', 'POST'])
def list_tests():
    conn = sqlite3.connect(DB_FILE_CONTROLLER, timeout=60)
    conn.row_factory = sqlite3.Row

    responses = conn.execute('SELECT rowid,* FROM schedule').fetchall()

    all_sequence = []
    for response in responses:
        all_sequence.append(dict(response))
        all_sequence = sorted(all_sequence, key=lambda k: k['AddTime'], reverse=False)

    html = '<html><table border="1"><tr>'
    for key in ["DevEui", "Cat", "SubCat", "Criteria", "Parameter", "CurrentPara", "Config", "StartTime",
                "FinishTime", "rowid", "Passed", "Report Ready"]:
        html += "<th>" + key + "</th>"
    html += "</tr>"
    
    #response["Passed"] None: ongoing, 1: passed, -1: failed, -2: not run, -3: not implemented, -4: packet MIC error
    
    for response in all_sequence:
        if (response["FinishTime"] and not response["Passed"]):
            packets = get_all_packets(response)
            _, packets_valid = generate_error_log(packets, response)
            if len(packets_valid) == len(packets):
                try:
                    _, suc = eval("ext_verification.verify_" + response["Cat"] + "_" + response["SubCat"] + "(packets, response)")
                    print("Verify", response["Cat"] + "_" + response["SubCat"])
                except AttributeError:
                    suc = -3
            else:
                suc = -4
                
            response["Passed"] = suc
            conn.execute("UPDATE schedule SET Passed=(?) WHERE rowid=(?)", (response["Passed"], response["rowid"]))
            conn.commit()
    
    for response in all_sequence:
        html += "<tr>"
        for key in ["DevEui", "Cat", "SubCat", "Criteria", "Parameter", "CurrentPara", "Config", 
                    "StartTime", "FinishTime", "rowid", "Passed", "Ready"]:
            if key == "rowid":
                html += "<td><a href='/result/testid=%d'>%d</a><br></td>" % (response[key], response[key])
                continue
            
            if key == "DevEui":
                html += "<td>{}</td>".format(reverse_eui(response[key]).upper())
                continue
            
            if key == "Passed":
                lut = {1: "<font color='green'>Passed</font>", 
                      -1: "<font color='red'>Failed</font>", 
                      -2: "<font color='black'>Not Tested</font>", 
                      -3: "<font color='black'>Not Implemented</font>", 
                      -4: "<font color='red'>Packet MIC Error</font>", 
                      None: ""}
                response[key] = lut[response[key]]
            
            if key == "StartTime":
                if not response[key]:
                    response[key] = "Pending Start"
                else:
                    response[key] = str(datetime.fromtimestamp(response[key]))[:-7]
            if key == "FinishTime":
                if not response[key]:
                    response[key] = "Not Finished"
                else:
                    response[key] = str(datetime.fromtimestamp(response[key]))[:-7]
            if key == "Ready":
                if response[key] == 0:
                    response[key] = " "
                if response[key] == 1:
                    response[key] = "Generating"
                if response[key] == 2:
                    response[key] = "Ready"
            html += "<td>{}</td>".format(str(response[key]))
        html += "</tr>"
    html += "</table></html>"
    
    conn.commit()
    conn.close()
    
    return html


def generate_general_fig(packets, key):
    x = []
    y = []

    html = "<br>"

    previous_para = -1

    for packet in packets:
        if key not in ["MType", "ACK", "datr"]:
            if packet["direction"] == "up":
                if key in ["rssi", "lsnr", "freq", "size", "toa"]:
                    x.append(datetime.fromtimestamp(packet["time"]))
                    y.append(packet[key])
                if key in ["time_diff"]:
                    if previous_para >= 0:
                        x.append(datetime.fromtimestamp(packet["time"]))
                        y.append(packet[key[:-5]] - previous_para)
                    previous_para = packet[key[:-5]]
                    continue
                if key in ["FCnt", "FPort", "FRMPayload_length", "FCnt_diff"] and packet["json"]["MType"] in ["010",
                                                                                                              "100"]:
                    if key in ["FCnt_diff"]:
                        if previous_para >= 0:
                            x.append(datetime.fromtimestamp(packet["time"]))
                            y.append(packet["json"][key[:-5]] - previous_para)
                        previous_para = packet["json"][key[:-5]]
                        continue
                    if key == "FRMPayload_length":
                        x.append(datetime.fromtimestamp(packet["time"]))
                        y.append(len(packet["json"]["FRMPayload"]) / 2)
                        continue
                    if key in packet["json"]:
                        x.append(datetime.fromtimestamp(packet["time"]))
                        y.append(float(packet["json"][key]))
        else:
            if key in ["datr"]:
                x.append(datetime.fromtimestamp(packet["time"]))
                if packet["direction"] == "up":
                    y.append(datrLUT[packet["json"]["region"]]["up"][packet[key]])
                else:
                    y.append(datrLUT[packet["json"]["region"]]["down"][packet[key]])
            if key in ["MType"]:
                x.append(datetime.fromtimestamp(packet["time"]))
                y.append(int(packet["json"]["MType"], 2))
            if key in ["ACK"]:
                if packet["json"]["MType"] in ["101"]:
                    x.append(datetime.fromtimestamp(packet["time"]))
                    y.append(-1)
                if packet["json"]["MType"] in ["010", "100"]:
                    x.append(datetime.fromtimestamp(packet["time"]))
                    y.append(int(packet["json"]["ACK"]))

    if y:
        if key in ["rssi", "lsnr", "freq", "datr", "time_diff", "FRMPayload_length", "size", "toa"]:
            html += "Mean: %.2f<br>" % np.mean(y)
            html += "Min: %.2f<br>" % np.min(y)
            html += "Max: %.2f<br>" % np.max(y)
    
        if key in ["FCnt"]:
            html += "Frame Lost: %d<br>" % (np.max(y) - np.min(y) + 1 - len(y))
            html += "FER: %.3f%%<br>" % ((1 - len(y) / (np.max(y) - np.min(y) + 1)) * 100)
    
        if key in ["toa"]:
            html += "Total TOA: %f Seconds<br>" % np.sum(y)
            html += "Duty cycle: %f%%<br>" % (np.sum(y) / (packets[-1]["time"] - packets[0]["time"]) * 100)

        fig = plt.figure(figsize=(8.5, 3))
        ax = fig.add_subplot(111)
        ax.plot(x, y, ".")
        ax.grid()
        ax.set_xlabel("time")
        ax.set_ylabel(key)
    
        plt.tight_layout()
        html += mpld3.fig_to_html(fig)
        plt.close(fig)
    
        if key in ["rssi", "lsnr", "freq", "FPort", "datr", "time_diff", "FCnt_diff",
                   "FRMPayload_length", "size", "MType", "ACK"]:
            fig = plt.figure(figsize=(8.5, 3))
            ax = fig.add_subplot(121)
            ax.hist(y, bins=128)
            ax.grid()
            ax.set_title("Histogram")
            ax.set_xlabel(key)
    
            ax = fig.add_subplot(122)
            ax.plot(sorted(y), np.arange(0, 1 - 1e-8, 1 / len(y)))
            ax.grid()
            ax.set_title("CDF")
            ax.set_xlabel(key)
            ax.set_ylabel("Probability")
    
            plt.tight_layout()
            html += mpld3.fig_to_html(fig)
            plt.close(fig)
    
            if key not in ["time_diff", "lsnr"]:
                y_dist = sorted(list(set(y)))
                for item in y_dist:
                    html += "%.1f: %d <br>" % (item, y.count(item))

    html += "<hr>"
    return html


def generate_frmpayload(packets):
    html = ""

    if packets:
        html = '<html><table border="1"><tr>'
        for key in ["Time", "Direction", "FPort", "FRMPayload"]:
            html += "<th>" + key + "</th>"
        html += "</tr>"

        for packet in packets:
            if "FPort" not in packet["json"]:
                continue

            html += "<tr>"
            
            html += "<td>{}</td>".format(str(datetime.fromtimestamp(packet["time"]))[:-5])
            html += "<td>{}</td>".format(packet["direction"])
            for key in ["FPort", "FRMPayload"]:
                if key in ["time", "direction"]:
                    html += "<td>{}</td>".format(str(packet[key]))
                    continue
                
                html += "<td>{}</td>".format(str(packet["json"][key]))
            html += "</tr>"
        html += "</table></html>"

    html += "<hr>"
    return html


def generate_correlation_fig(packets, key, category_key):
    html = key + "<br>"
    html += category_key + "<br><br>"

    data = {}
    for packet in packets:
        if packet["direction"] == "up":
            if packet[category_key] not in data:
                data[packet[category_key]] = []
            data[packet[category_key]].append(packet[key])

    fig = plt.figure(figsize=(8.5, 3))
    ax = fig.add_subplot(111)

    for x in sorted(data.keys()):
        ax.plot([x, x], [np.percentile(data[x], 10), np.percentile(data[x], 90)], "b")
        ax.plot(x, np.mean(data[x]), "ok")
    ax.grid()

    plt.tight_layout()
    html += mpld3.fig_to_html(fig)
    plt.close(fig)

    html += "<hr>"

    return html


def generate_network_delay_fig(response):
    html = ""

    conn = sqlite3.connect(DB_FILE_BACKUP, timeout=60)
    conn.row_factory = sqlite3.Row
    if not response["FinishTime"]:
        response["FinishTime"] = time.time()

    fig1 = plt.figure(figsize=(8.5, 3))
    ax1 = fig1.add_subplot(111)

    fig2 = plt.figure(figsize=(8.5, 3))
    ax2 = fig2.add_subplot(111)

    
    for dst in ["ns", "gw", "tc"]:
        delays = conn.execute('SELECT time_ack-time_gen, time_ack FROM delay WHERE time_ack > (?) \
        AND time_ack < (?) and dst=(?) ORDER BY time_ack',
                              (response["StartTime"] - 0.1, response["FinishTime"] - 0.1, dst)).fetchall()
        x = []
        y = []
        for delay in delays:
            x.append(datetime.fromtimestamp(delay["time_ack"]))
            y.append(delay["time_ack-time_gen"])
        
        if len(x) > 1000:
            interval = int(len(x)/1000)
            x = x[::interval]
            y = y[::interval]
        
        if y:
            ax1.plot(x, y, ".", label=dst)
            ax2.plot(sorted(y), np.arange(0, 1 - 1e-8, 1 / len(y)), label=dst)

    ax1.legend()
    ax2.legend()

    ax1.grid()
    plt.tight_layout()
    html += mpld3.fig_to_html(fig1)
    plt.close(fig1)

    ax2.grid()
    plt.tight_layout()
    plt.legend()
    html += mpld3.fig_to_html(fig2)
    plt.close(fig2)

    html += "<hr>"
    return html


def generate_title(response):
    cached = False
    if response["UpdateTime"]:
        fileName = CACHE_FOLDER + "/" + response["DevEui"] + "_" + str(response["UpdateTime"]) + "_" + "title" + ".html_xz"
        if os.path.exists(fileName):
            cached = True

    if not cached:
        html = ""
        for key in ["DevEui", "Cat", "SubCat", "Criteria", "Parameter", "CurrentPara",
                    "Config", "AddTime", "StartTime", "FinishTime"]:
            if key.find("Time") >= 0 and response[key]:
                html += key + ":" + str(datetime.fromtimestamp(response[key])) + "<br>"
            else:
                html += key + ":" + str(response[key]) + "<br>"
        if response["FinishTime"]:
            html += "Duration: %f" % (response["FinishTime"] - response["StartTime"])
        html += "<hr>"
        
        if response["FinishTime"]:
            with lzma.open(fileName, "w") as f:
                f.write(html.encode())
    else:
        with lzma.open(fileName, "r") as f:
            html = f.read().decode()
    return html


def generate_detail_log(packets):
    html = ""
    for pkt in packets:
        html += json.dumps(pkt, indent=8, sort_keys=True).replace(' ', '&nbsp;').replace("\n", "<br>") + "<br>"
    html += "<hr>"
    return html


def generate_mac_trace(packets):
    html = '<html><table border="1"><tr>'
    for key in ["Time", "MType", "ACK", "FCnt", "MAC Commands"]:
        html += "<th>" + key + "</th>"

    for packet in packets:
        if packet["json"]["MType"] in ["010", "100", "011", "101"]:
            html += "<tr>"
            html += "<td>" + str(datetime.fromtimestamp(packet["time"]))[:-5] + "</td>"
            html += "<td>" + packet["json"]["MType"] + "</td>"
            html += "<td>" + packet["json"]["ACK"] + "</td>"
            html += "<td>" + "%d" % packet["json"]["FCnt"] + "</td>"
            if packet["json"]["MAC Commands"]:
                html += "<td>" + json.dumps(packet["json"]["MAC Commands"]) + "</td>"
            else:
                html += "<td></td>"
            html += "</tr>"

    html += "</table></html>"
    html += "<hr>"
    return html


def generate_power(start, duration, detail = True):

    cached = False
    fileName = CACHE_FOLDER + "/" + "current_" + str(start) + "_" + str(duration) + "_" + str(detail) + ".html_xz"
    if os.path.exists(fileName):
        cached = True
    else:
        cached = False

    if not cached:
    
        start = float(start)
        duration = float(duration)
        
        if detail and duration > 120:
            return "Duration too long for high sampling rate current profile"
        
        html = ""
        
        conn = sqlite3.connect(DB_FILE_PM, timeout=60)
        conn.row_factory = sqlite3.Row
        
        if conn.execute('SELECT max(time) FROM power').fetchone()["max(time)"]:
            if float(conn.execute('SELECT max(time) FROM power').fetchone()["max(time)"]) <= start + duration + 1:
                backup_db_pm()
        else:
            backup_db_pm()
        
        if detail:
            currents = conn.execute('SELECT time, value FROM power WHERE duration = 1 AND time >= (?) '
                                    'AND time < (?) ORDER BY time',
                                     (start-1, start+duration+1)).fetchall()
        else:
            if duration > 86400:
                currents = conn.execute('SELECT time, average, max FROM power WHERE duration = 60 '
                                        'AND time >= (?) AND time < (?) ORDER BY time',
                                         (start-1, start+duration+1)).fetchall()
            else:
                currents = conn.execute('SELECT time, average, max FROM power WHERE duration = 1 '
                                        'AND time >= (?) AND time < (?) ORDER BY time',
                                         (start-1, start+duration+1)).fetchall()
        
        x = []
        y = []
        y1 = []
        
        for current in currents:
            if detail:
                l_y = [int.from_bytes(current["value"][i:i+4], byteorder='little', signed = True)/1000000.0
                       for i in range(0, len(current["value"]), 4)]
                l_x = np.linspace(current["time"], current["time"]+1, len(l_y))
                
                x += list(l_x)
                y += list(l_y)
            else:
                x.append(current["time"])
                y.append(current["average"]/1000000)
                y1.append(current["max"]/1000000)
        
        plot_x = []
        plot_y = []
        plot_y1 = []
        if detail:
            for i in range(len(x)):
                if start <= x[i] <= start+duration:
                    plot_x.append(datetime.fromtimestamp(x[i]))
                    plot_y.append(y[i])
            y1 = plot_y
        else:
            for i in range(len(x)):
                if start <= x[i] <= start+duration:
                    plot_x.append(datetime.fromtimestamp(x[i]))
                    plot_y.append(y[i])
                    plot_y1.append(y1[i])
        
        print(len(plot_x))
        
        backup_x = plot_x.copy()
        backup_y = plot_y.copy()
        backup_y1 = plot_y1.copy()
        
            
        if not plot_x:
            return "No Data <br>"
        
        fig = plt.figure(figsize=(8.5, 3))
        ax = fig.add_subplot(111)
        ax.plot(plot_x, plot_y)
        
        if not detail:
            ax.plot(plot_x, plot_y1)
            
        conn.close()
        
        ax.grid()
        ax.set_xlabel("time")
        ax.set_ylabel("current")
    
        plt.tight_layout()
        html += mpld3.fig_to_html(fig)
        plt.close(fig)
        
        
        fig = plt.figure(figsize=(8.5, 3))
        ax = fig.add_subplot(121)
        ax.hist(plot_y, bins=32)
        ax.grid()
        ax.set_title("Histogram")
        ax.set_xlabel("current")
    
        ax = fig.add_subplot(122)
        ax.plot(sorted(plot_y), np.linspace(0, 1, len(plot_y)))
        if not detail:
            ax.plot(sorted(plot_y1), np.linspace(0, 1, len(plot_y1)))
        else:
            backup_y1 = backup_y
            
        ax.grid()
        ax.set_title("CDF")
        ax.set_xlabel("current")
        ax.set_ylabel("Probability")
    
        plt.tight_layout()
        html += mpld3.fig_to_html(fig)
        plt.close(fig)
        
        html += "Average Current: %f mA<br>" % np.mean(backup_y)
        html += "Peak Current: %f mA<br>" % np.max(backup_y1)
        print(np.mean(backup_y)*(np.max(backup_x)-np.min(backup_x)))
        html += "Power Consumption: %f mAh<br>" % (np.mean(backup_y)*(np.max(x)-np.min(x))/3600.0)
        
        with lzma.open(fileName, "w") as f:
            f.write(html.encode())
    else:
        with lzma.open(fileName, "r") as f:
            html = f.read().decode()
        
    return html


def generate_current(response, packets):
    html = ""

    conn = sqlite3.connect(DB_FILE_PM, timeout=60)
    conn.row_factory = sqlite3.Row
    
    if not response["FinishTime"]:
        response["FinishTime"] = time.time()
        
    html += generate_power(response["StartTime"] - 10, response["FinishTime"] - response["StartTime"] + 10, False)
    
    html += "<br>"

    html += '<html><table border="1"><tr>'
    for key in ["MType", "datr", "Time", "Average", "Peak"]:
        html += "<th>" + key + "</th>"
    html += "</tr>"
    
    for packet in packets:
        html += "<tr>"
        html += "<td>{}</td>".format(packet["json"]["MType"])
        html += "<td>{}</td>".format(packet["datr"])
        
        if packet["direction"] == "up":
            html += "<td><a href='/current/1/%f+%f'>%s</a></td>" % \
                    (packet["time"]-5, 15, str(datetime.fromtimestamp(packet["time"]))[:-5])
            
            avg = conn.execute('SELECT AVG(average) FROM power WHERE duration=1 AND time > (?) AND time < (?)',
                               (packet["time"]-5, packet["time"]+10)).fetchone()["AVG(average)"]
            if avg:
                html += "<td>%.4f</td>" % (avg/1e6)
            else:
                html += "<td></td>"
            
            peak = conn.execute('SELECT MAX(max) FROM power WHERE duration=1 AND time > (?) AND time < (?)',
                                (packet["time"]-5, packet["time"]+10)).fetchone()["MAX(max)"]
            if peak:
                html += "<td>%.2f</td>" % (peak/1e6)
            else:
                html += "<td></td>"
        else:
            html += "<td>%s</td>" % str(datetime.fromtimestamp(packet["time"]))[:-5]
            html += "<td></td><td></td>"
        
        html += "</tr>"
        
    conn.close()
        
    html += "</table></html>"
    
    html += "<hr>"
            
    return html


def plot_items(packets, items, response):

    html_total = ""
    for item in items.split("+"):
    
        cached = False
        if response and response["UpdateTime"] and item != "current":
            fileName = CACHE_FOLDER + "/" + response["DevEui"] + "_" + str(response["UpdateTime"]) + "_" + item + ".html_xz"
            if os.path.exists(fileName):
                cached = True
        else:
            cached = False
        
        if not cached:
            if not packets:
                html = "No valid packets <hr>"
            else:
                html = ""
                html += "<font size='5'>" + item + "</font><br>"
                if item == "verification" and response:
                    try:
                        html_local, suc = eval("ext_verification.verify_" + response["Cat"] + "_" + response["SubCat"] + "(packets, response)")
                        html += html_local
                    except AttributeError:
                        html += "Verification function not implemented <br><hr>"
                if item.find("-") >= 0:
                    keywords = item.split("-")
                    html += generate_correlation_fig(packets, keywords[0], keywords[1])
                if item == "log":
                    html += generate_detail_log(packets)
                if item == "delay":
                    html += generate_network_delay_fig(response)
                if item == "mac":
                    html += generate_mac_trace(packets)
                if item == "current":
                    html += generate_current(response, packets)
                if item == "FRMPayload":
                    html += generate_frmpayload(packets)
                if item in ["rssi", "lsnr", "freq", "size", "datr", "toa", "FCnt", "ACK", "FPort", "FRMPayload_length",
                            "time_diff", "FCnt_diff", "MType"]:
                    html += generate_general_fig(packets, item)
                if item == "print":
                    html += """
                            <script type="text/javascript">
                            <!--
                            window.print();
                            //-->
                            </script>
                            """
            if response and response["UpdateTime"] and item != "current":
                with lzma.open(fileName, "w") as f:
                    f.write(html.encode())
        else:
            with lzma.open(fileName, "r") as f:
                html = f.read().decode()
        html_total += html
    return html_total


def generate_cache(response):
    
    conn = sqlite3.connect(DB_FILE_CONTROLLER, timeout=60)
    conn.row_factory = sqlite3.Row
    conn.execute('UPDATE schedule SET Ready = 1 WHERE rowid=(?)', (response["rowid"],))
    conn.commit()
    

    
    html = generate_title(response)
    packets = get_all_packets(response)
    html_error, packets = generate_error_log(packets, response)

    '''
    items = ""
    for item in ["verification", "rssi", "lsnr", "freq", "size", "datr", "toa", "FCnt", "ACK", "FPort", "FRMPayload_length", "time_diff", "FCnt_diff", "MType", 
                 "current", "log", "delay", "mac", "FRMPayload", "rssi-freq", "lsnr-freq"]:
        plot_items(packets, item, response)
    '''    
    conn = sqlite3.connect(DB_FILE_CONTROLLER, timeout=60)
    conn.row_factory = sqlite3.Row
    conn.execute('UPDATE schedule SET Ready = 2 WHERE rowid=(?)', (response["rowid"],))
    conn.commit()


@result_api.route('/result/testid=<rowid>/<items>', methods=['GET', 'POST'])
def open_result(rowid, items):
    conn = sqlite3.connect(DB_FILE_CONTROLLER, timeout=60)
    conn.row_factory = sqlite3.Row
    response = conn.execute('SELECT * FROM schedule WHERE rowid=(?)', (rowid,)).fetchone()
    conn.close()
    
    if not response:
        return "Test ID not found"
    response = dict(response)
        
    if items == "cache":
        generate_cache(response)
        html = "Cache finished"
    else:
            
        html = generate_title(response)
        
        packets = get_all_packets(response)
        html_error, packets = generate_error_log(packets, response)
        html += html_error
        
        html += plot_items(packets, items, response)
    
    return html


@result_api.route('/result/testid=<rowid>', methods=['GET', 'POST'])
def open_result_brief(rowid):
    conn = sqlite3.connect(DB_FILE_CONTROLLER, timeout=60)
    conn.row_factory = sqlite3.Row
    response = conn.execute('SELECT * FROM schedule WHERE rowid=(?)', (rowid,)).fetchone()
    conn.close()
    
    if not response:
        return "Test ID not found"
    response = dict(response)

    html = generate_title(response)
    packets = get_all_packets(response)
    html_error, packets = generate_error_log(packets, response)
    
    html += plot_items(packets, "verification", response)
    
    html += "<font size='5'>More Information</font><br>"
    lut = {"PHY Parameters": ["rssi", "lsnr", "freq", "size", "datr", "toa", "log"], 
           "MAC Parameters": ["MType", "FCnt", "ACK", "FPort", "FRMPayload_length", "FRMPayload", "mac"], 
           "Power Consumption": ["current"], 
           "Parameters between Packets": ["time_diff", "FCnt_diff"], 
           "Testbed Operation": ["delay", "cache"]}
    
    for key in ["PHY Parameters", "MAC Parameters", "Power Consumption", "Parameters between Packets", "Testbed Operation"]:
        html += "<br><font size='4'>"+key+"</font><br>"
        for item in lut[key]:
            html += "<a href='/result/testid=%d/%s'>%s</a><br>" % (int(rowid), item, item)
        
    return html


@result_api.route('/current/<detail>/<startTime>+<duration>', methods=['GET', 'POST'])
def open_current_time(startTime, duration, detail):
    startTime = float(startTime)
    duration = float(duration)
    detail = int(detail)
    
    if startTime > time.time():
        return "Start time too late."
    if startTime + duration > time.time():
        duration = time.time() - startTime
    return generate_power(startTime, duration, detail)
    
    
@result_api.route('/current/<detail>/last/<duration>', methods=['GET', 'POST'])
def open_current_last(duration, detail):
    duration = float(duration)
    detail = int(detail)
    return generate_power(time.time()-duration, duration, detail)


@result_api.route('/packet/device/<DevEui>/<startTime>+<duration>/<items>', methods=['GET', 'POST'])
def open_packet_device(DevEui, startTime, duration, items):
    response = {"DevEui": reverse_eui(DevEui).lower(),
                "StartTime": float(startTime),
                "FinishTime": float(startTime) + float(duration), 
                "UpdateTime": 0}
    
    packets = get_all_packets(response)
    html, packets = generate_error_log(packets, response)
    html += plot_items(packets, items, None)
    return html


@result_api.route('/packet/last/<count>/<items>', methods=['GET', 'POST'])
def open_packet_last(count, items):
        
    backup_db_proxy()
    
    conn = sqlite3.connect(DB_FILE_BACKUP, timeout=60)
    conn.row_factory = sqlite3.Row

    packets_conn = conn.execute('SELECT rowid,* FROM packet ORDER BY time DESC LIMIT (?)', (count, )).fetchall()
    
    packets = []
    for packet in packets_conn:
        pkt = dict(packet)
        if pkt["json"]:
            pkt["json"] = json.loads(pkt["json"])
        if pkt["test"]:
            pkt["test"] = json.loads(pkt["test"])
        
        packets.append(pkt)
    
    html = plot_items(packets, items, None)
    return html


@result_api.route('/log', methods=['GET', 'POST'])
def get_log():
    text = open(os.path.join("log", "ctb.log"), "r").read()
    html = text.replace(' ', '&nbsp;&nbsp;').replace("\n", "<br>")
    return html