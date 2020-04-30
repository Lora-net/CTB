#file      send_sequence.py

#brief      scrypt to start a full test sequence to test bench

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

import requests
import json

ip = "10.9.72.10"
DevEui = "3246CDB93246CDB9"

url = "http://" + ip + "/device"

data = [
    {
        "DevEui": DevEui,
        "AppKey":"2B7E151628AED2A6ABF7158809CF4F3C",
        "NwkKey":"2B7E151628AED2A6ABF7158809CF4F3C",
        "region":"US"
    }
]
data_send = data

r = requests.post(url = url, data = json.dumps(data_send))
print(r.text)


url = "http://" + ip + "/sequence"


data = {
    "normal": {
        "normal": {
            "Criteria": "count",
            "Parameter": 32
        }
    },
}

"""
data = {
    "join": {
        "deny": {
            "Criteria": "count",
            "Parameter": 8
        },
        "mic": {
            "Criteria": "count",
            "Parameter": 4
        },
        "rx2": {
            "Criteria": "count",
            "Parameter": 4
        }
    },
    "normal": {
        "normal": {
            "Criteria": "count",
            "Parameter": 24
        }
    },
    "mac": {
        "mask_125": {
            "Criteria": "count",
            "Parameter": 8
        },
        "mask_500": {
            "Criteria": "count",
            "Parameter": 8
        },
        "tx_power": {
            "Criteria": "count",
            "Parameter": 12
        },
        "dr": {
            "Criteria": "count",
            "Parameter": 8
        },
        "redundancy": {
            "Criteria": "count",
            "Parameter": 16
        },
        "status": {
            "Criteria": "count",
            "Parameter": 4
        },
        "rx_para_rx1dro": {
            "Criteria": "count",
            "Parameter": 8
        },
        "rx_para_rx2dr": {
            "Criteria": "count",
            "Parameter": 8
        },
        "rx_para_rx2freq": {
            "Criteria": "count",
            "Parameter": 8
        },
        "rx_timing": {
            "Criteria": "count",
            "Parameter": 8
        }
    },
    "downlink": {
        "confirmed": {
            "Criteria": "count",
            "Parameter": 8,
            "Config": {
                "FPort": 20
            }
        },
        "cnt": {
            "Criteria": "count",
            "Parameter": 8
        },
        "freq": {
            "Criteria": "count",
            "Parameter": 44,
            "Config": {
                  "Step": 4,
                  "Datr": 3
            }
        },
        "timing": {
            "Criteria": "count",
            "Parameter": 44,
            "Config": {
                  "Step": 20,
                  "Datr": 3
            }
        },
        "mic": {
            "Criteria": "count",
            "Parameter": 8
        }
    }
}
"""

data_send = []

for cat in data:
    for subcat in data[cat]:
        d = {
            "DevEui": DevEui,
            "Cat": cat,
            "SubCat": subcat
        }
        d = {**d, **data[cat][subcat]}
        data_send.append(d)

print(json.dumps(data_send, indent = 4))



r = requests.post(url = url, data = json.dumps(data_send))
print(r.text)
