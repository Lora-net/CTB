#file      ext_sequence.py

#brief      test sequences definitions

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
# -*- coding: utf-8 -*-
"""
Created on Mon Oct 15 17:24:14 2018

@author: flu
"""
import time
import random
import logging
import numpy as np

from lib_base import datrLUTrev, datrLUT
from lib_packet_command import MacCommandDecoder

def sequence_test_activate(pkt, conn=None):
    if pkt["json"]["MType"] in ["000", "001"]:
        return pkt
    
    if pkt["json"]["MType"] in ["010", "100"]:
        pkt["json"]["MType"] = "100"
        pkt["size"] = -1
        return pkt

    if pkt["json"]["MType"] in ["011", "101"]:
        pkt["json"]["FPort"] = 224
        pkt["json"]["FRMPayload"] = "01010101"
        pkt["size"] = -1

    conn.execute(
        "UPDATE schedule SET FinishTime=(?) WHERE rowid = (?)",
        (time.time(), pkt["test"]['rowid']))
    conn.commit()
    return pkt


def sequence_join_cflist(pkt, conn=None):
    if pkt["json"]["MType"] == "000":
        return pkt
    
    if pkt["json"]["MType"] == "001":
        conn.execute("UPDATE schedule SET CurrentPara=CurrentPara+1 WHERE rowid = (?)", (pkt["test"]['rowid'],))
        conn.commit()

        if pkt["json"]["region"] == "EU":
            pkt["json"]["CFList"] = pkt["test"]["Config"]["Channel"]
            for _ in range(4):
                pkt["json"]["CFList"] += "000000"
            pkt["json"]["CFList"] += "00"
            pkt["size"] = -1
            return pkt

    conn.execute(
        "UPDATE schedule SET FinishTime=(?) WHERE rowid = (?)",
        (time.time(), pkt["test"]['rowid']))
    conn.commit()
    return pkt


def sequence_join_deny(pkt, conn=None):
    if pkt["json"]["MType"] == "000":
        return pkt
    if pkt["json"]["MType"] == "001":
        conn.execute("UPDATE schedule SET CurrentPara=CurrentPara+1 WHERE rowid = (?)", (pkt["test"]['rowid'],))
        conn.commit()
        return None

    conn.execute(
        "UPDATE schedule SET FinishTime=(?) WHERE rowid = (?)",
        (time.time(), pkt["test"]['rowid']))
    conn.commit()

    return pkt


def sequence_join_mic(pkt, conn=None):
    if pkt["json"]["MType"] == "000":
        return pkt
    if pkt["json"]["MType"] == "001":
        conn.execute("UPDATE schedule SET CurrentPara=CurrentPara+1 WHERE rowid = (?)", (pkt["test"]['rowid'],))
        conn.commit()
        pkt["json"]["mic"] = "random"
        pkt["size"] = -1
        return pkt

    conn.execute(
        "UPDATE schedule SET FinishTime=(?) WHERE rowid = (?)",
        (time.time(), pkt["test"]['rowid']))
    conn.commit()

    return pkt


def sequence_join_rx2(pkt, conn=None):
    if pkt["json"]["MType"] == "000":
        return pkt
    if pkt["json"]["MType"] == "001":
        conn.execute("UPDATE schedule SET CurrentPara=CurrentPara+1 WHERE rowid = (?)", (pkt["test"]['rowid'],))
        conn.commit()

        if pkt["json"]["region"] == "US":
            pkt["tmst"] += 1000000
            pkt["datr"] = "SF12BW500"
            pkt["freq"] = 923.3
        if pkt["json"]["region"] == "EU":
            pkt["tmst"] += 1000000
            pkt["datr"] = "SF12BW125"
            pkt["freq"] = 869.525
        return pkt

    conn.execute(
        "UPDATE schedule SET FinishTime=(?) WHERE rowid = (?)",
        (time.time(), pkt["test"]['rowid']))
    conn.commit()

    return pkt


def sequence_normal_normal(pkt, conn=None):
    if pkt["json"]["MType"] in ["000", "010", "100"]:
        conn.execute("UPDATE schedule SET CurrentPara=CurrentPara+1 WHERE rowid = (?)", (pkt["test"]['rowid'],))
        conn.commit()

        try:
            pkt["rssi"] -= pkt["test"]["Config"]["Attn_rssi"]
            pkt["lsnr"] -= pkt["test"]["Config"]["Attn_lsnr"]
        except KeyError:
            pass
        
        try:
            pkt["rssi"] = pkt["test"]["Config"]["Set_rssi"]
            pkt["lsnr"] = pkt["test"]["Config"]["Set_lsnr"]
        except KeyError:
            pass
    
    return pkt


