# file      web_config.py

# brief      API calls configuration

# Revised BSD License


# Copyright Semtech Corporation 2021. All rights reserved.

# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
# Redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer.
# Redistributions in binary form must reproduce the above copyright
# notice, this list of conditions and the following disclaimer in the
# documentation and/or other materials provided with the distribution.
# Neither the name of the Semtech corporation nor the
# names of its contributors may be used to endorse or promote products
# derived from this software without specific prior written permission.


# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL SEMTECH CORPORATION. BE LIABLE FOR ANY DIRECT,
# INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import sqlite3, json, time, os, subprocess
from flask import request, Blueprint, redirect, url_for, send_file, render_template, jsonify
from datetime import datetime
import shutil
import socket
import sys
import logging
import urllib.parse
from base64 import b64encode

from lib_base import DB_FILE_CONTROLLER, DB_FILE_PROXY, DB_FILE_BACKUP, CACHE_FOLDER, \
    addr_pc, config_logger, PROC_MSG, device_on, CACHE_STATE, start_pcap
from lib_db import backup_db_proxy, backup_db_proxy, backup_db_tc, backup_db_pm, \
    TABLES, merge_db_backup, delete_records, insert_records, TABLE_SETS

config_api = Blueprint('config_api', __name__)

tcp_process = []

def parse_response(responses, table, has_link=False):
    if not responses:
        return ''

    records = []
    for response in responses:
        records.append(dict(response))

    keys = list(records[0].keys())
    if table in TABLE_SETS['blob_tables']:
        keys.remove(TABLE_SETS['blob_tables'][table])

    html = '<table border="1">'
    html += '<tr>' + ("<th>%s</th>" * len(keys)) % tuple(keys) + '</tr>'
    for record in records:
        html += "<tr>"
        for key in keys:
            if has_link and 'id' in key.lower() and key[0:-2].lower() in table.lower():
                html += "<td><a href='/table/{0}/id={1}'>{1}</a><br></td>".format(table, record[key])
            else:
                html += "<td>{}</td>".format(record[key])
        html += "</tr>"
    html += "</table>"
    return html




@config_api.route('/table/<table>', methods=['POST', 'GET', 'DELETE'])
def config_table(table):
    conn = None
    if request.method == 'POST':
        try:
            tables = json.loads(request.data.decode())
            logging.debug("tables are {}".format(tables))
            if table not in tables:
                return "error, no %s found!" % table

            conn = sqlite3.connect(DB_FILE_BACKUP, timeout=60)
            conn.row_factory = sqlite3.Row
            insert_records(conn, table, tables)
            conn.commit()
            conn.close()
            return "ok"
        except Exception as e:
            if conn:
                conn.close()
            return "error happened: {}".format(sys.exc_info()[1])
    if request.method == 'GET':
        if table not in TABLES:
            return "Table %s doesn't exist" % table
        conn = sqlite3.connect(DB_FILE_BACKUP, timeout=60)
        conn.row_factory = sqlite3.Row
        responses = conn.execute("SELECT * FROM %s" % table).fetchmany(1000)
        conn.close()

        if not responses:
            html = "<h1>%s table is empty</h1>" % table
        else:
            html = '<html><h1>%s Table</h1>' % table
            if 'has_link' in TABLES[table] and TABLES[table]['has_link']:
                html += parse_response(responses, table, True)
            else:
                html += parse_response(responses, table)
            html += '</html>'
        return html
    if request.method == 'DELETE':
        try:
            rows = json.loads(request.data.decode())
            if "rowids" in rows[0]:
                rowids = rows[0]['rowids']
                for rowid in rowids:
                    rows.append({'rowid': rowid})
                rows.pop(0)

            conn = sqlite3.connect(DB_FILE_BACKUP, timeout=60)
            conn.row_factory = sqlite3.Row
            delete_records(conn, table, 'rowid', rows)
            conn.commit()
            conn.close()
            return "ok"
        except:
            if conn:
                conn.close()
            return "error"


