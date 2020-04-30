#file      web_config.py

#brief      API calls configuration

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

import RPi.GPIO as GPIO
import sqlite3, json, time, os
from flask import request, Blueprint
from datetime import datetime
from gpiozero import LED
import shutil
from lib_base import DB_FILE_CONTROLLER, DB_FILE_PROXY, DB_FILE_BACKUP, DB_FILE_PM, reverse_eui, CACHE_FOLDER
from lib_db import backup_db_proxy, backup_db_proxy, backup_db_tc, backup_db_pm


config_api = Blueprint('config_api', __name__)


@config_api.route('/device', methods=['GET', 'POST', 'DELETE'])
def configure_device():
    if request.method == 'POST':
        try:
            devices = json.loads(request.data.decode())
            conn = sqlite3.connect(DB_FILE_PROXY, timeout=60)
            conn.row_factory = sqlite3.Row

            for device in devices:
                conn.execute('INSERT OR REPLACE INTO device (DevEui, AppKey, NwkKey, region) VALUES (?,?,?,?)',
                             (reverse_eui(device["DevEui"]), device["AppKey"], device["NwkKey"], device["region"]))
            conn.commit()
            conn.close()
            return "ok"
        except Exception as e:
            return request.data.decode() + "<br>" + str(e)
    if request.method == 'GET':
        conn = sqlite3.connect(DB_FILE_PROXY, timeout=60)
        conn.row_factory = sqlite3.Row
        responses = conn.execute("SELECT rowid,* FROM device").fetchall()
        conn.close()

        all_devices = []
        for response in responses:
            all_devices.append(dict(response))

        html = """<html><table border="1">
            <tr><th>DevEui</th><th>AppKey</th><th>NwkKey</th><th>Region</th><th>Rowid</th></tr>"""
        for response in all_devices:
            html += "<tr>"
            for key in ["DevEui", "AppKey", "NwkKey", "region", "rowid"]:
                if key == "DevEui":
                    html += "<td>{}</td>".format(reverse_eui(response[key]).upper())
                else:
                    html += "<td>{}</td>".format(response[key])
            html += "</tr>"
        html += "</table></html>"
        return html
    if request.method == 'DELETE':
        try:
            conn = sqlite3.connect(DB_FILE_PROXY, timeout=60)
            conn.row_factory = sqlite3.Row

            if request.data.decode() == "all":
                conn.execute('DELETE FROM device')
                conn.commit()
            else:
                rows = json.loads(request.data.decode())

                for row in rows:
                    conn.execute('DELETE FROM device WHERE rowid=(?)', (row["rowid"], ))
                    conn.commit()
            conn.close()
            return "ok"
        except:
            conn.close()
            return "error"


@config_api.route('/sequence', methods=['GET', 'POST', 'DELETE'])
def configure_schedule():
    if request.method == 'POST':
        try:
            schedules = json.loads(request.data.decode())
            conn = sqlite3.connect(DB_FILE_CONTROLLER, timeout=60)
            conn.row_factory = sqlite3.Row

            for schedule in schedules:
                if "Config" not in schedule:
                    schedule["Config"] = {}
                schedule["Config"] = json.dumps(schedule["Config"])

                conn.execute('INSERT OR REPLACE INTO schedule (DevEui, Cat, SubCat, Criteria, Parameter, \
                CurrentPara, Config, AddTime, Ready) VALUES (?,?,?,?,?,?,?,?,?)',
                             (reverse_eui(schedule["DevEui"]), schedule["Cat"], schedule["SubCat"],
                              schedule["Criteria"], schedule["Parameter"], 0, schedule["Config"], time.time(), 0))
            conn.commit()
            conn.close()
            
            return "ok"
        except:
            return "error"
    if request.method == 'GET':
        return "<a href='/result' target='_blank'>All sequences and results</a>"
        
    if request.method == 'DELETE':
        try:
            conn = sqlite3.connect(DB_FILE_CONTROLLER, timeout=60)
            conn.row_factory = sqlite3.Row
            if request.data.decode() == "all":
                conn.execute('DELETE FROM schedule')
                conn.commit()
            else:
                rows = json.loads(request.data.decode())

                for row in rows:
                    if "rowid" in row:
                        conn.execute('DELETE FROM schedule WHERE rowid=(?)', (row["rowid"], ))
                        conn.commit()
                    if "Cat" in row and "SubCat" not in row:
                        conn.execute('DELETE FROM schedule WHERE Cat=(?)', (row["Cat"], ))
                        conn.commit()
                    if "Cat" in row and "SubCat" in row:
                        conn.execute('DELETE FROM schedule WHERE Cat=(?) and SubCat=(?)', (row["Cat"], row["SubCat"]))
                        conn.commit()
            conn.close()
            return "ok"
        except:
            conn.close()
            return "error"


