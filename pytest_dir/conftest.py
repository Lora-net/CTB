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

import socket
import json
import sqlite3
import time
import pytest
import os
import logging
import operator
import inspect
import subprocess
import signal
import sys
from importlib import import_module
import copy
import threading
import requests

sys.path.append("..")
import lib_base as lib
from lib_base import GW_ID

def pytest_addoption(parser):
    parser.addoption(
        "--deveui", action="store", default="70B3B514900B03A8", help="deveui used in the test"
    )
    parser.addoption(
        "--criteria", action="store", default="count", help="criteria used in the test"
    )
    parser.addoption(
        "--parameter", action="store", type=int, default=8, help="parameter used in the test"
    )
    parser.addoption(
        "--config", action="store", default="{}", help="config for the test"
    )
    parser.addoption(
        "--addtime", action="store", type=float, help="addtime of the test. Use current time when it doesn't exist"
    )
    parser.addoption(
        "--pcap", action="store_true", default=False, help="flag to enable pcap"
    )
    parser.addoption(
        "--verify_only", action="store_true", default=False, help="flag to enable verification only"
    )
    parser.addoption(
        "--rowid", action="store", type=int, help="rowid of the test instance, only used for verification only"
    )
    parser.addoption(
        "--timeout", action="store", default="{}", help="set time out for test at both step level and test level"
    )

header = {'Content-Type': 'application/json', 
    'Accept': 'application/json',
    'Grpc-Metadata-Authorization': 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhcGlfa2V5X2lkIjoiM2JmNjUzMmYtYmJkZS00NGYzLTkwOGItNGJlMjNjNTllOTM1IiwiYXVkIjoiYXMiLCJpc3MiOiJhcyIsIm5iZiI6MTYwNTgxOTQyMCwic3ViIjoiYXBpX2tleSJ9.R66bBddlNju8IvRVYB0bLZ7xjvyj5f4l14CD7Q5oPUg'
    }

nsdata ={"networkServer": 
        {
        "caCert": "",
        "gatewayDiscoveryDR": 0,
        "gatewayDiscoveryEnabled": False,
        "gatewayDiscoveryInterval": 0,
        "gatewayDiscoveryTXFrequency": 0,
        "id": "1",
        "name": "default",
        "routingProfileCACert": "",
        "routingProfileTLSCert": "",
        "routingProfileTLSKey": "",
        "server": "",
        "tlsCert": "",
        "tlsKey": ""
        }
    }
    
gwProfiledataUS ={"gatewayProfile": 
        {
        "channels": [0,1,2,3,4,5,6,7],
        "extraChannels": [],
        "id": "532a5bec-5351-4bd2-ba71-0e8e88edf017",
        "name": "default",
        "statsInterval": None
        }
    }

gwProfiledataEU ={"gatewayProfile": 
        {
        "channels": [0,1,2,3,4,5,6,7],
        "extraChannels": [
        {
        "modulation": "LORA",
        "frequency": 867100000,
        "bandwidth": 125,
        "bitrate": 0,
        "spreadingFactors": [7,8,9,10,11,12] 
        },
        {
        "modulation": "LORA",
        "frequency": 867300000,
        "bandwidth": 125,
        "bitrate": 0,
        "spreadingFactors": [7,8,9,10,11,12] 
        },
        {
        "modulation": "LORA",
        "frequency": 867500000,
        "bandwidth": 125,
        "bitrate": 0,
        "spreadingFactors": [7,8,9,10,11,12] 
        },
        {
        "modulation": "LORA",
        "frequency": 867700000,
        "bandwidth": 125,
        "bitrate": 0,
        "spreadingFactors": [7,8,9,10,11,12] 
        },
        {
        "modulation": "LORA",
        "frequency": 867900000,
        "bandwidth": 125,
        "bitrate": 0,
        "spreadingFactors": [7,8,9,10,11,12] 
        },
        {
        "modulation": "LORA",
        "frequency": 868300000,
        "bandwidth": 125,
        "bitrate": 0,
        "spreadingFactors": [7,8,9,10,11,12] 
        },
        {
        "modulation": "LORA",
        "frequency": 868500000,
        "bandwidth": 125,
        "bitrate": 0,
        "spreadingFactors": [7,8,9,10,11,12] 
        }
        ],
        "id": "532a5bec-5351-4bd2-ba71-0e8e88edf017",
        "name": "default",
        "statsInterval": None
        }
    }

gwdata = {"gateway": 
        {
        "boards": [],
        "description": "Volatile gateway",
        "discoveryEnabled": False,
        "location": 
        {
          "accuracy": 0,
          "altitude": 0,
          "latitude": 0,
          "longitude": 0,
          "source": "UNKNOWN"
        },
        "metadata": {},
        "name": "default",
        "tags": {}
        }
    }   