@config_api.route('/table/<table>/id=<rowid>', methods=['GET'])
def show_linked_tables(table, rowid):
    if table not in TABLES:
        return "Table %s doesn't exist" % table
    if 'has_link' not in TABLES[table] or not TABLES[table]['has_link']:
        return "Table %s doesn't have linked tables"

    responses = {}
    conn = sqlite3.connect(DB_FILE_BACKUP, timeout=60)
    conn.row_factory = sqlite3.Row
    for lk_table in TABLES[table]['linked_table']:
        responses[lk_table] = conn.execute('SELECT * FROM {} WHERE {}=(?)'.format(lk_table, TABLES[table]['primary_key']),
                                           (rowid,)).fetchmany(200)

    conn.close()

    html = '<html>'
    for lk_table in TABLES[table]['linked_table']:
        if not responses[lk_table]:
            html += '<h1> ' + lk_table + ' table is empty</h1>'
        else:
            html += '<html><h1>%s Table</h1>' % lk_table
            if 'has_link' in TABLES[lk_table] and TABLES[lk_table]['has_link']:
                html += parse_response(responses[lk_table], lk_table, True)
            else:
                html += parse_response(responses[lk_table], lk_table)
        html += '<br><br>'
    html += '</html>'

    return html


@config_api.route('/product', methods=['GET', 'POST'])
def update_product():
    conn = sqlite3.connect(DB_FILE_BACKUP, timeout=60)
    conn.row_factory = sqlite3.Row
    responses = conn.execute("SELECT p.ProductID, p.Name, v.CompanyName, p.Series, p.ProductJPG "
                             "FROM product AS p, vendor AS v WHERE p.VendorID=v.VendorID").fetchall()
    conn.close()

    products = []
    for response in responses:
        products.append(dict(response))

    html = """<html><h1>Product Table</h1><table border="1">
            <tr><th>ProductID</th><th>ProductName</th><th>CompanyName</th><th>Series</th><th>ProductJPG</th><th>Update</th></tr>"""
    for product in products:
        html += "<tr>"
        for key in ["ProductID", "Name", "CompanyName", "Series", "ProductJPG"]:
            if key == "ProductJPG":
                if product[key]:
                    html +='<td><img alt="Product Photo" src="data:image/jpg;base64,{}" style="width:100px;"></td>'.format(
                        b64encode(product[key]).decode('utf-8'))
                else:
                    html += "<td>None</td>"
            else:
                html += "<td>{}</td>".format(product[key])

        html += ('<td><form action="/upload_pic" method="post" enctype="multipart/form-data"> <input type="file" name="picture"/> '
                '<input type="hidden" name="rowid" value="{}"> <input type="submit"/> </form>').format(product["ProductID"])
        html += "</tr>"
    html += "</table>"
    return html

@config_api.route('/upload_pic', methods=['POST'])
def upload_product_picture():
    rowid = request.form.to_dict(flat=True)['rowid']
    picture = request.files['picture'].read()
    conn = None
    try:
        conn = sqlite3.connect(DB_FILE_BACKUP, timeout=60)
        conn.row_factory = sqlite3.Row
        conn.execute("UPDATE product SET ProductJPG=(?) WHERE rowid=(?)", (picture, rowid))
        conn.commit()
        conn.close()
        return redirect(request.referrer)
    except:
        if conn:
            conn.close()
        return "adding picture error!"