def sequence_normal_per(pkt, conn=None):
    if pkt["json"]["MType"] in ["000", "010", "100"]:
        conn.execute("UPDATE schedule SET CurrentPara=CurrentPara+1 WHERE rowid = (?)", (pkt["test"]['rowid'],))
        conn.commit()

        if random.random() > pkt["test"]["Config"]["Up"] / 100.0:
            return pkt
        else:
            return None
    if pkt["json"]["MType"] in ["001", "011", "101"]:        

        if random.random() > pkt["test"]["Config"]["Down"] / 100.0:
            return pkt
        else:
            return None
            
    return pkt
    
    
def sequence_normal_block(pkt, conn=None):
    if pkt["json"]["MType"] in ["000", "010", "100"]:
        conn.execute("UPDATE schedule SET CurrentPara=CurrentPara+1 WHERE rowid = (?)", (pkt["test"]['rowid'],))
        conn.commit()

    if str(pkt["freq"]) in pkt["test"]["Config"]:
        if random.random() > pkt["test"]["Config"][str(pkt["freq"])] / 100.0:
            return pkt
        else:
            return None
    else:   
        return pkt


def sequence_normal_no_mac(pkt, conn=None):
    if pkt["json"]["MType"] in ["000", "001"]:
        return pkt

    if pkt["json"]["MType"] in ["010", "100"]:
        conn.execute("UPDATE schedule SET CurrentPara=CurrentPara+1 WHERE rowid = (?)", (pkt["test"]['rowid'],))
        conn.commit()
        return pkt

    if pkt["json"]["MType"] in ["011", "101"]:
        pkt["size"] = -1
        if pkt["json"]["FPort"] == 0:
            pkt["json"]["FPort"] = -1
            pkt["json"]["FRMPayload"] = ""
            
        pkt["json"]["MAC Commands"] = []
        pkt["json"]["FOpts"] = ""

        return pkt


def sequence_downlink_freq(pkt, conn=None):
    if pkt["json"]["MType"] in ["000", "001"]:
        return pkt

    if pkt["json"]["MType"] in ["010", "100"]:
        conn.execute("UPDATE schedule SET CurrentPara=CurrentPara+1 WHERE rowid = (?)", (pkt["test"]['rowid'],))
        conn.commit()

        pkt["json"]["MType"] = "100"
        pkt["size"] = -1
        return pkt

    if pkt["json"]["MType"] in ["011", "101"]:
        offset_index = np.floor((pkt["test"]["CurrentPara"] - 1) / pkt["test"]["Parameter"] * 11 + 1e-8)
        if offset_index > 5:
            offset_index -= 11

        pkt["test"]["offset"] = offset_index * pkt["test"]["Config"]["Step"] / 1000

        pkt["json"]["MType"] = "101"
        pkt["freq"] += pkt["test"]["offset"]

        if "FPort" in pkt["test"]["Config"]:
            pkt["json"]["FPort"] = pkt["test"]["Config"]["FPort"]
            pkt["json"]["FRMPayload"] = ('%08x' % random.randint(0, 2 ** 32 - 1)).lower()
        
        if pkt["datr"] != datrLUTrev[pkt["json"]["region"]][min([pkt["test"]["Config"]["Datr"] + 10, 13])]:
            pkt["json"]["MAC Commands"] = [{"NbTrans": 0, "DataRate": pkt["test"]["Config"]["Datr"], "TXPower": 0,
                                            "ChMask": "1111111100000000", "Command": "LinkADRReq", "ChMaskCntl": 0}]
            pkt["json"]["FOpts"] = "03%x0ff0000" % pkt["test"]["Config"]["Datr"]
        else:
            pkt["json"]["MAC Commands"] = []
            pkt["json"]["FOpts"] = ""

        pkt["size"] = -1

        return pkt


def sequence_downlink_rx2(pkt, conn=None):
    if pkt["json"]["MType"] == "000":
        return pkt
    if pkt["json"]["MType"] == "001":
        return pkt

    if pkt["json"]["MType"] in ["010", "100"]:
        conn.execute("UPDATE schedule SET CurrentPara=CurrentPara+1 WHERE rowid = (?)", (pkt["test"]['rowid'],))
        conn.commit()

        pkt["json"]["MType"] = "100"
        pkt["size"] = -1
        return pkt

    if pkt["json"]["MType"] in ["011", "101"]:
        pkt["tmst"] += 1000000
        pkt["datr"] = "SF12BW500"
        pkt["freq"] = 923.3
        return pkt


