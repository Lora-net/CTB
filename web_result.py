#file      web_result.py

#brief      web interface functions configuration

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

import matplotlib
import sqlite3
import json
import mpld3
import time
import operator
import os
import lzma
import threading
import sys
import base64
import numpy as np
import matplotlib.pyplot as plt
from flask import Blueprint, send_file, request, redirect, url_for
from lib_base import datrLUT, DB_FILE_BACKUP, DB_FILE_CONTROLLER, CACHE_FOLDER, \
    deduplication_threshold, config, TEST_STATE, CACHE_STATE
from lib_db import backup_db_proxy, backup_db_tc, delete_records, calc_db_pm
from datetime import datetime, timedelta
from importlib import import_module

sys.path.append("./pytest_dir")

matplotlib.use('Agg')
result_api = Blueprint('result_api', __name__)


def generate_table(result):
    html = '<html><table border="1"><tr>'
    for key in result['keys']:
        html += "<th>" + key + "</th>"
    html += "</tr>"

    for row in result['rows']:
        for e in row:
            html += "<td>{}</td>".format(e)
        html += "</tr>"

    html += "</table></html>"

    return html


def generate_passed_table(result):
    html = '<html><table border="1"><tr>'
    for key in ["Criteria", "Result", "Passed"]:
        html += "<th>" + key + "</th>"
    html += "</tr>"

    for i in range(len(result)):
        html += "<td>{}</td>".format(result[i][0])
        html += "<td>{}</td>".format(result[i][1])
        html += "<td>{}</td>".format(result[i][2])
        html += "</tr>"

    html += "</table></html>"

    return html


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
            backup_db_tc()
            backup_db_proxy()
        else:
            if max_time < response["FinishTime"]:
                backup_db_tc()
                backup_db_proxy()
                
        dev_addrs = conn.execute('SELECT DevAddr FROM session WHERE TestInstID=(?) and DevAddr is not null',
                                 (response["TestInstID"],)).fetchall()
        dev_addrs = [item["DevAddr"] for item in dev_addrs]

        packets_conn = conn.execute('SELECT * FROM packet WHERE TestInstID=(?) ORDER BY time',
                                        (response["TestInstID"],)).fetchall()
        conn.close()

        packets = []
        
        last_up_time = 0
        for packet in packets_conn:
            pkt = dict(packet)
            if pkt["json"]:
                pkt["json"] = json.loads(pkt["json"])
    
            if "error" in pkt["json"]:
                if pkt["json"]["MType"] in ["000"]:
                    if pkt["json"]["DevEui"] == response["DevEui"]:
                        packets.append(pkt)
                else:
                    if "DevAddr" in pkt["json"]:
                        if pkt["json"]["DevAddr"] in dev_addrs:
                            packets.append(pkt)
            else:
                if pkt["direction"] == "up":
                    if "Cat" in response and response["Cat"].lower() == "rf":  # RF testbench needs test information returned for validation
                        if pkt["stat"] == 1:  # dedup happens already, single stat==1 packet can be generated
                            packets.append(pkt)
                    else:
                        if pkt["time"] - last_up_time > deduplication_threshold and pkt["stat"] == 0:
                            packets.append(pkt)
                    last_up_time = pkt["time"]

                if pkt["stat"] == 1 and pkt["direction"] == "down":
                    packets.append(pkt)
        
        packets.sort(key=operator.itemgetter("time"))
        

        
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


def update_latest_result(inst):
    if inst['Passed'] == TEST_STATE['RUNNING']:
        conn = sqlite3.connect(DB_FILE_CONTROLLER, timeout=60)
        conn.row_factory = sqlite3.Row
        response = conn.execute('SELECT UpdateTime, CurrentPara FROM testInstance WHERE StartTime=(?)',
                                 (inst['StartTime'],)).fetchone()
        conn.close()
        if response:
            for key in ['UpdateTime', 'CurrentPara']:
                inst[key] = response[key]