@config_api.route('/device', methods=['GET', 'POST', 'DELETE'])
def configure_device():
    if request.method == 'POST':
        try:
            devices = json.loads(request.data.decode())
            conn = sqlite3.connect(DB_FILE_BACKUP, timeout=60)
            conn.row_factory = sqlite3.Row

            for device in devices:
                conn.execute('INSERT OR REPLACE INTO device (DevEui, SkuID, AppKey, NwkKey) VALUES (?,?,?,?)',
                             (device["DevEui"].lower(), device["SkuID"], device["AppKey"], device["NwkKey"]))
            conn.commit()
            conn.close()
            return "ok"
        except Exception as e:
            return request.data.decode() + "<br>" + str(e)
    if request.method == 'GET':
        conn = sqlite3.connect(DB_FILE_BACKUP, timeout=60)
        conn.row_factory = sqlite3.Row
        responses = conn.execute("SELECT rowid,* FROM device").fetchall()
        skus = conn.execute("SELECT * FROM regionSKU").fetchall()
        conn.close()

        all_devices = []
        for response in responses:
            all_devices.append(dict(response))
        region_skus = []
        for sku in skus:
            region_skus.append(dict(sku))

        html = """<html><h1>Device Table</h1><script src='https://kit.fontawesome.com/a076d05399.js'></script><table border="1">
            <tr><th>DevEui (16)</th><th>AppKey (32)</th><th>NwkKey (32)</th><th>SkuID</th><th>Rowid</th><th>Delete</th></tr>"""
        for response in all_devices:
            html += "<tr>"
            for key in ["DevEui", "AppKey", "NwkKey", "SkuID", "rowid"]:
                if key == "DevEui":
                    html += "<td>{}</td>".format(response[key].upper())
                else:
                    html += "<td>{}</td>".format(response[key])
            # a trash icon is displayed in the last column for each row to allow you to delete that row
            # rowid is passed as an argument to the /device/delete URL
            html += """<td align="center"><a href = "/device/delete?rowid={}" > <i class='fas fa-trash-alt'> </a></td>""".format(
                response["rowid"])
            html += "</tr>"
        html += "</table>"
        # after the table of devices is rendered we have a form to allow you to add a device
        html += "<br><h2>Quickly add a new device:</h2>"
        html += """<form action="/device/add" method="post">"""
        html += """<label for="deveui">DevEUI:</label><br><input type="text" size=20 id="deveui" name="deveui" value="0123456789ABCDEF"><br>"""
        html += """<label for="appkey">AppKey:</label><br><input type="text" size=36 id="appkey" name="appkey" value="00000000000000000000000000000000"><br>"""
        html += """<label for="nwkkey">NwkKey:</label><br><input type="text" size=36 id="nwkkey" name="nwkkey" value="00000000000000000000000000000000"><br>"""
        html += """<p>Select the region SkuID:</p>"""
        html += '<select name="skuid" id="skuid">'
        for sku in region_skus:
            html += '<option value="' + str(sku['SkuID']) + '">SkuID:' + str(sku['SkuID']) + ', PartNumber:' + sku[
                'PartNumber'] + ', Region:' + sku['Region'] + '</option>'
        html += '</select><br><br>'
        html += """<input type = "submit" value="Add Device"></form>"""
        html += "</html>"
        return html
    if request.method == 'DELETE':
        try:
            conn = sqlite3.connect(DB_FILE_BACKUP, timeout=60)
            conn.row_factory = sqlite3.Row

            if request.data.decode() == "all":
                conn.execute('DELETE FROM device')
                conn.commit()
            else:
                rows = json.loads(request.data.decode())

                for row in rows:
                    conn.execute('DELETE FROM device WHERE rowid=(?)', (row["rowid"],))
                    conn.commit()
            conn.close()
            return "ok"
        except:
            conn.close()
            return "error"


# the ability to delete a row from the device table (the trash icon) is directed here
# the url must have the rowid ID set as an argument (done by the table rendering)
@config_api.route('/device/delete', methods=['GET'])
def device_delete_row():
    if 'rowid' in request.args:
        rowid = int(request.args['rowid'])
    else:
        return "Error: No rowid specified."
    try:
        conn = sqlite3.connect(DB_FILE_BACKUP, timeout=60)
        conn.row_factory = sqlite3.Row
        conn.execute('DELETE FROM device WHERE rowid=(?)', (rowid,))
        conn.commit()
        conn.close()
        return redirect(request.referrer)
    except:
        conn.close()
        return "error device-delete"


# the ability to quickly add a device is directed here by the form submit
@config_api.route('/device/add', methods=['POST'])
def device_add():
    try:
        conn = sqlite3.connect(DB_FILE_BACKUP, timeout=60)
        conn.row_factory = sqlite3.Row

        conn.execute('INSERT OR REPLACE INTO device (DevEui, AppKey, NwkKey, SkuID) VALUES (?,?,?,?)',
                     (request.form['deveui'].lower(), request.form['appkey'],
                      request.form['nwkkey'], request.form['skuid']))

        conn.commit()
        conn.close()
        return redirect(request.referrer)
    except:
        conn.close()
        return "error device-add"