def sequence_downlink_timing(pkt, conn=None):
    if pkt["json"]["MType"] in ["000", "001"]:
        return pkt

    if pkt["json"]["MType"] in ["010", "100"]:
        conn.execute("UPDATE schedule SET CurrentPara=CurrentPara+1 WHERE rowid = (?)", (pkt["test"]['rowid'],))
        conn.commit()

        pkt["json"]["MType"] = "100"
        pkt["size"] = -1
        return pkt
    if pkt["json"]["MType"] in ["011", "101"]:
        offset_index = np.floor((pkt["test"]["CurrentPara"] - 1) / pkt["test"]["Parameter"] * 11 + 1e-8)
        if offset_index > 5:
            offset_index -= 11

        pkt["test"]["offset"] = offset_index * pkt["test"]["Config"]["Step"] * 1000

        pkt["json"]["MType"] = "101"
        pkt["tmst"] += int(pkt["test"]["offset"])

        if "FPort" in pkt["test"]["Config"]:
            pkt["json"]["FPort"] = pkt["test"]["Config"]["FPort"]
            pkt["json"]["FRMPayload"] = ('%08x' % random.randint(0, 2 ** 32 - 1)).lower()

        if pkt["datr"] != datrLUTrev[pkt["json"]["region"]][min([pkt["test"]["Config"]["Datr"] + 10, 13])]:
            pkt["json"]["MAC Commands"] = [{"NbTrans": 0, "DataRate": pkt["test"]["Config"]["Datr"], "TXPower": 0,
                                            "ChMask": "1111111100000000", "Command": "LinkADRReq", "ChMaskCntl": 0}]
            pkt["json"]["FOpts"] = "03%x0ff0000" % pkt["test"]["Config"]["Datr"]
        else:
            pkt["json"]["MAC Commands"] = []
            pkt["json"]["FOpts"] = ""

        pkt["size"] = -1

        return pkt


def sequence_downlink_confirmed(pkt, conn=None):
    if pkt["json"]["MType"] in ["000", "001"]:
        return pkt

    if pkt["json"]["MType"] in ["010", "100"]:
        conn.execute("UPDATE schedule SET CurrentPara=CurrentPara+1 WHERE rowid = (?)", (pkt["test"]['rowid'],))
        conn.commit()

        pkt["json"]["MType"] = "100"
        pkt["size"] = -1
        return pkt

    if pkt["json"]["MType"] in ["011", "101"]:
        pkt["json"]["MType"] = "101"
        pkt["size"] = -1
        return pkt


def sequence_downlink_cnt(pkt, conn=None):
    if pkt["json"]["MType"] in ["000", "001"]:
        return pkt

    if pkt["json"]["MType"] in ["010", "100"]:
        conn.execute("UPDATE schedule SET CurrentPara=CurrentPara+1 WHERE rowid = (?)", (pkt["test"]['rowid'],))
        conn.commit()

        pkt["json"]["MType"] = "100"
        pkt["size"] = -1
        return pkt

    if pkt["json"]["MType"] in ["011", "101"]:
        pkt["json"]["MType"] = "101"
        if "FPort" in pkt["test"]["Config"]:
            pkt["json"]["FPort"] = pkt["test"]["Config"]["FPort"]
            pkt["json"]["FRMPayload"] = ('%08x' % random.randint(0, 2 ** 32 - 1)).lower()

        pkt["json"]["FCnt"] = max([0, random.randint(0, pkt["json"]["FCnt"] - pkt["test"]["CurrentPara"] - 1)])
        pkt["size"] = -1
        return pkt
        
        
def sequence_downlink_mic(pkt, conn=None):
    if pkt["json"]["MType"] in ["000", "001"]:
        return pkt

    if pkt["json"]["MType"] in ["010", "100"]:
        conn.execute("UPDATE schedule SET CurrentPara=CurrentPara+1 WHERE rowid = (?)", (pkt["test"]['rowid'],))
        conn.commit()

        pkt["json"]["MType"] = "100"
        pkt["size"] = -1
        return pkt

    if pkt["json"]["MType"] in ["011", "101"]:
        pkt["json"]["MType"] = "101"
        pkt["json"]["mic"] = ('%08x' % random.randint(0, 2 ** 32 - 1)).lower() + "00"
        pkt["size"] = -1
        return pkt
        
        
def sequence_mac_payload(pkt, conn=None):
    if pkt["json"]["MType"] in ["000", "001"]:
        return pkt

    if pkt["json"]["MType"] in ["010", "100"]:
        conn.execute("UPDATE schedule SET CurrentPara=CurrentPara+1 WHERE rowid = (?)", (pkt["test"]['rowid'],))
        conn.commit()

        pkt["json"]["MType"] = "100"
        pkt["size"] = -1
        return pkt

    if pkt["json"]["MType"] in ["011", "101"]:
        pkt["json"]["MAC Commands"] = [{"Command": "DevStatusReq"}]
        
        pkt["json"]["FOpts"] = ""
        pkt["json"]["FPort"] = 0
        pkt["json"]["FRMPayload"] = "06"
        pkt["size"] = -1
        return pkt


def sequence_mac_general(pkt, conn=None):
    if pkt["json"]["MType"] in ["000", "001"]:
        return pkt

    if pkt["json"]["MType"] in ["010", "100"]:
        conn.execute("UPDATE schedule SET CurrentPara=CurrentPara+1 WHERE rowid = (?)", (pkt["test"]['rowid'],))
        conn.commit()
        if pkt["test"]["CurrentPara"] == 0:
            pkt["json"]["MType"] = "100"
            pkt["size"] = -1
        return pkt

    if pkt["json"]["MType"] in ["011", "101"]:
        if pkt["test"]["CurrentPara"] == 1:
            pkt["json"]["MAC Commands"] = []
            pkt["json"]["FOpts"] = pkt["test"]["Config"]["Command"]
            pkt["json"]["MAC Commands"] = MacCommandDecoder(pkt["test"]["Config"]["Command"], 0)
            pkt["size"] = -1
        return pkt

    return pkt