dpdata= {"deviceProfile": 
        {
        "classBTimeout": 0,
        "classCTimeout": 0,
        "factoryPresetFreqs": [],
        "geolocBufferTTL": 0,
        "geolocMinBufferSize": 0,
        "id": "532a5bec-5351-4bd2-ba71-0e8e88edf017",
        "macVersion": "1.0.2",
        "maxDutyCycle": 0,
        "maxEIRP": 30,
        "name": "default",
        "payloadCodec": "",
        "payloadDecoderScript": "",
        "payloadEncoderScript": "",
        "pingSlotDR": 0,
        "pingSlotFreq": 0,
        "pingSlotPeriod": 0,
        "regParamsRevision": "B",
        "rfRegion": "US915",
        "rxDROffset1": 0,
        "rxDataRate2": 0,
        "rxDelay1": 0,
        "rxFreq2": 0,
        "supports32BitFCnt": False,
        "supportsClassB": False,
        "supportsClassC": False,
        "supportsJoin": True,
        "tags": {},
        "uplinkInterval": "60s"
        }   
    }

spdata= {"serviceProfile": 
        {
        "addGWMetaData": True,
        "channelMask": None,
        "devStatusReqFreq": 0,
        "dlBucketSize": 0,
        "dlRate": 0,
        "dlRatePolicy": "DROP",
        "drMax": 0,
        "drMin": 0,
        "hrAllowed": False,
        "id": "21212121-2121-2121-2121-2121212121ae",
        "minGWDiversity": 0,
        "name": "default",
        "nwkGeoLoc": False,
        "prAllowed": False,
        "raAllowed": False,
        "reportDevStatusBattery": True,
        "reportDevStatusMargin": True,
        "targetPER": 0,
        "ulBucketSize": 0,
        "ulRate": 0,
        "ulRatePolicy": "DROP"
        }
    }

appdata={"application": 
        {
        "description": "volatile application",
        "id": "0",
        "name": "default",
        "payloadCodec": "",
        "payloadDecoderScript": "",
        "payloadEncoderScript": "" 
        }
    }

devicedata = {"device": 
        { 
        "description": "Device under test",  
        "isDisabled": False, 
        "name": "DUT", 
        "referenceAltitude": 0, 
        "skipFCntCheck": True, 
        "tags": {}, 
        "variables": {} 
        }
    }
    
nsdata = {"networkServer": 
    {
        "id": "1",
        "name": "default ns ",
        "server": "localhost:8000",
        "caCert": "",
        "tlsCert": "",
        "tlsKey": "",
        "routingProfileCACert": "",
        "routingProfileTLSCert": "",
        "routingProfileTLSKey": "",
        "gatewayDiscoveryEnabled": False,
        "gatewayDiscoveryInterval": 0,
        "gatewayDiscoveryTXFrequency": 0,
        "gatewayDiscoveryDR": 0
    }
}  
orgdata = {"organization": 
    {
        "canHaveGateways": True,
        "displayName": "default",
        "id": "1",
        "maxDeviceCount": 20,
        "maxGatewayCount": 20,
        "name": "default"
    }
}  
keysdata = {"deviceKeys": 
    {
        "appKey": "5A6967426565416C6C69616E63653039",
        "genAppKey": "",
        "nwkKey": "5A6967426565416C6C69616E63653039"
    }
}

gwdata['gateway']['id'] = GW_ID 
orgURL = 'http://localhost:8080/api/organizations'
gwProfileURL = 'http://localhost:8080/api/gateway-profiles'
gwURL = 'http://localhost:8080/api/gateways'
serviceProfileURL = 'http://localhost:8080/api/service-profiles'
deviceProfileURL = 'http://localhost:8080/api/device-profiles'
applicationURL = 'http://localhost:8080/api/applications'
deviceURL = 'http://localhost:8080/api/devices'
nsURL = 'http://localhost:8080/api/network-servers'

nscreated=False
orgflag=False
nsflag=False
spflag=False
gwpflag=False
gwflag=False
dflag=False
dpflag=False
appflag=False
http_response_ok = 200

def networkservice():
    ns_eu = subprocess.Popen(["chirpstack-network-server", "-c", "/home/pi/chirpstack_ns_EU/chirpstack-network-server.toml"], stdout=subprocess.PIPE)
    time.sleep(9)
            
@pytest.fixture
def chirpstack_EU(request):
 
    deveui = request.config.getoption("--deveui")
    print(deveui)
    nscreated=False
    networkservice()
    #ns_eu = subprocess.Popen(["chirpstack-network-server", "-c", "/home/pi/chirpstack_ns_EU/chirpstack-network-server.toml"], stdout=subprocess.PIPE)
    jwt= requests.post("http://localhost:8080/api/internal/login", headers={'Content-Type': 'application/json', 'Accept': 'application/json'}, data= json.dumps({"email": "admin","password": "admin"} ))
    if jwt.status_code == http_response_ok:
    
        header['Grpc-Metadata-Authorization']= 'Bearer ' + jwt.json()["jwt"]
        logging.info("Beginning creation of chisrpstack services")
        for count in range(9):            
            try:
                time.sleep(1)
                logging.debug("Creating NS, attempt number {}".format(count+1))
                createns = requests.post(nsURL, headers = header, data =json.dumps(nsdata))
                if createns.status_code==http_response_ok:
                    nscreated=True
                    logging.debug("Network server created")
                    break
            except:
                pass
           
        if nscreated==False:
            logging.error("Timeout(10s): Network server could not be created correctly ")
            print("http response:",createns) 
            os.system("sudo pkill chirpstack-netw")
