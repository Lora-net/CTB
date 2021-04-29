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

from flask import Blueprint, request, redirect, url_for
import sqlite3, time, os, json, sys, threading
import lib_base as lib
from web_result import generate_cache

manual_test = Blueprint('manual_test', __name__)

qr_questions = {
    'qr_exist': {'full': "Does QR Code exist?",
                 'short': "Does QR Code exist?"},
    'is_readable': {'full':"Is QR Code readable by a QR Code reader?",
                    'short':"Is the QR Code readable?"},
    'location_match': {'full': ("Does the QR Code match the location provided in question "
                                "I.Q.QrLocation of the Intake Questionnaires?"),
                       'short': "Does the location match?"},
    'structure_match': {'full': "Does the QR Code match input proviced in I.Q.QrStructure?",
                        'short': "Does the structure match?"},
    'vendorid_exist': {'full': 'Is VendorID included?',
                       'short': 'Is VendorID included?'},
    'vendorid_correct': {'full': "Is VendorID correct?",
                         'short': "Is VendorID correct?"}
}

security_questions = {
    'join_procedure': {'full': "Was the join procedure successful and did it match the information proviced in S.K.OTAAProcedureReference?",
                       'short': "Does join procedure match the OTAAProcedureReference?",
                       'exp_ans': "Yes"},
    'default_key': {'full': "Is the default Semtech OTA.A.AppKey (2B7E151628AED2A6ABF7158809CF4F3C) used?",
                    'short': "Is the defult Semtech AppKey used?",
                    'exp_ans': "No"},
    'blank_key': {'full': "Is a blank key (000000...00) used?",
                  'short': "Is a blank key used?",
                  'exp_ans': "No"},
    'partial_match_key': {'full': "Are there more than three bytes in the random key (OTA.A.AppKey) that match one another?",
                    'short': "More than three bytes in AppKey match one another",
                    'exp_ans': "No"},
    'symmetric_key': {'full': "Are keys symmetric on all 2 or 3 devices (i.e. 010203......030201)?",
                      'short': "Are keys symmetric?",
                      'exp_ans': "No"},
    'unique_deveui_key': {'full': "Is the DevEUI of this DUT different from other samples'?",
                          'short': "Is the DevEUI unique?",
                          'exp_ans': "Yes"},
    'unique_appkey_key': {'full': "Is the AppKey of this DUT different from other samples'?",
                          'short': "Is the AppKey unique?",
                          'exp_ans': "Yes"},
    'unique_appeui_key': {'full': "Is the AppEUI of this DUT different from other samples'?",
                          'short': "Is the AppEUI unique?",
                          'exp_ans': "No"},
    'derived_key': {'full': "Are keys of this device derived from another as result of an increment?",
                    'short': "Are keys derived from others?",
                    'exp_ans': "No"},
    'embedded_key': {'full': "Are keys embedded one in another, i.e. DevEUI as part of AppEUI or AppKey or any similar combination?",
                     'short': "Are keys embedded one in another?",
                     'exp_ans': "No"},
    'supports_join_server': {'full': 'Does the device support Join Server?',
                             'short': 'Does the device support Join Server?'}
}

def gen_yes_no_question(question, var_name):
    html = '<p>%s</p>' % question
    html += '<input type="radio" id="yes" name="%s", value="Yes">' % var_name
    html += '<label for="yes">Yes</label><br>'
    html += '<input type="radio" id="no" name="%s", value="No">' % var_name
    html += '<label for="no">No</label><br>'
    return html

def insert_record(test_inst):
    keys = tuple(test_inst.keys())
    try:
        conn = sqlite3.connect(lib.DB_FILE_BACKUP, timeout=60)
        conn.row_factory = sqlite3.Row
        test_inst["TestInstID"] = test_inst["rowid"] = \
            conn.execute('INSERT OR REPLACE INTO testInstance (' + ','.join(keys) + ') VALUES (' + ','.join('?'*len(keys)) + ')',
                         [test_inst[key] for key in keys]).lastrowid
        conn.commit()
        conn.close()
        for key in ("Criteria", "Parameter", "CurrentPara", "Config"):
            test_inst[key] = None
        threading.Thread(target=generate_cache, args=(test_inst,)).start()
        return redirect(url_for("result_api.list_tests"))
    except:
        return "add_result error happened: {}".format(sys.exc_info()[0])

def add_to_form(request, title, subcat, inner_html):
    deveui = request.args.get('deveui')
    if not deveui:
        return "Error: Need a DevEui for this test"
    html = '<h1>{}</h1>'.format(title)
    html += '<form action="/test/add_result" method="post", enctype="multipart/form-data">'
    html += '<label for="deveui">DevEUI: {}</label>'.format(deveui)
    html += '<input type="hidden" id="deveui" name="deveui" value="{}" readonly>'.format(deveui)
    html += '<input type="hidden" name="SubCat" value="{}">'.format(subcat)
    html += inner_html
    html += '<br>'
    html += '<label for="operator">Operator:</label>'
    html += '<input type="text" size=20 id="operator" name="operator" value="">'
    html += '<br>'
    html += '<label for="comments">Operator Comments:</label><br>'
    html += '<textarea cols="80", rows="5", id="comments" name="comments"></textarea>'
    html += '<br>'
    html += '<input type="submit", value="Submit">'
    html += '</form>'
    return html