def sequence_mac_mask_125(pkt, conn=None):
    if pkt["json"]["MType"] in ["000", "001"]:
        return pkt

    pkt["json"]["MAC Commands"] = []
    pkt["json"]["FOpts"] = ""
    if pkt["json"]["FPort"] == 0:
        pkt["json"]["FPort"] = -1
    pkt["size"] = -1

    if pkt["json"]["MType"] in ["010", "100"]:
        conn.execute("UPDATE schedule SET CurrentPara=CurrentPara+1 WHERE rowid = (?)", (pkt["test"]['rowid'],))
        conn.commit()
        if pkt["test"]["CurrentPara"] in [0, pkt["test"]["Parameter"] / 2]:
            pkt["json"]["MType"] = "100"
        return pkt

    if pkt["json"]["MType"] in ["011", "101"]:
        if pkt["json"]["region"] == "US":
            dr = datrLUT[pkt["json"]["region"]]["down"][pkt["datr"]] - 10
            if pkt["test"]["CurrentPara"] == 1:
                pkt["json"]["MAC Commands"] = [{"NbTrans": 0, "DataRate": dr, "TXPower": 0, "ChMask": "0000111100000000",
                                                "Command": "LinkADRReq", "ChMaskCntl": 0}]
                pkt["json"]["FOpts"] = "03%x00f0000" % dr
            if pkt["test"]["CurrentPara"] == pkt["test"]["Parameter"] / 2 + 1:
                pkt["json"]["MAC Commands"] = [{"NbTrans": 0, "DataRate": 0, "TXPower": 0, "ChMask": "1111111100000000",
                                                "Command": "LinkADRReq", "ChMaskCntl": 0}]
                pkt["json"]["FOpts"] = "03%x0ff0000" % dr
        if pkt["json"]["region"] == "EU":
            dr = datrLUT[pkt["json"]["region"]]["down"][pkt["datr"]]
            if pkt["test"]["CurrentPara"] == 1:
                pkt["json"]["MAC Commands"] = [{"NbTrans": 0, "DataRate": dr, "TXPower": 0, "ChMask": "0000000100000000",
                                                "Command": "LinkADRReq", "ChMaskCntl": 0}]
                pkt["json"]["FOpts"] = "03%x0010000" % dr
            if pkt["test"]["CurrentPara"] == pkt["test"]["Parameter"] / 2 + 1:
                pkt["json"]["MAC Commands"] = [{"NbTrans": 0, "DataRate": 0, "TXPower": 0, "ChMask": "00000011100000000",
                                                "Command": "LinkADRReq", "ChMaskCntl": 0}]
                pkt["json"]["FOpts"] = "03%x0070000" % dr
        return pkt


def sequence_mac_mask_500(pkt, conn=None):
    if pkt["json"]["MType"] in ["000", "001"]:
        return pkt

    pkt["json"]["MAC Commands"] = []
    pkt["json"]["FOpts"] = ""
    if pkt["json"]["FPort"] == 0:
        pkt["json"]["FPort"] = -1
    pkt["size"] = -1

    if pkt["json"]["MType"] in ["010", "100"]:
        conn.execute("UPDATE schedule SET CurrentPara=CurrentPara+1 WHERE rowid = (?)", (pkt["test"]['rowid'],))
        conn.commit()
        if pkt["test"]["CurrentPara"] in [0, pkt["test"]["Parameter"] / 2]:
            pkt["json"]["MType"] = "100"
        return pkt

    if pkt["json"]["MType"] in ["011", "101"]:
        if pkt["json"]["region"] == "US":
            if pkt["test"]["CurrentPara"] == 1:
                pkt["json"]["MAC Commands"] = [{"NbTrans": 0, "DataRate": 4, "TXPower": 0, "ChMask": "0000000100000000",
                                                "Command": "LinkADRReq", "ChMaskCntl": 7}]
                pkt["json"]["FOpts"] = "0340010070"
            if pkt["test"]["CurrentPara"] == pkt["test"]["Parameter"] / 2 + 1:
                pkt["json"]["MAC Commands"] = [{"NbTrans": 0, "DataRate": 0, "TXPower": 0, "ChMask": "1111111100000000",
                                                "Command": "LinkADRReq", "ChMaskCntl": 0}]
                pkt["json"]["FOpts"] = "0300ff0000"
            return pkt