#            ns_eu.poll()
            print("Network server process status: ",ns_eu.returncode)
            raise Exception("Network server creation timeout, please retry")
        else:
            nsflag=True
            print("Network server created")
            deletensURL = nsURL + '/' + createns.json()['id']
            gwProfiledataEU['gatewayProfile']['networkServerID']=createns.json()['id']
            gwdata['gateway']['networkServerID']=createns.json()['id']
            dpdata['deviceProfile']['networkServerID']=createns.json()['id']
            spdata['serviceProfile']['networkServerID']=createns.json()['id']  
            
            createorg = requests.post(orgURL, headers = header , data = json.dumps(orgdata) )    
            if createorg.status_code!=http_response_ok:
                print("Organization could not be created", createorg)
            else:    
                orgflag=True
                print("Organization created")
                deleteorgURL = orgURL + '/' + createorg.json()['id']
                appdata['application']['organizationID']=createorg.json()['id']
                spdata['serviceProfile']['organizationID']=createorg.json()['id']
                dpdata['deviceProfile']['organizationID']=createorg.json()['id']
                gwdata['gateway']['organizationID']=createorg.json()['id']
                
                createsp = requests.post(serviceProfileURL, headers = header , data = json.dumps(spdata) )        
                if createsp.status_code!=http_response_ok:      
                    print("Service profile could not be created correctly",createsp)      
                        
                else:
                    spflag = True
                    print("Service profile created")
                    deleteserviceProfileURL = serviceProfileURL + '/' + createsp.json()['id']
                    
                    creategwp = requests.post(gwProfileURL,headers=header,data=json.dumps(gwProfiledataEU))
                    if creategwp.status_code!=http_response_ok:
                        print("Gateway profile could not be created correctly",creategwp)
                        
                    else:
                        gwpflag=True
                        print("Gateway profile created")
                        deletegwpURL = gwProfileURL + '/' + creategwp.json()['id']
                            
                        createdp = requests.post(deviceProfileURL, headers = header, data = json.dumps(dpdata))
                        if createdp.status_code!=http_response_ok:
                            print("Device profile could not be created correctly",createdp)
                            
                        else: 
                            dpflag=True
                            print("Device profile created")  
                            deletedeviceProfileURL = deviceProfileURL + '/' + createdp.json()['id']
                                
                            appdata['application']['serviceProfileID'] = createsp.json()['id']   
                            createapp = requests.post(applicationURL,headers = header, data = json.dumps(appdata))
                            if createapp.status_code!=http_response_ok:
                                print("Application could not be created correctly", createapp) 
                                
                            else:
                                appflag=True
                                print("Application created")
                                deleteapplicationURL = applicationURL + '/' + createapp.json()['id']
                                 
                                gwdata['gateway']['gatewayProfileID'] = creategwp.json()['id']
                                creategw = requests.post(gwURL,headers = header,data=json.dumps(gwdata))
                                if creategw.status_code!=http_response_ok:
                                    print("Gateway could not be added correctly", creategw)
                                else:
                                    gwflag=True
                                    print("Gateway added")
                                    deletegwURL = gwURL + '/' + gwdata['gateway']['id']                                                   
                                    devicedata['device']['applicationID'] = createapp.json()['id']
                                    devicedata['device']['devEUI'] = deveui
                                    devicedata['device']['deviceProfileID'] = createdp.json()['id']
                                    createdevice = requests.post(deviceURL,headers = header, data = json.dumps(devicedata))
                                    if createdevice.status_code!=http_response_ok:
                                        print("Device could not be provissioned correctly", createdevice)
                                    else:
                                        dflag=True    
                                        deletedeviceURL = deviceURL + '/' + devicedata['device']['devEUI']
                                        print("Device provissioned, adding keys")
                                        keysURL = deletedeviceURL + '/keys' 
                                        keysdata['deviceKeys']['devEUI'] = devicedata['device']['devEUI']
                                        createkeys = requests.post(keysURL,headers = header, data = json.dumps(keysdata))
                                        if createkeys.status_code!=http_response_ok:
                                            print("Device keys could not be added")
                                        else:
                                            print("Device keys added")
    else:
        print("Cannot retrieve api key, chirpstack services not initialized")            
        
    yield 
            
    print("Beginning teardown of chirpstack services")
    if dflag: 
        deletedevice = requests.delete(deletedeviceURL,headers=header)
        print("Device provissioning deletion status", deletedevice)    
    if appflag: 
        deleteapp = requests.delete(deleteapplicationURL,headers=header)
        print("Application deletion status", deleteapp)    
    if gwflag: 
        deletegw = requests.delete(deletegwURL,headers=header)
        print("Gateway deletion status", deletegw)
    if gwpflag: 
        deletegwp = requests.delete(deletegwpURL,headers=header)
        print("Gateway profile deletion status", deletegwp)
    if dpflag: 
        deletedp = requests.delete(deletedeviceProfileURL,headers=header)
        print("Device profile deletion status", deletedp)        
    if spflag: 
        deletesp = requests.delete(deleteserviceProfileURL, headers=header)
        print("Service profile deletion status", deletesp)
    if nsflag:
        deletens = requests.delete(deletensURL, headers=header)
        print("Network server deletion status", deletens)
    if orgflag:
        deleteorg = requests.delete(deleteorgURL, headers=header)
        print("Organization deletion status", deleteorg)
    print("Killing network server process")
    os.system("sudo pkill chirpstack-netw")