@config_api.route('/sequence', methods=['GET', 'POST', 'DELETE'])
def configure_schedule():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(1)
    if request.method == 'POST':
        try:
            sock.sendto(bytes([PROC_MSG["WB_POST_SEQUENCE"]]) + request.data, addr_pc)
            msg, addr = sock.recvfrom(1024)
            return msg.decode("utf-8")
        except:
            logging.error("error happened: {}".format(sys.exc_info()[0]))
            return "error"
    elif request.method == 'GET':
        try:
            sock.sendto(bytes([PROC_MSG["WB_GET_SEQUENCE"]]), addr_pc)
            byte_data, addr = sock.recvfrom(10240)
            all_sequence = json.loads(byte_data.decode())
            logging.debug("all_sequence {}".format(all_sequence))
            html = ""
        except:
            html = '"Error: Sequence GET error"'
            html += '<br>'
            all_sequence = []

        html += '<html><table border="1"><tr>'
        for key in ["DevEui", "Cat", "SubCat", "Criteria", "Parameter", "Config",
                    "CurrentState", "AddTime", "StartTime", "rowid"]:
            html += "<th>" + key + "</th>"
        html += "</tr>"

        for idx, response in enumerate(all_sequence):
            html += "<tr>"
            response["rowid"] = idx
            response["DevEui"] = response["DevEui"].upper()
            if "StartTime" not in response:
                response["CurrentState"] = "Pending Start"
                response["StartTime"] = ""
            else:
                response["CurrentState"] = "Running"
                response["StartTime"] = str(datetime.fromtimestamp(response["StartTime"]))[:-7]
            response["AddTime"] = str(datetime.fromtimestamp(response["AddTime"]))[:-7]

            for key in ["DevEui", "Cat", "SubCat", "Criteria", "Parameter", "Config",
                        "CurrentState", "AddTime", "StartTime", "rowid"]:
                html += "<td>{}</td>".format(str(response[key]))
            html += "</tr>"
        html += "</table>"

        # after the table of scheduled tests is rendered we have a form to allow you to add a test
        html += "<br><h2>Quickly add a test:</h2>"
        html += """<form action="/sequence/add" method="post">"""
        html += """<label for="deveui">DevEUI:</label><br><input type="text" size=20 id="deveui" name="DevEui" value="0123456789ABCDEF"><br>"""
        html += """<label for="cat">Category:</label><br><input type="text" size=20 id="cat" name="Cat" value="manual"><br>"""
        html += """<label for="subcat">Sub-category:</label><br><input type="text" size=20 id="SubCat" name="SubCat" value="qrcode"><br>"""
        html += """<p>Select the test Criteria:</p>"""
        html += """<input type="radio" id="Count" name="Criteria" value="count" checked><label for="Count">Count</label><br>"""
        html += """<input type="radio" id="Time" name="Criteria" value="time"><label for="Time">Time</label><br><br>"""
        html += """<label for="parameter">Parameter:</label><br>"""
        html += """<input type="text" size=20 id="parameter" name="Parameter" value="4"><br>"""  # try a number for Parameter value?
        html += """<label for="config">Configuration: (JSON object)</label><br>"""
        html += """<input type="text" size=40 id="config" name="Config" value='{"a":2, "b":True}'><br><br>"""  # seem to need capital True
        html += """<input type = "submit" value="Add Test"></form>"""
        html += "</html>"
        return html

    elif request.method == 'DELETE':
        try:
            sock.sendto(bytes([PROC_MSG["WB_DEL_SEQUENCE"]]) + request.data, addr_pc)
            msg, addr = sock.recvfrom(1024)
            return msg.decode("utf-8")
        except:
            return "error"