def sequence_mac_status(pkt, conn=None):
    logging.debug("sequence_mac_status")
    if pkt["json"]["MType"] in ["000", "001"]:
        return pkt

    pkt["json"]["MAC Commands"] = []
    pkt["json"]["FOpts"] = ""
    if pkt["json"]["FPort"] == 0:
        pkt["json"]["FPort"] = -1
    pkt["size"] = -1

    if pkt["json"]["MType"] in ["010", "100"]:
        conn.execute("UPDATE schedule SET CurrentPara=CurrentPara+1 WHERE rowid = (?)", (pkt["test"]['rowid'],))
        conn.commit()
        pkt["json"]["MType"] = "100"
        return pkt

    if pkt["json"]["MType"] in ["011", "101"]:
        pkt["json"]["MAC Commands"] = [{"Command": "DevStatusReq", "DevStatusReq": None}]
        pkt["json"]["FOpts"] = "06"
        return pkt


def sequence_mac_tx_power(pkt, conn=None):
    if pkt["json"]["MType"] in ["000", "001"]:
        return pkt

    pkt["json"]["MAC Commands"] = []
    pkt["json"]["FOpts"] = ""
    if pkt["json"]["FPort"] == 0:
        pkt["json"]["FPort"] = -1
    pkt["size"] = -1

    if pkt["json"]["MType"] in ["010", "100"]:
        conn.execute("UPDATE schedule SET CurrentPara=CurrentPara+1 WHERE rowid = (?)", (pkt["test"]['rowid'],))
        conn.commit()
        if pkt["test"]["CurrentPara"] % (pkt["test"]["Parameter"] / 6) == 0:
            pkt["json"]["MType"] = "100"
        return pkt

    if pkt["json"]["MType"] in ["011", "101"]:
        if (pkt["test"]["CurrentPara"] - 1) % (pkt["test"]["Parameter"] / 6) == 0:
            pkt["test"]["power_index"] = np.floor((pkt["test"]["CurrentPara"] - 1 + 1e-8) /
                                                  (pkt["test"]["Parameter"] / 6)) * 2
            if pkt["test"]["power_index"] == 10:
                pkt["test"]["power_index"] = 0

            if pkt["json"]["region"] == "US":
                dr = datrLUT[pkt["json"]["region"]]["down"][pkt["datr"]] - 10
                pkt["json"]["MAC Commands"] = [{"NbTrans": 0, "DataRate": dr,
                                                "TXPower": pkt["test"]["power_index"],
                                                "ChMask": "1111111100000000", "Command": "LinkADRReq", "ChMaskCntl": 0}]
                pkt["json"]["FOpts"] = "03%x%xff0000" % (dr, int(pkt["test"]["power_index"]))
            if pkt["json"]["region"] == "EU":
                dr = datrLUT[pkt["json"]["region"]]["down"][pkt["datr"]] - 0
                pkt["json"]["MAC Commands"] = [{"NbTrans": 0, "DataRate": dr,
                                                "TXPower": pkt["test"]["power_index"],
                                                "ChMask": "0000011100000000", "Command": "LinkADRReq", "ChMaskCntl": 0}]
                pkt["json"]["FOpts"] = "03%x%x070000" % (dr, int(pkt["test"]["power_index"]))
        return pkt


def sequence_mac_dr(pkt, conn=None):
    if pkt["json"]["MType"] in ["000", "001"]:
        return pkt

    pkt["json"]["MAC Commands"] = []
    pkt["json"]["FOpts"] = ""
    if pkt["json"]["FPort"] == 0:
        pkt["json"]["FPort"] = -1
    pkt["size"] = -1
    

    if pkt["json"]["MType"] in ["010", "100"]:
        conn.execute("UPDATE schedule SET CurrentPara=CurrentPara+1 WHERE rowid = (?)", (pkt["test"]['rowid'],))
        conn.commit()
        if pkt["test"]["CurrentPara"] in [0, pkt["test"]["Parameter"] / 2]:
            pkt["json"]["MType"] = "100"
        return pkt

    if pkt["json"]["MType"] in ["011", "101"]:
        if pkt["json"]["region"] == "US":
            if pkt["test"]["CurrentPara"] == 1:
                pkt["json"]["MAC Commands"] = [{"NbTrans": 0, "DataRate": 3, "TXPower": 0, "ChMask": "1111111100000000",
                                                "Command": "LinkADRReq", "ChMaskCntl": 0}]
                pkt["json"]["FOpts"] = "0330ff0000"
            if pkt["test"]["CurrentPara"] == pkt["test"]["Parameter"] / 2 + 1:
                pkt["json"]["MAC Commands"] = [{"NbTrans": 0, "DataRate": 0, "TXPower": 0, "ChMask": "1111111100000000",
                                                "Command": "LinkADRReq", "ChMaskCntl": 0}]
                pkt["json"]["FOpts"] = "0300ff0000"
        if pkt["json"]["region"] == "EU":
            if pkt["test"]["CurrentPara"] == 1:
                pkt["json"]["MAC Commands"] = [{"NbTrans": 0, "DataRate": 3, "TXPower": 0, "ChMask": "0000011100000000",
                                                "Command": "LinkADRReq", "ChMaskCntl": 0}]
                pkt["json"]["FOpts"] = "0330070000"
            if pkt["test"]["CurrentPara"] == pkt["test"]["Parameter"] / 2 + 1:
                pkt["json"]["MAC Commands"] = [{"NbTrans": 0, "DataRate": 0, "TXPower": 0, "ChMask": "0000011100000000",
                                                "Command": "LinkADRReq", "ChMaskCntl": 0}]
                pkt["json"]["FOpts"] = "0300070000"
        return pkt