#    ns_eu.poll()
#    print(ns_eu.returncode)
        
def ns_us():
    ns_us = subprocess.Popen(["chirpstack-network-server", "-c", "/home/pi/chirpstack_ns_US/chirpstack-network-server.toml"], stdout=subprocess.PIPE)   
    time.sleep(10)

@pytest.fixture
def chirpstack_US():

    ns_us()
    jwt= requests.post("http://localhost:8080/api/internal/login", headers={'Content-Type': 'application/json', 'Accept': 'application/json'}, data= json.dumps({"email": "admin","password": "admin"} ))
    if jwt.status_code == http_response_ok:
    
        header['Grpc-Metadata-Authorization']= 'Bearer ' + jwt.json()["jwt"]
        print("Beginning creation of chisrpstack services")
        createns = requests.post(nsURL, headers = header, data =json.dumps(nsdata))
        if createns.status_code!=http_response_ok:
            print("Network server could not be created correctly",createns) 
        else:
            nsflag=True
            print("Network server created")
            deletensURL = nsURL + '/' + createns.json()['id']
            gwProfiledataUS['gatewayProfile']['networkServerID']=createns.json()['id']
            gwdata['gateway']['networkServerID']=createns.json()['id']
            dpdata['deviceProfile']['networkServerID']=createns.json()['id']
            spdata['serviceProfile']['networkServerID']=createns.json()['id']  
            
            createorg = requests.post(orgURL, headers = header , data = json.dumps(orgdata) )    
            if createorg.status_code!=http_response_ok:
                print("Organization could not be created", createorg)
            else:    
                orgflag=True
                print("Organization created")
                deleteorgURL = orgURL + '/' + createorg.json()['id']
                appdata['application']['organizationID']=createorg.json()['id']
                spdata['serviceProfile']['organizationID']=createorg.json()['id']
                dpdata['deviceProfile']['organizationID']=createorg.json()['id']
                gwdata['gateway']['organizationID']=createorg.json()['id']
                
                createsp = requests.post(serviceProfileURL, headers = header , data = json.dumps(spdata) )        
                if createsp.status_code!=http_response_ok:      
                    print("Service profile could not be created correctly",createsp)      
                        
                else:
                    spflag = True
                    print("Service profile created")
                    deleteserviceProfileURL = serviceProfileURL + '/' + createsp.json()['id']
                    
                    creategwp = requests.post(gwProfileURL,headers=header,data=json.dumps(gwProfiledataUS))
                    if creategwp.status_code!=http_response_ok:
                        print("Gateway profile could not be created correctly",creategwp)
                        
                    else:
                        gwpflag=True
                        print("Gateway profile created")
                        deletegwpURL = gwProfileURL + '/' + creategwp.json()['id']
                            
                        createdp = requests.post(deviceProfileURL, headers = header, data = json.dumps(dpdata))
                        if createdp.status_code!=http_response_ok:
                            print("Device profile could not be created correctly",createdp)
                            
                        else: 
                            dpflag=True
                            print("Device profile created")  
                            deletedeviceProfileURL = deviceProfileURL + '/' + createdp.json()['id']
                                
                            appdata['application']['serviceProfileID'] = createsp.json()['id']   
                            createapp = requests.post(applicationURL,headers = header, data = json.dumps(appdata))
                            if createapp.status_code!=http_response_ok:
                                print("Application could not be created correctly", createapp) 
                                
                            else:
                                appflag=True
                                print("Application created")
                                deleteapplicationURL = applicationURL + '/' + createapp.json()['id']
                                 
                                gwdata['gateway']['gatewayProfileID'] = creategwp.json()['id']
                                creategw = requests.post(gwURL,headers = header,data=json.dumps(gwdata))
                                if creategw.status_code!=http_response_ok:
                                    print("Gateway could not be added correctly", creategw)
                                else:
                                    gwflag=True
                                    print("Gateway added")
                                    deletegwURL = gwURL + '/' + gwdata['gateway']['id']                                                   
                                    devicedata['device']['applicationID'] = createapp.json()['id']
                                    devicedata['device']['devEUI'] = deveui
                                    devicedata['device']['deviceProfileID'] = createdp.json()['id']
                                    createdevice = requests.post(deviceURL,headers = header, data = json.dumps(devicedata))
                                    if createdevice.status_code!=http_response_ok:
                                        print("Device could not be provissioned correctly", createdevice)
                                    else:
                                        dflag=True    
                                        deletedeviceURL = deviceURL + '/' + devicedata['device']['devEUI']
                                        print("Device provissioned, adding keys")
                                        keysURL = deletedeviceURL + '/keys' 
                                        keysdata['deviceKeys']['devEUI'] = devicedata['device']['devEUI']
                                        createkeys = requests.post(keysURL,headers = header, data = json.dumps(keysdata))
                                        if createkeys.status_code!=http_response_ok:
                                            print("Device keys could not be added")
                                        else:
                                            print("Device keys added")
    else:
        print("Cannot retrieve api key, chirpstack services not initialized")            
        
    yield 
            
    print("Beginning teardown of chirpstack services")
    if dflag: 
        deletedevice = requests.delete(deletedeviceURL,headers=header)
        print("Device provissioning deletion status", deletedevice)    
    if appflag: 
        deleteapp = requests.delete(deleteapplicationURL,headers=header)
        print("Application deletion status", deleteapp)    
    if gwflag: 
        deletegw = requests.delete(deletegwURL,headers=header)
        print("Gateway deletion status", deletegw)
    if gwpflag: 
        deletegwp = requests.delete(deletegwpURL,headers=header)
        print("Gateway profile deletion status", deletegwp)
    if dpflag: 
        deletedp = requests.delete(deletedeviceProfileURL,headers=header)
        print("Device profile deletion status", deletedp)        
    if spflag: 
        deletesp = requests.delete(deleteserviceProfileURL, headers=header)
        print("Service profile deletion status", deletesp)
    if nsflag:
        deletens = requests.delete(deletensURL, headers=header)
        print("Network server deletion status", deletens)
    if orgflag:
        deleteorg = requests.delete(deleteorgURL, headers=header)
        print("Organization deletion status", deleteorg)
    ns_us.kill()