# the ability to quickly add a test is directed here by the form submit
@config_api.route('/sequence/add', methods=['POST'])
def sequence_add():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(1)

    dict = request.form.to_dict(flat=True)
    if dict['Cat'] == "manual":
        return redirect(url_for("manual_test.test_manual_{}".format(dict['SubCat']), deveui=dict['DevEui']))
    dict['Parameter'] = int(dict['Parameter'])
    dict['Config'] = eval(dict['Config'])
    logging.debug(dict)

    try:
        sock.sendto(bytes([PROC_MSG['WB_POST_SEQUENCE']]) + ("[" + json.dumps(dict) + "]").encode(), addr_pc)
        msg, addr = sock.recvfrom(1024)
        tmp = msg.decode("utf-8")
        if tmp != "ok":
            return tmp
        else:
            time.sleep(1)  # need a sleep to avoid exception on the return page
            logging.debug("Adding sequence returning to {} with 303 return code".format(request.referrer))
            return redirect(request.referrer, 303)

    except:
        logging.error("sequence-add error happened:", sys.exc_info()[0])
        return "error sequence-add"


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
                             (0, 0, 0, packet['AppSKey'], packet['FNwkSIntKey'], packet['SNwkSIntKey'],
                              packet['NwkSEncKey'],
                              packet['JoinNonce'], packet['Home_NetID'],
                              packet['DevAddr'], packet['RxDelay'], packet['OptNeg'], packet['RX1DRoffset'],
                              packet['RX2DataRate'], 923.3))
            conn.commit()
            conn.close()

            return "ok"
        except:
            return "error"

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
                    html += "<td>{}</td>".format(response[key].upper())
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
    if request.method == 'POST':
        return redirect(request.referrer)
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

    shutil.rmtree(CACHE_FOLDER)
    os.mkdir(CACHE_FOLDER)

    os.system("sudo systemctl restart testbench")


@config_api.route('/calibrate', methods=['GET', 'POST', 'DELETE'])
def recalibrate_ask():
    html = "Resetting the calibration? Before that, please remove all load from the current sensing board<br>"
    html += "<a href='/calibrate/confirmed'>Confirmed</a><br>"
    return html


@config_api.route('/calibrate/confirmed', methods=['GET', 'POST', 'DELETE'])
def recalibrate_confirmed():
    os.remove("ads1256/calibration.txt")
    os.system("sudo systemctl restart testbench")


@config_api.route('/remove_cache', methods=['GET', 'POST', 'DELETE'])
def remove_cache():
    backup_db_proxy()
    backup_db_pm()

    shutil.rmtree(CACHE_FOLDER)
    os.mkdir(CACHE_FOLDER)

    conn = sqlite3.connect(DB_FILE_CONTROLLER)
    conn.execute("UPDATE testInstance SET Ready = %d" % CACHE_STATE['NONE'])
    conn.commit()
    conn.close()

    backup_db_tc()

    return "ok"


def device_on_with_checking(on=True):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(1)
    try:
        sock.sendto(bytes([PROC_MSG["WB_QUERY_TEST_STATE"]]) + request.data, addr_pc)
        msg, addr = sock.recvfrom(1024)
        if msg.decode("utf-8") == "Test is running":
            return "Test is running! You cannot power %s device!" % ("up" if on else "down")
    except:
        logging.error("error happened:", sys.exc_info()[0])
        pass
    device_on(on)

    return "ok"


@config_api.route('/device/powerdown', methods=['GET', 'POST', 'DELETE'])
def device_pwrdwn():
    msg = device_on_with_checking(False)
    if msg == "ok" and request.method == 'POST':
        return redirect(request.referrer)
    else:
        return msg


@config_api.route('/device/powerup', methods=['GET', 'POST', 'DELETE'])
def device_pwrup():
    msg = device_on_with_checking()
    if msg == "ok" and request.method == 'POST':
        return redirect(request.referrer)
    else:
        return msg


@config_api.route('/device/reboot', methods=['GET', 'POST', 'DELETE'])
def device_reset():
    msg = device_on_with_checking(False)
    if msg != "ok":
        return msg
    time.sleep(10)
    device_on()
    return "ok"


@config_api.route('/pcap/start', methods=['GET', 'POST', 'DELETE'])
def pcapstart():
    global tcp_process
    tcp_process = start_pcap()
    return "ok"


@config_api.route('/pcap/stop', methods=['GET', 'POST', 'DELETE'])
def pcapstop():
    global tcp_process
    tcp_process.terminate()
    os.system("sudo mv *.pcap pcap")
    return "ok"


@config_api.route('/upload', methods=['POST'])
def upload_file():
    if request.method == 'POST':
        f = request.files['file']
        f.save("db/db_backup2.db")
        try:
            merge_db_backup()
            return 'file has been uploaded and database merged successfully'
        except:
            return "error happened: {}".format(sys.exc_info()[1])


@config_api.route('/download', methods=['GET', 'POST'])
def download_file():
    logging.debug("downloading db file")
    return send_file("db/db_backup.db", as_attachment=True, cache_timeout=0)

"""
Report Generator Test Selection 

Works with rg_select.html template
"""