def sequence_mac_redundancy(pkt, conn=None):
    if pkt["json"]["MType"] in ["000", "001"]:
        return pkt

    pkt["json"]["MAC Commands"] = []
    pkt["json"]["FOpts"] = ""
    if pkt["json"]["FPort"] == 0:
        pkt["json"]["FPort"] = -1
    pkt["size"] = -1

    if pkt["json"]["MType"] in ["010", "100"]:
        conn.execute("UPDATE schedule SET CurrentPara=CurrentPara+1 WHERE rowid = (?)", (pkt["test"]['rowid'],))
        conn.commit()
        if pkt["test"]["CurrentPara"] in [0, pkt["test"]["Parameter"] / 2]:
            pkt["json"]["MType"] = "100"
        return pkt

    if pkt["json"]["MType"] in ["011", "101"]:
        if pkt["json"]["region"] == "US":
            dr = datrLUT[pkt["json"]["region"]]["down"][pkt["datr"]] - 10
            if pkt["test"]["CurrentPara"] == 1:
                pkt["json"]["MAC Commands"] = [{"NbTrans": 3, "DataRate": dr, "TXPower": 0,
                                                "ChMask": "1111111100000000",
                                                "Command": "LinkADRReq", "ChMaskCntl": 0}]
                pkt["json"]["FOpts"] = "03%x0ff0003" % dr
                return pkt
            if pkt["test"]["CurrentPara"] == pkt["test"]["Parameter"] / 2 + 1:
                pkt["json"]["MAC Commands"] = [{"NbTrans": 0, "DataRate": dr, "TXPower": 0,
                                                "ChMask": "1111111100000000",
                                                "Command": "LinkADRReq", "ChMaskCntl": 0}]
                pkt["json"]["FOpts"] = "03%x0ff0000" % dr
                return pkt
        if pkt["json"]["region"] == "EU":
            dr = datrLUT[pkt["json"]["region"]]["down"][pkt["datr"]] - 10
            if pkt["test"]["CurrentPara"] == 1:
                pkt["json"]["MAC Commands"] = [{"NbTrans": 3, "DataRate": dr, "TXPower": 0,
                                                "ChMask": "0000011100000000",
                                                "Command": "LinkADRReq", "ChMaskCntl": 0}]
                pkt["json"]["FOpts"] = "03%x0070003" % dr
                return pkt
            if pkt["test"]["CurrentPara"] == pkt["test"]["Parameter"] / 2 + 1:
                pkt["json"]["MAC Commands"] = [{"NbTrans": 0, "DataRate": dr, "TXPower": 0,
                                                "ChMask": "0000011100000000",
                                                "Command": "LinkADRReq", "ChMaskCntl": 0}]
                pkt["json"]["FOpts"] = "03%x0070000" % dr
                return pkt
        return None


def sequence_mac_rx_para_rx1dro(pkt, conn=None):
    if pkt["json"]["MType"] in ["000", "001"]:
        return pkt

    pkt["json"]["MAC Commands"] = []
    pkt["json"]["FOpts"] = ""
    if pkt["json"]["FPort"] == 0:
        pkt["json"]["FPort"] = -1
    pkt["size"] = -1

    if pkt["json"]["MType"] in ["010", "100"]:
        conn.execute("UPDATE schedule SET CurrentPara=CurrentPara+1 WHERE rowid = (?)", (pkt["test"]['rowid'],))
        conn.commit()
        pkt["json"]["MType"] = "100"
        return pkt

    if pkt["json"]["MType"] in ["011", "101"]:
        pkt["json"]["MType"] = "101"
        if "FPort" in pkt["test"]["Config"]:
            pkt["json"]["FPort"] = pkt["test"]["Config"]["FPort"]
            pkt["json"]["FRMPayload"] = ('%08x' % random.randint(0, 2 ** 32 - 1)).lower()

        if pkt["json"]["region"] == "US":
            if pkt["test"]["CurrentPara"] == 1:
                pkt["json"]["MAC Commands"] = [{"RX1DRoffset": 3,
                                                "RX2DataRate": 8,
                                                "Frequency": 9233000,
                                                "Command": "RXParamSetupReq"}]
                pkt["json"]["FOpts"] = "053868E28C"
            if pkt["test"]["CurrentPara"] == pkt["test"]["Parameter"] / 2 + 1:
                pkt["json"]["MAC Commands"] = [{"RX1DRoffset": 0,
                                                "RX2DataRate": 8,
                                                "Frequency": 9233000,
                                                "Command": "RXParamSetupReq"}]
                pkt["json"]["FOpts"] = "050868E28C"
            if 1 < pkt["test"]["CurrentPara"] <= pkt["test"]["Parameter"] / 2 + 1:
                pkt["datr"] = \
                    datrLUTrev[pkt["json"]["region"]][max([datrLUT[pkt["json"]["region"]]["down"][pkt["datr"]] - 3, 8])]
        if pkt["json"]["region"] == "EU":
            if pkt["test"]["CurrentPara"] == 1:
                pkt["json"]["MAC Commands"] = [{"RX1DRoffset": 3,
                                                "RX2DataRate": 0,
                                                "Frequency": 8695250,
                                                "Command": "RXParamSetupReq"}]
                pkt["json"]["FOpts"] = "0530D2AD84"
            if pkt["test"]["CurrentPara"] == pkt["test"]["Parameter"] / 2 + 1:
                pkt["json"]["MAC Commands"] = [{"RX1DRoffset": 0,
                                                "RX2DataRate": 0,
                                                "Frequency": 8695250,
                                                "Command": "RXParamSetupReq"}]
                pkt["json"]["FOpts"] = "0500D2AD84"
            if 1 < pkt["test"]["CurrentPara"] <= pkt["test"]["Parameter"] / 2 + 1:
                pkt["datr"] = \
                    datrLUTrev[pkt["json"]["region"]][max([datrLUT[pkt["json"]["region"]]["down"][pkt["datr"]] - 3, 0])]

        return pkt


