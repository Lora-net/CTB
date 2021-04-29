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
import lib_base as lib
from lib_base import GW_ID


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

deveui=request.config.getoption("--deveui")
#deveui = "00137A1000003F82" #schedule["DevEUI"]
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

def networkservice_eu():
    ns_eu = subprocess.Popen(["chirpstack-network-server", "-c", "/home/pi/chirpstack_ns_EU/chirpstack-network-server.toml"], stdout=subprocess.PIPE)
    time.sleep(10)
            
@pytest.fixture
def chirpstack_EU():
 
    nscreated=False
    networkservice_eu()
    #ns_eu = subprocess.Popen(["chirpstack-network-server", "-c", "/home/pi/chirpstack_ns_EU/chirpstack-network-server.toml"], stdout=subprocess.PIPE)
    jwt= requests.post("http://localhost:8080/api/internal/login", headers={'Content-Type': 'application/json', 'Accept': 'application/json'}, data= json.dumps({"email": "admin","password": "admin"} ))
    if jwt.status_code == http_response_ok:
    
        header['Grpc-Metadata-Authorization']= 'Bearer ' + jwt.json()["jwt"]
        logging.info("Beginning creation of chisrpstack services")
        for count in range(9):            
            time.sleep(1)
            logging.debug("Creating NS, attempt number {}".format(count+1))
            createns = requests.post(nsURL, headers = header, data =json.dumps(nsdata))
            if createns.status_code==http_response_ok:
                nscreated=True
                logging.debug("Network server created")
                break
           
        if nscreated==False:
            logging.error("Timeout(10s): Network server could not be created correctly, please retry")
            print("http response:",createns) 
            os.system("sudo pkill chirpstack-netw")
            ns_eu.poll()
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
    ns_eu.poll()
    print(ns_eu.returncode)
        
def networkservice_us():
    ns_us = subprocess.Popen(["chirpstack-network-server", "-c", "/home/pi/chirpstack_ns_US/chirpstack-network-server.toml"], stdout=subprocess.PIPE)   
    time.sleep(10)

@pytest.fixture
def chirpstack_US():
    nscreated=False
    networkservice_eu()
    #ns_us = subprocess.Popen(["chirpstack-network-server", "-c", "/home/pi/chirpstack_ns_US/chirpstack-network-server.toml"], stdout=subprocess.PIPE)
    jwt= requests.post("http://localhost:8080/api/internal/login", headers={'Content-Type': 'application/json', 'Accept': 'application/json'}, data= json.dumps({"email": "admin","password": "admin"} ))
    if jwt.status_code == http_response_ok:
    
        header['Grpc-Metadata-Authorization']= 'Bearer ' + jwt.json()["jwt"]
        logging.info("Beginning creation of chisrpstack services")
        for count in range(9):            
            time.sleep(1)
            logging.debug("Creating NS, attempt number {}".format(count+1))
            createns = requests.post(nsURL, headers = header, data =json.dumps(nsdata))
            if createns.status_code==http_response_ok:
                nscreated=True
                logging.debug("Network server created")
                break
           
        if nscreated==False:
            logging.error("Timeout(10s): Network server could not be created correctly, please retry")
            print("http response:",createns) 
            os.system("sudo pkill chirpstack-netw")
            ns_eu.poll()
            print("Network server process status: ",ns_eu.returncode)
            raise Exception("Network server creation timeout, please retry")
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
    print("Killing network server process")
    os.system("sudo pkill chirpstack-netw")
    ns_us.poll()
    print(ns_us.returncode)