@manual_test.route('/manual/qrcode')
def test_manual_qrcode():
    html = gen_yes_no_question(qr_questions['qr_exist']['full'], "qr_exist")
    html += '<p>If it exists, upload QR Code picture, answer the following questions and click "Submit";'
    html += ' If not, click "Submit" button directly.</p>'
    html += '<input type="file" name="picture">'
    html += gen_yes_no_question(qr_questions['is_readable']['full'], "is_readable")
    html += gen_yes_no_question(qr_questions['location_match']['full'], "location_match")
    html += gen_yes_no_question("Does the QR Code match input proviced in I.Q.QrStructure?", "structure_match")
    html += '<br>'
    html += '<label for="qrcode">QR Code:</label>'
    html += '<input type="text" size=128 id="qrcode" name="qrcode" value="">'
    html += gen_yes_no_question(qr_questions['vendorid_exist']['full'], "vendorid_exist")
    html += gen_yes_no_question(qr_questions['vendorid_correct']['full'], "vendorid_correct")
    return add_to_form(request, 'QR Code Test', 'qrcode', html)


@manual_test.route('/manual/security')
def test_manual_security():
    html = ""
    for key in tuple(security_questions.keys()):
        html += gen_yes_no_question(security_questions[key]['full'], key)

    return add_to_form(request, 'Security Key Distribution Test', 'security', html)


def verify_qrcode(result, test_inst):
    picture = request.files['picture']
    test_inst['Picture'] = picture.read()
    veri_msg = {}
    for key in qr_questions:
        if key not in result:
            result[key] = "No"
    veri_msg['verification'] = [(qr_questions['qr_exist']['short'], result['qr_exist'], result['qr_exist'] == "Yes")]
    if result['qr_exist'] == "Yes":
        for key in ("is_readable", "location_match", "structure_match"):
            veri_msg['verification'].append((qr_questions[key]['short'], result[key], result[key] == "Yes"))

        qr_len = len(result['qrcode'])
        veri_msg['verification'].append(('Length of QR Code: "{}"'.format(result['qrcode']), len(result['qrcode']),
                                         qr_len >= 48 and qr_len <= 128))
        if result['vendorid_exist'] == "Yes":
            veri_msg['verification'].append((qr_questions['vendorid_correct']['short'],
                                             result['vendorid_correct'],
                                             result['vendorid_correct'] == "Yes"))
    test_inst['VerificationMsg'] = veri_msg
    passed = True
    for item in veri_msg['verification']:
        passed = passed and item[2]
    if not passed:
        test_inst['Passed'] = lib.TEST_STATE['FAILED']
        test_inst['ErrorMsg'] = "verification failed"
    else:
        test_inst['Passed'] = lib.TEST_STATE['PASSED']
        test_inst['ErrorMsg'] = None

def verify_security(result, test_inst):
    veri_msg = {}
    for key in security_questions:
        if key not in result:
            result[key] = "No"

    veri_msg['verification'] = []
    for key in ('join_procedure', 'default_key', 'blank_key', 'partial_match_key',
                'symmetric_key', 'unique_deveui_key', 'unique_appkey_key', 'unique_appeui_key', 'derived_key', 'embedded_key'):
        veri_msg['verification'].append((security_questions[key]['short'],
                                         result[key], result[key] == security_questions[key]['exp_ans']))

    veri_msg['verification'].append(((security_questions['supports_join_server']['short'],
                                 result['supports_join_server'],
                                 True if result['supports_join_server'] == "Yes" else "Warning")))

    passed = True
    for item in veri_msg['verification']:
        passed = passed and item[2]
    if not passed:
        test_inst['Passed'] = lib.TEST_STATE['FAILED']
        test_inst['ErrorMsg'] = "verification failed"
    else:
        test_inst['Passed'] = lib.TEST_STATE['PASSED']
        test_inst['ErrorMsg'] = None

    test_inst['VerificationMsg'] = veri_msg

@manual_test.route('/test/add_result', methods=['POST'])
def add_result():
    result = request.form.to_dict(flat=True)
    test_inst = {'DevEui': result['deveui'], 'BenchID': lib.config["gateway_id"],
                 'Cat': 'manual', 'SubCat': result['SubCat'], 'Comments': result['comments']}
    test_time = time.time()
    for key in ('AddTime', 'StartTime', 'UpdateTime', 'FinishTime'):
        test_inst[key] = test_time

    eval('verify_{}(result, test_inst)'.format(result['SubCat']))
    test_inst['VerificationMsg'] = json.dumps(test_inst['VerificationMsg'])
    test_inst['Ready'] = lib.CACHE_STATE['GENERATING']
    test_inst['DevEui'] = test_inst['DevEui'].lower()

    return insert_record(test_inst)