@pytest.fixture
def schedule(request):
    schedule = {}
    logging.debug("test name is {}".format(request.node.name))
    test_names = request.node.name.split("_", 2)
    schedule['Cat'] = test_names[1]
    schedule['SubCat'] = test_names[2]
    schedule['DevEui'] = request.config.getoption("--deveui")
    schedule['Criteria'] = request.config.getoption("--criteria")
    schedule['Parameter'] = request.config.getoption("--parameter")
    schedule['Config'] = eval(request.config.getoption("--config"))
    schedule['AddTime'] =  request.config.getoption("--addtime") if request.config.getoption("--addtime") else time.time()
    schedule['pcap'] = request.config.getoption("--pcap")
    schedule['verify_only'] = request.config.getoption("--verify_only")
    if schedule['verify_only']:
        schedule['rowid'] =  request.config.getoption("--rowid") if request.config.getoption("--rowid") else None
    schedule['timeout'] = eval(request.config.getoption("--timeout"))
    return schedule


class TestController:
    __test__ = False
    keyboard_interrupt = False

    def __init__(self):
        self.start_time = 0
        self.update_time = 0
        self.pcap = False
        self.verify_only = False
        self.standby = False
        self.packet_count = 0
        self.schedule = {}
        self.packets = []
        self.conn = None
        self.sock = None
        self.ads_process = None
        self.fwd_process = None
        self.setup_ready = False
        self.exception_msg = None
        self.fwd_running = False
        self.veri_msg = {}
        logging.info("class controller successfully started")

    def config_test(self, schedule, standby=False):
        logging.debug("config_test, schedule is {}".format(schedule))
        if schedule['verify_only']:
            assert schedule['rowid'], 'No rowid found for verification only test'
            self.schedule['TestInstID'] = self.schedule["rowid"] = schedule['rowid']
            self.verify_only = True
            conn = sqlite3.connect(os.path.join("..", lib.DB_FILE_BACKUP), timeout=60)
            conn.row_factory = sqlite3.Row
            response = conn.execute('SELECT * from testInstance WHERE rowid=(?)',
                                    (self.schedule['rowid'],)).fetchone()
            conn.close()
            tmp = dict(response)
            assert schedule['Cat'] == tmp['Cat'] and schedule['SubCat'] == tmp['SubCat']
            tmp['Config'] = json.loads(tmp['Config'])
            self.config = tmp['Config']
            for key in tmp:
                self.schedule[key] = tmp[key]

            from web_result import del_cache
            del_cache("verification", self.schedule)
            del_cache("title", self.schedule)
            return

        self.schedule['DevEui'] = schedule["DevEui"].lower()
        self.schedule['StartTime'] = time.time()
        for key in ["Cat", "SubCat", "Criteria", "Parameter", "Config", "AddTime"]:
            self.schedule[key] = schedule[key]
        self.pcap = schedule['pcap']
        self.config = schedule['Config']
        self.standby = standby

        logging.debug("deveui: {}, standby:{}".format(self.schedule["DevEui"], standby))
        if not self.standby:
            conn = sqlite3.connect(os.path.join("..", lib.DB_FILE_BACKUP), timeout=60)
            conn.row_factory = sqlite3.Row
            self.schedule["TestInstID"] = self.schedule["rowid"] = \
                conn.execute('INSERT OR REPLACE INTO testInstance (DevEui, BenchID, Cat, SubCat, Criteria, Parameter, \
                CurrentPara, Config, AddTime, StartTime, Passed, Ready) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                             (self.schedule["DevEui"], lib.config["gateway_id"], self.schedule["Cat"], self.schedule["SubCat"],
                              self.schedule["Criteria"], self.schedule["Parameter"], 0, json.dumps(self.schedule["Config"]),
                              self.schedule["AddTime"], self.schedule["StartTime"], lib.TEST_STATE['RUNNING'],
                              lib.CACHE_STATE['NONE'])).lastrowid
            conn.commit()
            conn.close()
            logging.debug("rowid is {}".format(self.schedule["TestInstID"]))

            self.conn = sqlite3.connect(os.path.join("..", lib.DB_FILE_CONTROLLER), timeout=60)
            self.conn.row_factory = sqlite3.Row
            self.temp_rowid = \
                self.conn.execute('INSERT OR REPLACE INTO testInstance (DevEui, BenchID, Cat, SubCat, Criteria, Parameter, \
                CurrentPara, Config, AddTime, StartTime) VALUES (?,?,?,?,?,?,?,?,?,?)',
                                (self.schedule["DevEui"], lib.config["gateway_id"], self.schedule["Cat"], self.schedule["SubCat"],
                                self.schedule["Criteria"], self.schedule["Parameter"], 0, json.dumps(self.schedule["Config"]),
                                self.schedule["AddTime"], self.schedule["StartTime"])).lastrowid
            self.conn.commit()

        if self.pcap:
            self.tcp_process = lib.start_pcap()

    def setup_socket(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(1)
        self.sock.bind(("", lib.addr_tc[1]))
        if not self.standby:
            self.sock.sendto(bytes([lib.PROC_MSG["TC_SETUP_TEST"]])
                             + json.dumps(self.schedule).encode(), lib.addr_pc)
            self.sock.sendto(bytes([0, 1, 2, lib.PROC_MSG["TC_SETUP_TEST"]])
                             + json.dumps({'DevEui': self.schedule['DevEui'],
                                           "TestInstID": self.schedule['TestInstID']}).encode(),
                             lib.addr_pf)

    def start_misc_process(self):
        threading.Thread(target=os.system, args=("cd ../ads1256 && sudo ./ads1256_driver > /dev/null",)).start()
        time.sleep(1)

        if lib.use_internal_gateway:
            path = os.getcwd()
            logging.debug("current path is %s" % path)
            os.chdir('/home/pi/lora-net/picoGW_packet_forwarder/lora_pkt_fwd/')
            self.fwd_process = subprocess.Popen(['./lora_pkt_fwd'],
                                                stdout=subprocess.PIPE,
                                                stderr=subprocess.STDOUT)
            os.chdir(path)
            self.log_thread = threading.Thread(target=self.log_fwd)
            self.log_thread.start()

    def sequence(self, tc, pkt):
        return pkt, False

    def power_cycle_device(self):
        logging.debug("power cycling device starts")
        lib.device_on(False)
        time.sleep(10)
        lib.device_on()
        logging.debug("power cycling device is finished")

    def receive(self):
        try:
            byte_data, addr = self.sock.recvfrom(10240)
        except socket.timeout:
            return None
        self.addr_proxy = addr

        json_data = json.loads(byte_data[4:].decode())
        pkt = None
        for pk in ['rxpk', 'txpk']:
            if pk in json_data:
                pkt = json_data[pk]
                self.header = byte_data[:4]
                self.packet_type = pk
                logging.debug("controller received {}, token is: {}, packet is: {}".format(
                    list(byte_data[1:3]), pk, pkt))

                if pk == 'rxpk' and self.is_duplicate(pkt):
                    pkt = None
                    break
                # For now, for rx, save the packet before manipulation, so deepcopy
                # a backup and append it to the list. For tx, save the packets after according
                # to the logic in get_all_packets in web_result
                if pk == 'rxpk':
                    self.packets.append(copy.deepcopy(pkt))
                else:
                    self.packets.append(pkt)
                break

        return pkt

    def send(self, pkt):
        if self.header and self.packet_type:
            byte_data = self.header + json.dumps({self.packet_type: pkt}).encode()
            self.sock.sendto(byte_data, self.addr_proxy)
            self.header = None
            self.packet_type = None

    def is_duplicate(self, pkt):
        # deduplication
        if pkt['json']['MType'] in lib.UPLINK_PACKETS and "UpdateTime" in self.schedule:
            if time.time() - self.schedule["UpdateTime"] < lib.deduplication_threshold:
                logging.debug('dedup worked')
                return None
        if pkt['json']['MType'] in lib.UPLINK_PACKETS:
            self.schedule["UpdateTime"] = time.time()
            if not self.standby:
                self.conn.execute("UPDATE testInstance SET UpdateTime=(?), CurrentPara=(?) WHERE rowid=(?)",
                                  (self.schedule["UpdateTime"], self.packet_count, self.temp_rowid))
                self.conn.commit()

    def wait_for_packet(self, packet, timeout=20):
        start_time = time.time()
        success = False
        while not success and time.time()-start_time < timeout:
            pkt = self.receive()
            if pkt:
                if pkt["json"]["MType"] in packet:
                    success = True
                self.send(pkt)
        assert success, "wait_for_packet: {} timed out".format(packet)

    def wait_till_timeout(self, timeout):
        start_time = time.time()
        while time.time() - start_time < timeout:
            pkt = self.receive()
            if pkt:
                if pkt['json']['MType'] in lib.UPLINK_PACKETS:
                    self.packet_count += 1
                self.send(pkt)

    def wait_and_inject_dnlk_cmd(self, cmd, mac_cmd=None, fport=None, timeout=1200):
        start_time = time.time()
        success = False
        while not success and time.time() - start_time < timeout:
            pkt = self.receive()
            if pkt:
                if pkt["json"]["MType"] not in [lib.JOIN_REQUEST, lib.JOIN_ACCEPT]:
                    pkt["json"]["MAC Commands"] = []
                    pkt["json"]["FOpts"] = ""
                    if pkt["json"]["FPort"] == 0:
                        pkt["json"]["FPort"] = -1
                    pkt["size"] = -1

                if pkt["json"]["MType"] in [lib.UNCONFIRMED_DATA_UP, lib.CONFIRMED_DATA_UP]:
                    pkt["json"]["MType"] = lib.CONFIRMED_DATA_UP
                if pkt["json"]["MType"] in [lib.UNCONFIRMED_DATA_DOWN, lib.CONFIRMED_DATA_DOWN]:
                    if fport:
                        pkt["json"]["FPort"] = fport
                    if mac_cmd:
                        pkt["json"]["MAC Commands"] = mac_cmd
                        pkt["json"]["FOpts"] = cmd
                    else:
                        pkt["json"]["FRMPayload"] = cmd
                    success = True

                self.send(pkt)
        return success

    def overwrite_params_from_config(self, params):
        for key in params:
            if key in self.config:
                params[key] = self.config[key]

    def log_fwd(self):
        success_info = "concentrator started, packet can now be received"
        fatal_error = "ERROR: FAIL TO CONNECT BOARD ON"
        fatal_error_len = len(fatal_error)
        with self.fwd_process.stdout:
            for line in iter(self.fwd_process.stdout.readline, b''): # b'\n'-separated lines
                tmp = line.decode().rstrip()
                if tmp =="":
                    continue
                elif tmp[0:5] == "INFO:":
                    logging.info("[pkt_fwd] %s" % tmp[5:])
                    if not self.fwd_running and tmp.find(success_info) != -1:
                        self.fwd_running = True
                elif tmp[0:6] == "ERROR:":
                    logging.error("[pkt_fwd] %s" % tmp[6:])
                    if tmp[0:fatal_error_len] == fatal_error:
                        self.exception_msg = tmp
                        raise Exception(tmp)
                else:
                    logging.debug("[pkt_fwd] %s" % tmp)

    def get_all_packets(self):
        if not self.verify_only:
            return self.packets

        conn = sqlite3.connect(os.path.join("..", lib.DB_FILE_BACKUP), timeout=60)
        conn.row_factory = sqlite3.Row

        packets_conn = conn.execute('SELECT * FROM packet WHERE TestInstID = (?) ORDER BY time',
                                    (self.schedule["TestInstID"],)).fetchall()
        conn.close()

        if not packets_conn:
            return []

        packets = []
        last_up_time = 0
        for packet in packets_conn:
            pkt = dict(packet)
            if pkt["json"]:
                pkt["json"] = json.loads(pkt["json"])

            if "error" in pkt["json"]:
                if pkt["json"]["MType"] in ["000"]:
                    if pkt["json"]["DevEui"] == self.schedule["DevEui"]:
                        packets.append(pkt)
                # else:
                #     if "DevAddr" in pkt["json"]:
                #         if pkt["json"]["DevAddr"] in dev_addrs:
                #             packets.append(pkt)
            else:
                if pkt["direction"] == "up":
                    if "Cat" in self.schedule and self.schedule["Cat"].lower() == "rf":  # RF testbench needs test information returned for validation
                        if pkt["stat"] == 1:  # dedup happens already, single stat==1 packet can be generated
                            packets.append(pkt)
                    else:
                        if pkt["time"] - last_up_time > lib.deduplication_threshold and pkt["stat"] == 0:
                            packets.append(pkt)
                    last_up_time = pkt["time"]

                if pkt["stat"] == 1 and pkt["direction"] == "down":
                    packets.append(pkt)

        packets.sort(key=operator.itemgetter("time"))

        return packets

    def save_test_result(self):
        if self.verify_only:
            state_change = False

        if not self.setup_ready:
            pass
        elif self.keyboard_interrupt:
            self.keyboard_interrupt = False
            self.schedule["Passed"] = lib.TEST_STATE['ABORTED']
            self.schedule["ErrorMsg"] = "Keyboard Interrupt!"
            logging.info("Test aborted, %s" % self.schedule['ErrorMsg'])
        elif hasattr(sys, 'last_value'):
            self.schedule['Passed'] = lib.TEST_STATE['FAILED']
            self.schedule['ErrorMsg'] = "{}: {}".format(sys.last_type.__name__, sys.last_value)
            logging.info("Test falied, %s" % self.schedule['ErrorMsg'])
        else:
            if self.verify_only:
                if self.schedule["Passed"] != lib.TEST_STATE['ABORTED']:
                    self.schedule['Passed'] = lib.TEST_STATE['PASSED']
                    self.schedule["ErrorMsg"] = None
                    state_change = True
            else:
                self.schedule['Passed'] = lib.TEST_STATE['PASSED']
                self.schedule["ErrorMsg"] = None
            logging.info("Test Succeeded!")

        self.schedule['VerificationMsg'] = json.dumps(self.veri_msg)
        if self.verify_only:
            conn = sqlite3.connect(os.path.join("..", lib.DB_FILE_BACKUP), timeout=60)
            conn.row_factory = sqlite3.Row
            if state_change:
                conn.execute('UPDATE testInstance SET Passed=(?), VerificationMsg=(?), '
                             'ErrorMsg=(?) WHERE rowid=(?)',
                             (self.schedule["Passed"], self.schedule['VerificationMsg'],
                              self.schedule["ErrorMsg"], self.schedule["TestInstID"]))
            else:
                conn.execute('UPDATE testInstance SET VerificationMsg=(?), ErrorMsg=(?) WHERE rowid=(?)',
                             (self.schedule['VerificationMsg'], self.schedule['ErrorMsg'], self.schedule["TestInstID"]))
            conn.commit()
            conn.close()
            return

        for key in ["UpdateTime", "FinishTime"]:
            if key not in self.schedule:
                self.schedule[key] = time.time()
        self.schedule["CurrentPara"] = self.packet_count

        if not self.standby:
            conn = sqlite3.connect(os.path.join("..", lib.DB_FILE_BACKUP), timeout=60)
            conn.row_factory = sqlite3.Row
            conn.execute('UPDATE testInstance SET CurrentPara=(?), UpdateTime=(?), '
                         'FinishTime=(?), Passed=(?), VerificationMsg=(?), ErrorMsg=(?), '
                         'Ready=(?) WHERE rowid=(?)',
                         (self.schedule["CurrentPara"], self.schedule["UpdateTime"],
                          self.schedule["FinishTime"], self.schedule["Passed"],
                          self.schedule["VerificationMsg"], self.schedule["ErrorMsg"],
                          lib.CACHE_STATE['GENERATING'], self.schedule["TestInstID"]))
            conn.commit()
            conn.close()

    def teardown(self):
        logging.debug("teardown is started")
#        if self.ads_process:
#            self.ads_process.terminate()
        os.system('sudo killall ads1256_driver')
        if self.fwd_process:
            self.fwd_process.terminate()
        if not self.standby:
            self.save_test_result()
        if self.conn:
            self.conn.close()
        if self.sock:
            if not self.standby:
                self.sock.sendto(bytes([0, 1, 2, lib.PROC_MSG["TC_TEARDOWN_TEST"]]), lib.addr_pf)
            self.sock.sendto(bytes([lib.PROC_MSG["TC_TEARDOWN_TEST"]]) + json.dumps(self.schedule).encode(), lib.addr_pc)
            self.sock.close()
        if self.pcap:
            self.tcp_process.terminate()
            timestamp = time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime(self.schedule['StartTime']))
            os.system("sudo mv *.pcap ../log/test_{}_{}_{}.pcap".format(self.schedule["Cat"], self.schedule["SubCat"], timestamp))

        logging.debug("teardown is finished")