@result_api.route('/result', methods=['GET', 'POST'])
def list_tests():
    all_sequence = get_test_result()

    html = '<html><table border="1"><script src="https://kit.fontawesome.com/a076d05399.js"></script><tr>'
    for key in ["rowid", "DevEui", "BenchID", "Cat", "SubCat", "Criteria", "Parameter", "CurrentPara", "Config", "StartTime",
                "FinishTime", "Passed", "Report Ready", "Comments", "Operator", "Delete"]:
        html += "<th>" + key + "</th>"
    html += "</tr>"
    
    for response in all_sequence:
        html += "<tr>"
        for key in ["TestInstID", "DevEui", "BenchID", "Cat", "SubCat", "Criteria", "Parameter", "CurrentPara", "Config",
                    "StartTime", "FinishTime", "Passed", "Ready", "Comments", "Operator"]:
            if key == "TestInstID":
                html += "<td><a href='/result/testid=%d'>%d</a><br></td>" % (response[key], response[key])
                continue
            
            if key == "DevEui":
                html += "<td>{}</td>".format(response[key].upper())
                continue
            
            if key == "Passed":
                lut = {TEST_STATE['PASSED']: "<font color='green'>Passed</font>",
                       TEST_STATE['FAILED']: "<font color='red'>Failed</font>",
                       TEST_STATE['RUNNING']: "<font color='black'>Running</font>",
                       TEST_STATE['ABORTED']: "<font color='orange'>Aborted</font>",
                       TEST_STATE['OBSERVATION']: "<font color='lime'>Observation</font>",
                       TEST_STATE['NA']: "<font color='black'>N/A</font>",
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
                if response[key] == CACHE_STATE['NONE']:
                    response[key] = " "
                if response[key] == CACHE_STATE['GENERATING']:
                    response[key] = "Generating"
                if response[key] == CACHE_STATE['READY']:
                    response[key] = "Ready"
            html += "<td>{}</td>".format(str(response[key]))
        html += '<td align="center"><a href = "/result/delete?rowid={}" ><i class="fas fa-trash-alt"></a></td>'.format(
                response["TestInstID"])
        html += "</tr>"
    html += "</table></html>"

    return html

@result_api.route('/result/delete', methods=['GET'])
def device_delete_row():
    if 'rowid' in request.args:
        rowid = int(request.args['rowid'])
    else:
        return "Error: No rowid specified."
    try:
        conn = sqlite3.connect(DB_FILE_BACKUP, timeout=60)
        conn.row_factory = sqlite3.Row
        delete_records(conn, "testInstance", 'rowid', [{"rowid": rowid}])
        conn.commit()
        conn.close()
        return redirect(request.referrer)
    except:
        conn.close()
        return "error device-delete"

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

@result_api.route('/comments/edit', methods=['POST'])
def edit_tests():
    if request.method == 'POST':
        result = request.form.to_dict(flat=True)
        conn = None
        try:
            conn = sqlite3.connect(DB_FILE_BACKUP, timeout=60)
            conn.row_factory = sqlite3.Row
            conn.execute("UPDATE testInstance SET Comments=(?), Operator=(?) WHERE rowid=(?)",
                         (result['comments'], result['operator'], int(result['rowid'])))
            conn.commit()
            conn.close()
            fileName = CACHE_FOLDER + "/" + result["DevEui"] + "_" + str(result["UpdateTime"]) + "_" + "title" + ".html_xz"
            if os.path.exists(fileName):
                print("cache filename is {}".format(fileName))
                os.remove(fileName)
            cached = True
            return redirect(request.referrer)
        except:
            if conn:
                conn.close()
            return "editting comments/operator error!"

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
            html += "Duration: {}".format(timedelta(seconds=(response["FinishTime"] - response["StartTime"])))
        html += '<form action="/comments/edit" method="post">'
        html += '<input type="hidden" id="rowid" name="rowid" value="{}">'.format(response['TestInstID'])
        html += '<input type="hidden" id="DevEui" name="DevEui" value="{}">'.format(response['DevEui'])
        html += '<input type="hidden" id="UpdateTime" name="UpdateTime" value="{}">'.format(response['UpdateTime'])
        html += '<label for="comments">Comments:</label><br>'
        html += '<textarea disabled="true", cols="80", rows="5", id="comments" name="comments">{}</textarea>'.format(response['Comments'])
        html += '<br>'
        html += '<label for="operator">Operator:</label><br>'
        html += '<input disabled="true" type="text" size=20 id="operator" name="operator" value="{}">'.format(response['Operator'])
        html += '<input id="submitbtn" disabled="disabled" name="Submit" type="submit" value="Submit" />'
        html += '</form>'
        html += '<button onclick="myFunction()">Edit</button>'
        html += """<script>
        function myFunction() {
        document.getElementById("comments").disabled=false;
        document.getElementById("operator").disabled=false;
        document.getElementById("submitbtn").disabled=false;
        }
        </script>"""
        html += "<hr>"

        if response["Passed"] == TEST_STATE['RUNNING']:
            html += "Test is running. Time elapsed {}<br>".format(timedelta(seconds=(time.time() - response["StartTime"])))
        elif response["Passed"] == TEST_STATE['PASSED']:
            html += "Test passed<br>"
        elif response["Passed"] == TEST_STATE['FAILED']:
            html += "Test failed, {}<br>".format(response["ErrorMsg"])
        elif response["Passed"] == TEST_STATE['ABORTED']:
            html += "Test aborted<br>"
        elif response["Passed"] == TEST_STATE['OBSERVATION']:
            html += "Test was in observation mode due to lack of information from questionnaire<br>"
        elif response["Passed"] == TEST_STATE['NA']:
            html += "Test not applicable<br>"
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


def generate_power(start, duration, detail = True, test_instid=None):
    cached = False
    if test_instid is not None:
        fileName = CACHE_FOLDER + "/" + "current_" + str(test_instid) + "_" +str(start) + "_" + str(duration) + "_" + str(detail) + ".html_xz"
    else:
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
        
        conn = sqlite3.connect(DB_FILE_BACKUP, timeout=60)
        conn.row_factory = sqlite3.Row

        if detail:
            if test_instid is None:
                currents = conn.execute('SELECT time, value FROM power WHERE duration = 1 AND time >= (?) '
                                    'AND time < (?) ORDER BY time',
                                     (start-1, start+duration+1)).fetchall()
            else:
                currents = conn.execute('SELECT time, value FROM power WHERE TestInstID=(?) AND '
                                        'duration = 1 AND time >= (?) AND time < (?) ORDER BY time',
                                        (test_instid, start-1, start+duration+1)).fetchall()
        else:
            if test_instid is None:
                currents = conn.execute('SELECT time, average, max FROM power WHERE duration = (?) '
                                        'AND time >= (?) AND time < (?) ORDER BY time',
                                         (60 if duration > 86400 else 1,
                                          start-1, start+duration+1)).fetchall()
            else:
                currents = conn.execute('SELECT time, average, max FROM power WHERE TestInstID=(?) AND '
                                        'duration = (?) AND time >= (?) AND time < (?) ORDER BY time',
                                         (test_instid, 60 if duration > 86400 else 1,
                                          start-1, start+duration+1)).fetchall()
        conn.close()

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

    if not response["FinishTime"]:
        response["FinishTime"] = time.time()
        
    html += generate_power(response["StartTime"] - 10,
                           response["FinishTime"] - response["StartTime"] + 10,
                           False, response['TestInstID'])
    
    html += "<br>"

    html += '<html><table border="1"><tr>'
    for key in ["MType", "datr", "Time", "Average", "Peak"]:
        html += "<th>" + key + "</th>"
    html += "</tr>"

    conn = sqlite3.connect(DB_FILE_BACKUP, timeout=60)
    conn.row_factory = sqlite3.Row
    for packet in packets:
        html += "<tr>"
        html += "<td>{}</td>".format(packet["json"]["MType"])
        html += "<td>{}</td>".format(packet["datr"])
        
        if packet["direction"] == "up":
            html += "<td><a href='/current/testid=%d/1/%f+%f'>%s</a></td>" % \
                    (response['TestInstID'], packet["time"]-5, 15,
                     str(datetime.fromtimestamp(packet["time"]))[:-5])
            
            avg = conn.execute('SELECT AVG(average) FROM power WHERE TestInstID=(?) AND '
                               'duration=1 AND time > (?) AND time < (?)',
                               (response['TestInstID'], packet["time"]-5,
                                packet["time"]+10)).fetchone()["AVG(average)"]
            if avg:
                html += "<td>%.4f</td>" % (avg/1e6)
            else:
                html += "<td></td>"
            
            peak = conn.execute('SELECT MAX(max) FROM power WHERE TestInstID=(?) AND '
                                'duration=1 AND time > (?) AND time < (?)',
                                (response['TestInstID'], packet["time"]-5,
                                 packet["time"]+10)).fetchone()["MAX(max)"]
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


def del_cache(item, response):
    if response and response["UpdateTime"] and item != "current":
        fileName = os.path.join(os.path.dirname(__file__), CACHE_FOLDER,
                                response["DevEui"] + "_" + str(response["UpdateTime"]) + "_" + item + ".html_xz")
        if os.path.exists(fileName):
            os.remove(fileName)

def generate_verification(response):
    html = ""
    if response and response['VerificationMsg']:
        response['VerificationMsg'] = json.loads(response['VerificationMsg'])
        if "verification" in response['VerificationMsg']:
            html += generate_passed_table(response['VerificationMsg']['verification'])
        if "details" in response['VerificationMsg']:
            html += "<br>Details<br>"
            html += generate_table(response['VerificationMsg']['details'])
        if response['Picture']:
            html += "<br>Picture<br>"
            html += '<img alt="Product Photo" src="data:image/jpg;base64,{}" style="width:300px;">'.format(base64.b64encode(response['Picture']).decode('utf-8'))

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
                if item == "verification" and response and response['Cat'] == "manual":
                    html = "<font size='5'>" + item + "</font><br>"
                    html += generate_verification(response)
            else:
                html = "<font size='5'>" + item + "</font><br>"
                if item == "verification":
                    html += generate_verification(response)
                if item.find("-") >= 0:
                    keywords = item.split("-")
                    html += generate_correlation_fig(packets, keywords[0], keywords[1])
                if item == "log":
                    html += generate_detail_log(packets)
                if item == "delay":
                    html += generate_network_delay_fig(response)
                if item == "mac":
                    html += generate_mac_trace(packets)
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
            if item == "current":
                html += generate_current(response, packets)

            if response and response["UpdateTime"] and item != "current":
                with lzma.open(fileName, "w") as f:
                    f.write(html.encode())
        else:
            with lzma.open(fileName, "r") as f:
                html = f.read().decode()
        html_total += html
    return html_total


def generate_cache(response):
    html = generate_title(response)
    packets = get_all_packets(response)
    html_error, packets = generate_error_log(packets, response)

    '''
    items = ""
    for item in ["verification", "rssi", "lsnr", "freq", "size", "datr", "toa", "FCnt", "ACK", "FPort", "FRMPayload_length", "time_diff", "FCnt_diff", "MType", 
                 "current", "log", "delay", "mac", "FRMPayload", "rssi-freq", "lsnr-freq"]:
        plot_items(packets, item, response)
    '''    
    conn = sqlite3.connect(DB_FILE_BACKUP, timeout=60)
    conn.row_factory = sqlite3.Row
    conn.execute('UPDATE testInstance SET Ready = 2 WHERE rowid=(?)', (response["rowid"],))
    conn.commit()
    conn.close()


def get_test_result(rowid=None):
    conn = sqlite3.connect(DB_FILE_BACKUP, timeout=60)
    conn.row_factory = sqlite3.Row
    if not rowid:
        responses = conn.execute('SELECT * FROM testInstance').fetchall()
    else:
        responses = conn.execute('SELECT * FROM testInstance WHERE rowid=(?)', (rowid,)).fetchall()
    latest_instid = conn.execute('SELECT MAX(testInstID) FROM testInstance WHERE BenchID=(?)',
                                 (config['gateway_id'],)).fetchone()["MAX(testInstID)"]
    conn.close()

    sequences = []
    for response in responses:
        inst = dict(response)
        if inst['TestInstID'] == latest_instid:
            update_latest_result(inst)
        sequences.append(inst)

    return sequences


@result_api.route('/result/testid=<rowid>/<items>', methods=['GET', 'POST'])
def open_result(rowid, items):
    response = get_test_result(rowid)

    if not response:
        return "Test ID not found"
    response = response[0]
    if items == "cache":
        response["rowid"] = rowid
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
    response = get_test_result(rowid)

    if not response:
        return "Test ID not found"
    response = response[0]
    html = generate_title(response)
    packets = get_all_packets(response)
    html_error, packets = generate_error_log(packets, response)
    
    html += plot_items(packets, "verification", response)

    if response['Cat'] == 'manual':
        return html

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


def open_current(startTime, duration, detail, test_instid=None):
    startTime = float(startTime)
    duration = float(duration)
    detail = int(detail)
    if test_instid is not None:
        test_instid = int(test_instid)

    if startTime > time.time():
        return "Start time too late."
    if startTime + duration > time.time():
        duration = time.time() - startTime
    return generate_power(startTime, duration, detail, test_instid)

@result_api.route('/current/calculation/testid=<rowid>', methods=['GET', 'POST'])
def calculate_current_per_min(rowid):
    calc_db_pm(rowid)
    return "OK"

@result_api.route('/current/<detail>/<startTime>+<duration>', methods=['GET', 'POST'])
def open_current_time(startTime, duration, detail):
    return open_current(startTime, duration, detail)

@result_api.route('/current/testid=<test_instid>/<detail>/<startTime>+<duration>', methods=['GET', 'POST'])
def open_current_time_with_instid(startTime, duration, detail, test_instid):
    return open_current(startTime, duration, detail, test_instid)


@result_api.route('/current/<detail>/last/<duration>', methods=['GET', 'POST'])
def open_current_last(duration, detail):
    duration = float(duration)
    detail = int(detail)
    return generate_power(time.time()-duration, duration, detail)


@result_api.route('/packet/device/<DevEui>/<startTime>+<duration>/<items>', methods=['GET', 'POST'])
def open_packet_device(DevEui, startTime, duration, items):
    response = {"DevEui": DevEui.lower(),
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

        packets.append(pkt)
    
    html = plot_items(packets, items, None)
    return html


@result_api.route('/log', methods=['GET', 'POST'])
def get_log():
    text = open(os.path.join("log", "ctb.log"), "r").read()
    html = text.replace(' ', '&nbsp;&nbsp;').replace("\n", "<br>")
    return html
