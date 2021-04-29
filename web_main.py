# file      web_main.py

# brief      small code starting web configuration and results functions

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

from flask import Flask

from web_config import config_api
from web_result import result_api
from manual_test import manual_test
from datetime import datetime

app = Flask(__name__)
#
#   Create a custom filter for displaying time from timestamp
#     on jinja template pages
#
@app.template_filter('cTime')
def time_cTime(s):
    return str(datetime.fromtimestamp(float(s)))[:-7]


def run_web():
    app.register_blueprint(config_api)
    app.register_blueprint(result_api)
    app.register_blueprint(manual_test)
    app.run(host="0.0.0.0", port=80, debug=True, use_reloader=False)


@app.route("/")
def hello():
    html = "<h1>Semtech LoRaWAN<sup>&reg;</sup> Conformance Testbench (CTB)</h1><br>"
    html += "<a href='/table/vendor' target='_blank'>Vendor</a><br>"
    html += "<a href='/product' target='_blank'>Upload Product Picture</a><br>"
    html += "<a href='/table/regionSKU' target='_blank'>Region SKU</a><br>"
    html += "<a href='/device' target='_blank'>Device</a><br>"
    html += "<a href='/sequence' target='_blank'>Waiting List</a><br>"
    html += "<a href='/result' target='_blank'>Result</a><br>"
    html += "<a href='/rg_select' target='_blank'>Generate a Report</a><br>"
    html += "<a href='/report_mng' target='_blank'>Manage and Render Reports</a><br>"
    html += "<h2>Power Cycling</h2>"
    html += "<p>Use the following buttons to power the device up or down</p>"
    html += '<form action="/device/powerup" method="post"> <input type="submit" value="Power On"> </form>'
    html += "<p> </p>"
    html += '<form action="/device/powerdown" method="post"> <input type="submit" value="Power Off"> </form>'
    html += "<h2>Backup and Restart CTB</h2>"
    html += "<p>Use the following buttons to backup all temporary data</p>"
    html += '<form action="/backup" method="post"> <input type="submit" value="Backup tmp data"> </form>'
    html += '<form action="/reboot" method="post"> <input type="submit" value="Backup and Reboot CTB"> </form>'
    html += "<p>Use the following button to Reset the test bench (deleting all databases!)</p>"
    html += '<form action="/reset" method="post"> <input type="submit" value="Delete All (DANGER!)"> </form>'
    html += "<h2>Merge Database</h2>"
    html += '<p>Choose a database file to merge:</p>'
    html += '<form action="/upload" method="post" enctype="multipart/form-data"> <input type="file" name="file"/> ' \
            '<input type="submit"/> </form> '
    html += "<a href='/download' target='_blank'>Download Database File</a><br>"
    return html


if __name__ == '__main__':
    run_web()