def get_dropdown_values():
    conn = sqlite3.connect(DB_FILE_BACKUP, timeout=60)
    conn.row_factory = sqlite3.Row

    all_vendors = conn.execute("SELECT VendorID,CompanyName FROM vendor").fetchall()
    all_products = []
    vendor_names = []
    for v in all_vendors:
        vendor_products = conn.execute("SELECT Name FROM product WHERE VendorID=(?)", (v['VendorID'],)).fetchall()
        prod_list = []
        for p in vendor_products:
            prod_list.append(p['Name'])
        all_products.append(prod_list)
        vendor_names.append(v['CompanyName'])
    conn.close()
    logging.debug("Dropdowns -- Vendors: {}, Products: {}".format(vendor_names, all_products))
    # build key,value pairs and dict
    zip_iterator = zip(vendor_names, all_products)
    vendor_entry_relations = dict(zip_iterator)
    return vendor_entry_relations


@config_api.route('/_update_dropdown')
def update_dropdown():
    # the value of the first dropdown (selected by the user)
    selected_vendor = request.args.get('selected_vendor', type=str)

    # get values for the second dropdown
    updated_values = get_dropdown_values()[selected_vendor]

    # create the values in the dropdown as a html string
    html_string_selected = ''
    for entry in updated_values:
        html_string_selected += '<option value="{0}">{0}</option>'.format(entry)

    return jsonify(html_string_selected=html_string_selected)


def get_test_list(selected_vendor, selected_product, selected_sku):
    conn = sqlite3.connect(DB_FILE_BACKUP, timeout=60)
    conn.row_factory = sqlite3.Row

    vendorID = conn.execute("SELECT VendorID FROM vendor WHERE CompanyName=(?)", (selected_vendor,)).fetchone()[0]
    productID = conn.execute("SELECT ProductID FROM product WHERE VendorID={} AND Name=(?)".format(vendorID),
                             (selected_product,)).fetchone()[0]
    skuID = conn.execute("SELECT SkuID FROM regionSKU WHERE ProductID={} AND Region=(?)".format(productID),
                         (selected_sku,)).fetchone()

    logging.debug("Test list query Vendor: {}, Product: {}, and SKU: {}".format(vendorID, productID, skuID))

    if skuID:
        devResponses = conn.execute("SELECT DevEui FROM device WHERE SkuID=(?)", (skuID[0],)).fetchall()
    else:
        devResponses = None

    dev_list = []
    if devResponses:
        for row in devResponses:
            dev_list.append(row['DevEui'])
    logging.debug("Dev list: {}".format(dev_list))
    if dev_list:
        devs = '(' + ', '.join(
            '"{0}"'.format(d) for d in dev_list) + ')'  # create a list of quoted strings for the query
        testList = conn.execute("SELECT * FROM testInstance WHERE DevEui IN " + devs).fetchall()
    else:
        testList = None
    conn.close()
    return (testList)


@config_api.route('/_process_data')
def process_data():
    selected_vendor = request.args.get('selected_vendor', type=str)
    selected_product = request.args.get('selected_product', type=str)
    selected_sku = request.args.get('selected_sku', type=str)

    # get all the test instances with the selected vendor, product and SKU
    testList = get_test_list(selected_vendor, selected_product, selected_sku)
    logging.debug("Got a testList: {}".format(testList))
    if (testList):
        results = []
        for ix in testList:
            result = dict(ix)
            if 'Picture' in result:
                del result['Picture']
            results.append(result)
        return (json.dumps(results))
    else:
        return (json.dumps([]))


#
#   Main entry for the report generator results selection
#
@config_api.route('/rg_select')
def rg_select():
    #   Initialize the dropdown menus
    vendor_entry_relations = get_dropdown_values()
    default_vendors = sorted(vendor_entry_relations.keys(), key=str.casefold)  # case-insensitive sort
    default_products = vendor_entry_relations[default_vendors[0]]
    default_skus = ['US', 'EU']
    #   Initial render with the defaults
    return render_template('rg_select.html',
                           all_vendors=default_vendors,
                           all_products=default_products,
                           all_skus=default_skus)