@config_api.route('/status', methods=['GET'])
def status_check():
    backup_db_proxy()

    try:
        conn = sqlite3.connect(DB_FILE_BACKUP, timeout=60)
        conn.row_factory = sqlite3.Row

        html = ""

        response = conn.execute("SELECT time FROM packet WHERE direction='up' ORDER BY time DESC LIMIT 1").fetchone()
        if response:
            html += "Last up packet %f seconds ago <br>" % (time.time() - response["time"])
        else:
            html += "No uplink packets <br>"

        response = conn.execute("SELECT time FROM packet WHERE direction='down' ORDER BY time DESC LIMIT 1").fetchone()
        if response:
            html += "Last down packet %f seconds ago <br>" % (time.time() - response["time"])
        else:
            html += "No downlink packets <br>"
        conn.close()
        return html
    except:
        return "error"


@config_api.route('/session', methods=['GET', 'POST', 'DELETE'])
def configure_session():
    if request.method == 'POST':
        try:
            sessions = json.loads(request.data.decode())
            conn = sqlite3.connect(DB_FILE_PROXY, timeout=60)
            conn.row_factory = sqlite3.Row

            for session in sessions:

                packet = {}

                packet['AppSKey'] = session['AppSKey']
                packet['FNwkSIntKey'] = session['NwkSKey']
                packet['SNwkSIntKey'] = session['NwkSKey']
                packet['NwkSEncKey'] = session['NwkSKey']
                packet['JoinNonce'] = ""
                packet['Home_NetID'] = ""
                packet['DevAddr'] = session['DevAddr']
                packet['RxDelay'] = 1
                packet['OptNeg'] = "0"
                packet['RX1DRoffset'] = 0
                packet['RX2DataRate'] = 7
                
            
                conn.execute('INSERT OR REPLACE INTO session (FCntUp,NFCntDown,AFCntDown,AppSKey,FNwkSIntKey,'
                             'SNwkSIntKey,NwkSEncKey,JoinNonce,Home_NetID,DevAddr,RxDelay,'
                             'OptNeg,RX1DRoffset,RX2DataRate, RX2Freq) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                             (0, 0, 0, packet['AppSKey'], packet['FNwkSIntKey'], packet['SNwkSIntKey'], packet['NwkSEncKey'],
                              packet['JoinNonce'], packet['Home_NetID'],
                              packet['DevAddr'], packet['RxDelay'], packet['OptNeg'], packet['RX1DRoffset'],
                              packet['RX2DataRate'], 923.3))
            conn.commit()
            conn.close()
            
            return "ok"
        except:
            return "error"
        
    
        return "POST method not supported"
    if request.method == 'GET':
        conn = sqlite3.connect(DB_FILE_PROXY, timeout=60)
        conn.row_factory = sqlite3.Row

        responses = conn.execute('SELECT rowid,* FROM session').fetchall()

        all_session = []
        for response in responses:
            all_session.append(dict(response))
            all_session = sorted(all_session, key=lambda k: k['time'])

        if not all_session:
            return "No session information available"

        keys = ["time", "DevEui", "JoinEUI", "Home_NetID", "region", "DevNonce", "JoinNonce", 
                "DevAddr", "AFCntDown", "FCntUp", "AppSKey", "rowid"]

        html = '<html><table border="1"><tr>'
        for key in keys:
            html += "<th>" + key + "</th>"
        html += "</tr>"

        for response in all_session:
            html += "<tr>"
            for key in keys:
                if key == "DevEui":
                    html += "<td>{}</td>".format(reverse_eui(response[key]).upper())
                    continue
                if key.find("Key") >= 0 or key in ["DevAddr", "DevNonce", "JoinNonce"]:
                    if response[key]:
                        html += "<td>{}</td>".format(response[key].upper())
                    else:
                        html += "<td>None</td>"
                    continue
                if key.find("time") >= 0 or key.find("Time") >= 0:
                    if not response[key]:
                        response[key] = "Ongoing"
                    else:
                        response[key] = str(datetime.fromtimestamp(response[key]))[:-7]
                html += "<td>{}</td>".format(str(response[key]))
            html += "</tr>"
        html += "</table></html>"

        return html
    if request.method == 'DELETE':
        conn = sqlite3.connect(DB_FILE_PROXY, timeout=60)
        conn.row_factory = sqlite3.Row

        conn.execute('DELETE FROM session')
        conn.commit()
        conn.close()
        
        return "ok"