#@pytest.fixture
#def chirpstack(schedule):
    #logging.debug("============================Entering chirpstack fixture===================")
    #logging.debug(schedule['DevEui'])
    #print("==============================================")
   # print(schedule['DevEui'])
   # return schedule['DevEui']

@pytest.fixture
def test_controller():
    test_controller = TestController()
    yield test_controller
    test_controller.teardown()


@pytest.fixture
def tc(test_controller, schedule):
    try:
        logging.debug("start setup")
        test_controller.config_test(schedule)
        test_controller.setup_socket()
        if not test_controller.verify_only:
            test_controller.start_misc_process()
            test_controller.power_cycle_device()
            if lib.use_internal_gateway:  # only if using internal gateway can we expect logs
                if test_controller.log_thread:
                    if not test_controller.log_thread.is_alive():
                        raise Exception(test_controller.exception_msg)
                    # if not test_controller.fwd_running:
                    #     raise Exception("Cannot start packet_forwarder properly")
            power_dir = os.path.join("..", "tmp", "power")
            logging.debug("power folder is: {}".format(power_dir))
            files = sorted(os.listdir(power_dir))
            logging.debug("files are {}".format(files))
            for file in files:
                os.remove(os.path.join(power_dir,file))
    except:
        test_controller.schedule['Passed'] = -1
        test_controller.schedule['ErrorMsg'] = "[fixture setup] {}: {}".format(sys.exc_info()[0].__name__, sys.exc_info()[1])
        logging.error("Exception %s happened during setup" % test_controller.schedule['ErrorMsg'])
        raise
    test_controller.setup_ready = True
    return test_controller


@pytest.fixture(autouse=True)
def term_handler():
    orig = signal.signal(signal.SIGTERM, signal.getsignal(signal.SIGINT))
    yield
    signal.signal(signal.SIGTERM, orig)


@pytest.hookimpl(tryfirst=True)
def pytest_keyboard_interrupt(excinfo):
    logging.debug("Keyboard interrupt is triggered, exeinfo: {}".format(excinfo))
    TestController.keyboard_interrupt = True
    pytestmark = pytest.mark.skip('Interrupted Test Session')