#
#   Start for generating a report...
#
@config_api.route('/_generate_report', methods=['GET'])
def generate_report():
    selected_vendor = request.args.get('selected_vendor', type=str)
    selected_product = request.args.get('selected_product', type=str)
    selected_sku = request.args.get('selected_sku', type=str)

    # manipulate the percent-encoded array argument from the query string
    #   into a python list of numeric strings

    str1 = urllib.parse.unquote(request.args.get('test_list', type=str))
    str2 = str1.replace(']','').replace('[','')
    str3 = str2.replace('"','').split(",")
    logging.debug("Array conversion for URL encoded string: {}, {}, {}, #entries: {}".format(str1, str2, str3,
                                                                                             len(str3)))
    # convert the list of numeric strings into a proper list of integers
    if str3[0] != '':     # check that we don't have an empty list
        testInstList = [int(numeric_string) for numeric_string in str3]
    else:
        testInstList = []
        return "No tests selected"
    #
    # Generate a report in the report table and redirect to display that table
    #
    logging.debug("Generating report table entry for TestInstIDs: {}".format(testInstList))

    # test jpg file as input blob
    #f = open('static/MIU-X.jpg', 'rb')
    #with f:
    #    fBytes = f.read()

    # create a new report in the report table... here we will store the summary comments
    try:
        conn = sqlite3.connect(DB_FILE_BACKUP, timeout=60)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        c.execute('INSERT OR REPLACE INTO report (VendorName, ProductName, RegionName, TestList, CreateTime, SummaryText) VALUES (?,?,?,?,?,?)',
                     (selected_vendor, selected_product,
                      selected_sku, str(testInstList), time.time(), "No comments, yet!"))
        conn.commit()

    except sqlite3.Error as er:
        print('SQLite error: %s' % (' '.join(er.args)))
        print("Exception class is: ", er.__class__)
        conn.close()
        return "error report-add"

    return(redirect("/report_mng"))  # redirect to the table view /report


#
# render a report
#
@config_api.route('/report', methods=['GET', 'POST'])
def display_report():
    rowid = request.args.get('reportid')
    if not rowid:
        return "error, reportid doesn't exist!"

    try:
        conn = sqlite3.connect(DB_FILE_BACKUP, timeout=60)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
    except sqlite3.Error as er:
        print('SQLite error: %s' % (' '.join(er.args)))
        print("Exception class is: ", er.__class__)
        conn.close()
        return "error report-render"

    # get all the data we need for display on the first page of the report

    reportRow = conn.execute("SELECT * FROM report WHERE ReportID={}".format(rowid)).fetchone()

    vendorRow = conn.execute("SELECT * FROM vendor WHERE CompanyName=(?)", (reportRow['VendorName'],)).fetchone()

    productRow = conn.execute("SELECT * FROM product WHERE VendorID={} AND Name=(?)".format(vendorRow['VendorID']),
                             (reportRow['ProductName'],)).fetchone()

    skuRow = conn.execute("SELECT * FROM regionSKU WHERE ProductID={} AND Region=(?)".format(productRow['ProductID']),
                         (reportRow['RegionName'],)).fetchone()

    contactRows = conn.execute("SELECT * FROM contact WHERE VendorID={}".format(vendorRow['VendorID'])).fetchall()

    testsTuple = '(' + str(reportRow['TestList'][1:-1]) + ')'
    logging.debug("Tuple of TestList: {}".format(testsTuple))
    testRows = conn.execute("SELECT * FROM testInstance WHERE TestInstID IN {}".format(testsTuple)).fetchall()

    powerSpecRow = conn.execute("SELECT * FROM powerSpec WHERE ProductID={}".format(productRow['ProductID'])).fetchone()

    upLinkRow = conn.execute("SELECT * FROM upLink WHERE ProductID={}".format(productRow['ProductID'])).fetchone()

    conn.close()

    createtime = str(datetime.fromtimestamp(reportRow['CreateTime']))[:-7]

    return render_template('report.html',
                           vendor=reportRow['VendorName'], product=reportRow['ProductName'], region=reportRow['RegionName'],
                           vendorRow=vendorRow, productRow=productRow, createtime=str(createtime),
                           prod_image=b64encode(productRow['ProductJPG']).decode("utf-8"),
                           skuRow=skuRow, contactRows=contactRows,
                           tests=reportRow['TestList'], testRows=testRows, reportRow=reportRow,
                           powerSpecRow=powerSpecRow, upLinkRow=upLinkRow)