def sequence_mac_rx_para_rx2dr(pkt, conn=None):
    if pkt["json"]["MType"] in ["000", "001"]:
        return pkt

    pkt["json"]["MAC Commands"] = []
    pkt["json"]["FOpts"] = ""
    if pkt["json"]["FPort"] == 0:
        pkt["json"]["FPort"] = -1
    pkt["size"] = -1

    if pkt["json"]["MType"] in ["010", "100"]:
        conn.execute("UPDATE schedule SET CurrentPara=CurrentPara+1 WHERE rowid = (?)", (pkt["test"]['rowid'],))
        conn.commit()
        pkt["json"]["MType"] = "100"
        return pkt

    if pkt["json"]["MType"] in ["011", "101"]:
        pkt["json"]["MType"] = "101"
        if "FPort" in pkt["test"]["Config"]:
            pkt["json"]["FPort"] = pkt["test"]["Config"]["FPort"]
            pkt["json"]["FRMPayload"] = ('%08x' % random.randint(0, 2 ** 32 - 1)).lower()

        if pkt["json"]["region"] == "US":
            if pkt["test"]["CurrentPara"] == 1:
                pkt["json"]["MAC Commands"] = [{"RX1DRoffset": 0,
                                                "RX2DataRate": 13,
                                                "Frequency": 9233000,
                                                "Command": "RXParamSetupReq"}]
                pkt["json"]["FOpts"] = "050D68E28C"
            if pkt["test"]["CurrentPara"] == pkt["test"]["Parameter"] / 2 + 1:
                pkt["json"]["MAC Commands"] = [{"RX1DRoffset": 0,
                                                "RX2DataRate": 8,
                                                "Frequency": 9233000,
                                                "Command": "RXParamSetupReq"}]
                pkt["json"]["FOpts"] = "050868E28C"

            pkt["freq"] = 923.3
            pkt["tmst"] += 1000000
            if 1 < pkt["test"]["CurrentPara"] <= (pkt["test"]["Parameter"] / 2 + 1):
                pkt["datr"] = datrLUTrev[pkt["json"]["region"]][13]
            else:
                pkt["datr"] = datrLUTrev[pkt["json"]["region"]][8]
        if pkt["json"]["region"] == "EU":
            if pkt["test"]["CurrentPara"] == 1:
                pkt["json"]["MAC Commands"] = [{"RX1DRoffset": 0,
                                                "RX2DataRate": 6,
                                                "Frequency": 8695250,
                                                "Command": "RXParamSetupReq"}]
                pkt["json"]["FOpts"] = "0506D2AD84"
            if pkt["test"]["CurrentPara"] == pkt["test"]["Parameter"] / 2 + 1:
                pkt["json"]["MAC Commands"] = [{"RX1DRoffset": 0,
                                                "RX2DataRate": 0,
                                                "Frequency": 8695250,
                                                "Command": "RXParamSetupReq"}]
                pkt["json"]["FOpts"] = "0500D2AD84"

            pkt["freq"] = 869.25
            pkt["tmst"] += 1000000
            if 1 < pkt["test"]["CurrentPara"] <= (pkt["test"]["Parameter"] / 2 + 1):
                pkt["datr"] = datrLUTrev[pkt["json"]["region"]][6]
            else:
                pkt["datr"] = datrLUTrev[pkt["json"]["region"]][0]
        return pkt