@config_api.route('/backup', methods=['GET', 'POST', 'DELETE'])
def backup():
    backup_db_proxy()
    backup_db_tc()
    backup_db_pm()
    return "ok"

    
@config_api.route('/reboot', methods=['GET', 'POST', 'DELETE'])
def reboot_ask():
    backup()
    html = "Backup complete, rebooting will result loss of data for up to 2 minutes, continue?<br>"
    html += "<a href='/reboot/confirmed'>Yes</a><br>"
    return html


@config_api.route('/reboot/confirmed', methods=['GET', 'POST', 'DELETE'])
def reboot_confirmed():
    backup()
    os.system("sudo reboot now")
    
    
@config_api.route('/reset', methods=['GET', 'POST', 'DELETE'])
def reset_ask():
    html = "Resetting the testbench will loss ALL data, continue?<br>"
    html += "<a href='/reset/confirmed'>Confirmed</a><br>"
    return html
    
@config_api.route('/reset/confirmed', methods=['GET', 'POST', 'DELETE'])
def reset_confirmed():
    os.remove(DB_FILE_CONTROLLER)
    os.remove(DB_FILE_PROXY)
    os.remove(DB_FILE_BACKUP)
    os.remove(DB_FILE_PM)

    shutil.rmtree(CACHE_FOLDER)
    os.mkdir(CACHE_FOLDER)

    os.system("sudo systemctl restart testbench")

    
@config_api.route('/calibrate', methods=['GET', 'POST', 'DELETE'])
def recalibrate_ask():
    html = "Resetting the calibration? Befor that, please remove all load from the current sensing board<br>"
    html += "<a href='/calibrate/confirmed'>Confirmed</a><br>"
    return html
    
@config_api.route('/calibrate/confirmed', methods=['GET', 'POST', 'DELETE'])
def recalibrate_confirmed():
    os.remove("ads1256/calibration.txt")
    os.system("sudo systemctl restart testbench")

@config_api.route('/device/reboot', methods=['GET', 'POST', 'DELETE'])
def device_reset():
    ldo_enable = LED(26)
    ldo_enable.off()
    time.sleep(1)
    ldo_enable.on()
    return "ok"

@config_api.route('/remove_cache', methods=['GET', 'POST', 'DELETE'])
def remove_cache():
    backup_db_proxy()
    backup_db_pm()

    shutil.rmtree(CACHE_FOLDER)
    os.mkdir(CACHE_FOLDER)

    conn = sqlite3.connect(DB_FILE_CONTROLLER)
    conn.execute("UPDATE schedule SET Passed = null, Ready = 0")
    conn.commit()
    conn.close()

    backup_db_tc()

    return "ok"

@config_api.route('/device/powerdown', methods=['GET', 'POST', 'DELETE'])
def device_pwrdwn():
    GPIO.setmode(GPIO.BCM)
    pin = 26
    GPIO.setup(pin,GPIO.OUT)
    GPIO.output(pin,0)
    time.sleep(1)
    return "ok"
    
@config_api.route('/device/powerup', methods=['GET', 'POST', 'DELETE'])
def device_pwrup():
    GPIO.setmode(GPIO.BCM)
    pin = 26
    GPIO.setup(pin,GPIO.OUT)
    GPIO.output(pin,1)
    return "ok"