@config_api.route('/merge', methods = ['GET','POST'])
def merge_file():
    try:
        merge_db_backup()
        return 'database has been merged successfully'
    except:
        return "merge error happened: {}".format(sys.exc_info()[1])

#
#   Action to update the SummaryText column of the report
#
@config_api.route('/_update_comments', methods=['POST'])
def update_report_comments():
    summarytext = request.form.get('summarytext')
    reportid = int(request.form.get('reportid'))

    try:
        conn = sqlite3.connect(DB_FILE_BACKUP, timeout=60)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        c.execute('UPDATE report SET SummaryText = (?) WHERE ReportID = (?)',(str(summarytext),
                     reportid))
        conn.commit()

    except sqlite3.Error as er:
        print('SQLite error: %s' % (' '.join(er.args)))
        print("Exception class is: ", er.__class__)
        conn.close()
        return "Error in updating SummaryText"

    conn.close()
    return "Summary text updated successfully"

#
#   /report page for managing the report table
#   redirected here by /_report_generator
#
@config_api.route('/report_mng', methods=['GET', 'DELETE']) # 'POST', removed.
def manage_reports():

    if request.method == 'GET':
        conn = sqlite3.connect(DB_FILE_BACKUP, timeout=60)
        conn.row_factory = sqlite3.Row
        responses = conn.execute("SELECT ReportID,* FROM report").fetchall()
        conn.close()

        all_reports = []
        for response in responses:
            all_reports.append(dict(response))

        html = """<html><h1>Report Table</h1><script src='https://kit.fontawesome.com/a076d05399.js'></script>
                  <table border="1"><tr><th>VendorName</th><th>ProductName</th><th>RegionName</th><th>TestList</th>
                  <th>CreateTime</th><th>SummaryText</th><th>ReportID</th><th>Delete</th></tr>"""
        for response in all_reports:
            html += "<tr>"
            style = 'padding: 5px 10px 5px 5px;'
            for key in ["VendorName", "ProductName", "RegionName", "TestList", "CreateTime", "SummaryText", "ReportID"]:
                if key == "ReportID":
                    html += "<td style = 'padding: 5px 10px 5px 5px;' align='center'><a href='/report?reportid=%d'>%d</a><br></td>" % (response[key], response[key])
                    continue
                if key == "CreateTime":
                    if response[key] != None:  # THIS IS A HACK... there should never be a NULL CreateTime in a real table
                        response[key] = str(datetime.fromtimestamp(response[key]))[:-7]
                        html += "<td style = 'padding: 5px 10px 5px 5px;'>{}</td>".format(str(response[key]))
                else:
                    html += "<td style = 'padding: 5px 10px 5px 5px;'>{}</td>".format(response[key])
            # a trash icon is displayed in the last column for each row to allow you to delete that row
            # rowid is passed as an argument to the /report/delete URL
            html += """<td align="center"><a href = "/report/delete?rowid={}" > <i class='fas fa-trash-alt'> </a></td>""".format(
                response["ReportID"])
            html += "</tr>"
        html += "</table>"
        html += "</html>"
        return html


    if request.method == 'DELETE':
        try:
            conn = sqlite3.connect(DB_FILE_BACKUP, timeout=60)
            conn.row_factory = sqlite3.Row

            if request.data.decode() == "all":
                conn.execute('DELETE FROM report')
                conn.commit()
            else:
                rows = json.loads(request.data.decode())

                for row in rows:
                    conn.execute('DELETE FROM report WHERE rowid=(?)', (row["rowid"],))
                    conn.commit()
            conn.close()
            return "ok"
        except:
            conn.close()
            return "error"

#
# the ability to delete a row from the report table (the trash icon) is directed here
# the url must have the rowid ID set as an argument (done by the table rendering)
#
@config_api.route('/report/delete', methods=['GET'])
def report_delete_row():
    if 'rowid' in request.args:
        rowid = int(request.args['rowid'])
    else:
        return "Error: No rowid specified."
    try:
        conn = sqlite3.connect(DB_FILE_BACKUP, timeout=60)
        conn.row_factory = sqlite3.Row
        conn.execute('DELETE FROM report WHERE rowid=(?)', (rowid,))
        conn.commit()
        conn.close()
        return redirect(request.referrer)
    except:
        conn.close()
        return "error report-delete"