def sequence_mac_rx_para_rx2freq(pkt, conn=None):
    if pkt["json"]["MType"] in ["000", "001"]:
        return pkt

    pkt["json"]["MAC Commands"] = []
    pkt["json"]["FOpts"] = ""
    if pkt["json"]["FPort"] == 0:
        pkt["json"]["FPort"] = -1
    pkt["size"] = -1

    if pkt["json"]["MType"] in ["010", "100"]:
        conn.execute("UPDATE schedule SET CurrentPara=CurrentPara+1 WHERE rowid = (?)", (pkt["test"]['rowid'],))
        conn.commit()
        pkt["json"]["MType"] = "100"
        return pkt

    if pkt["json"]["MType"] in ["011", "101"]:
        pkt["json"]["MType"] = "101"
        if "FPort" in pkt["test"]["Config"]:
            pkt["json"]["FPort"] = pkt["test"]["Config"]["FPort"]
            pkt["json"]["FRMPayload"] = ('%08x' % random.randint(0, 2 ** 32 - 1)).lower()

        if pkt["json"]["region"] == "US":
            if pkt["test"]["CurrentPara"] == 1:
                pkt["json"]["MAC Commands"] = [{"RX1DRoffset": 0,
                                                "RX2DataRate": 8,
                                                "Frequency": 9239000,
                                                "Command": "RXParamSetupReq"}]
                pkt["json"]["FOpts"] = "0508D8F98C"
            if pkt["test"]["CurrentPara"] == pkt["test"]["Parameter"] / 2 + 1:
                pkt["json"]["MAC Commands"] = [{"RX1DRoffset": 0,
                                                "RX2DataRate": 8,
                                                "Frequency": 9233000,
                                                "Command": "RXParamSetupReq"}]
                pkt["json"]["FOpts"] = "050868E28C"

            pkt["tmst"] += 1000000
            pkt["datr"] = datrLUTrev[pkt["json"]["region"]][8]
            if 1 < pkt["test"]["CurrentPara"] <= (pkt["test"]["Parameter"] / 2 + 1):
                pkt["freq"] = 923.9
            else:
                pkt["freq"] = 923.3
        if pkt["json"]["region"] == "EU":
            if pkt["test"]["CurrentPara"] == 1:
                pkt["json"]["MAC Commands"] = [{"RX1DRoffset": 0,
                                                "RX2DataRate": 0,
                                                "Frequency": 8681000,
                                                "Command": "RXParamSetupReq"}]
                pkt["json"]["FOpts"] = "0500287684"
            if pkt["test"]["CurrentPara"] == pkt["test"]["Parameter"] / 2 + 1:
                pkt["json"]["MAC Commands"] = [{"RX1DRoffset": 0,
                                                "RX2DataRate": 0,
                                                "Frequency": 8695250,
                                                "Command": "RXParamSetupReq"}]
                pkt["json"]["FOpts"] = "0500D2AD84"

            pkt["tmst"] += 1000000
            pkt["datr"] = datrLUTrev[pkt["json"]["region"]][8]
            if 1 < pkt["test"]["CurrentPara"] <= (pkt["test"]["Parameter"] / 2 + 1):
                pkt["freq"] = 923.9
            else:
                pkt["freq"] = 923.3

        return pkt


def sequence_mac_rx_timing(pkt, conn=None):
    if pkt["json"]["MType"] in ["000", "001"]:
        return pkt

    pkt["json"]["MAC Commands"] = []
    pkt["json"]["FOpts"] = ""
    
    if pkt["json"]["FPort"] == 0:
        pkt["json"]["FPort"] = -1
    
    pkt["size"] = -1

    if pkt["json"]["MType"] in ["010", "100"]:
        conn.execute("UPDATE schedule SET CurrentPara=CurrentPara+1 WHERE rowid = (?)", (pkt["test"]['rowid'],))
        conn.commit()
        pkt["json"]["MType"] = "100"
        return pkt

    if pkt["json"]["MType"] in ["011", "101"]:
        pkt["json"]["MType"] = "101"
        if "FPort" in pkt["test"]["Config"]:
            pkt["json"]["FPort"] = pkt["test"]["Config"]["FPort"]
            pkt["json"]["FRMPayload"] = ('%08x' % random.randint(0, 2 ** 32 - 1)).lower()

        if pkt["test"]["CurrentPara"] == 1:
            pkt["json"]["MAC Commands"] = [{"Del": 3,
                                            "Command": "RXTimingSetupReq"}]
            pkt["json"]["FOpts"] = "0803"
        if pkt["test"]["CurrentPara"] == pkt["test"]["Parameter"] / 2 + 1:
            pkt["json"]["MAC Commands"] = [{"Del": 1,
                                            "Command": "RXTimingSetupReq"}]
            pkt["json"]["FOpts"] = "0801"

        if 1 < pkt["test"]["CurrentPara"] <= (pkt["test"]["Parameter"] / 2 + 1):
            pkt["tmst"] += 2000000

        return pkt
