#file      lib_packet.py

#brief      general packet processing functions definition

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
import sqlite3
import time
import base64
import math
import random

from lib_base import DB_FILE_PROXY
import lib_packet_command

from lib_crypto import calc_cmac, encrypt_aes, decrypt_aes, pad16, decrypt_frame_payload, calc_mic_up, calc_mic_down


def decoder_join_request(pkt, conn=None):
    new_conn = False
    if not conn:
        conn = sqlite3.connect(DB_FILE_PROXY, timeout=60)
        conn.row_factory = sqlite3.Row
        new_conn = True

    packet = {}
    phy_payload = base64.b64decode(pkt['data']).hex()
    join_request_payload = phy_payload[2:-8]
    packet['DevEui'] = join_request_payload[16:32]

    response = conn.execute("SELECT * from device WHERE devEUI = (?)", (packet['DevEui'],)).fetchone()

    if response:
        nwk_key = dict(response)['NwkKey']
    else:
        packet['error'] = 'no device key'

        if new_conn:
            conn.close()
        return packet

    packet["device"] = dict(response)
    
    packet["region"] = response["region"]

    cmac = calc_cmac(nwk_key, phy_payload[:-8])
    packet["mic"] = phy_payload[-8:]

    if cmac != packet["mic"]:
        packet['error'] = 'MIC error'

        if new_conn:
            conn.close()
        return packet

    packet['JoinEUI'] = join_request_payload[:16]
    packet['DevNonce'] = join_request_payload[32:36]

    if "error" not in packet:
        conn.execute(
            'INSERT OR REPLACE INTO session (DevEui, JoinEUI, DevNonce, JoinDelay, JoinReqType, time, region)\
             VALUES (?,?,?,?,?,?,?)',
            (packet['DevEui'], packet['JoinEUI'], packet['DevNonce'], 5, 'ff', time.time(), response["region"]))
        conn.commit()

    if new_conn:
        conn.close()
    return packet


def decode_join_accept(pkt, conn=None):
    new_conn = False
    if not conn:
        conn = sqlite3.connect(DB_FILE_PROXY, timeout=60)
        conn.row_factory = sqlite3.Row
        new_conn = True

    packet = {}
    phy_payload = base64.b64decode(pkt['data']).hex()

    response = conn.execute("SELECT *, rowid from session WHERE time>(?) and "
                            "JoinNonce is null ORDER BY time DESC LIMIT 1",
                            (time.time() - 10,)).fetchone()
    if response:
        session = dict(response)
    else:
        packet['error'] = 'no session information'

        if new_conn:
            conn.close()
        return packet

    packet['session id'] = response['rowid']
    packet["region"] = response['region']

    device = conn.execute("SELECT * from device WHERE DevEui=(?)", (session['DevEui'],)).fetchone()

    packet['DevEui'] = session['DevEui']
    packet["device"] = dict(device)

    mhdr = phy_payload[:2]
    mhdr_bin = bin(int(mhdr, 16))[2:].zfill(8)
    # m_type = mhdr_bin[:3]

    major = mhdr_bin[7]
    if major == "1":
        packet['error'] = 'mayjor bit error'

        if new_conn:
            conn.close()
        return packet

    decrypted = encrypt_aes(device['NwkKey'], phy_payload[2:])
    mic = decrypted[-8:]
    packet["mic"] = mic
    packet['JoinNonce'] = decrypted[:6]
    packet['Home_NetID'] = decrypted[6:12]
    packet['DevAddr'] = decrypted[12:20]

    dl_settings = decrypted[20:22]
    dl_settings_bin = bin(int(dl_settings, 16))[2:].zfill(8)

    packet['OptNeg'] = dl_settings_bin[0]
    packet['RX1DRoffset'] = int(dl_settings_bin[1:4], 2)
    packet['RX2DataRate'] = int(dl_settings_bin[4:8], 2)

    packet['RxDelay'] = int(decrypted[22:24], 16)
    packet['CFList'] = decrypted[24:-8]

    if packet['OptNeg'] == '0':
        packet['AppSKey'] = encrypt_aes(device['NwkKey'],
                                        pad16('02' + packet['JoinNonce'] + packet['Home_NetID'] + session['DevNonce']))
        packet['FNwkSIntKey'] = encrypt_aes(device['NwkKey'], pad16(
            '01' + packet['JoinNonce'] + packet['Home_NetID'] + session['DevNonce']))
        packet['SNwkSIntKey'] = packet['FNwkSIntKey']
        packet['NwkSEncKey'] = packet['FNwkSIntKey']

        # pldCmac = phy_payload[:2] + decrypted[:-8]
        # cmac = calCMAC(device['NwkKey'], pldCmac)
    else:
        packet['error'] = "LoRaWAN 1.1 not supported"

    if "error" not in packet:
        conn.execute('UPDATE session SET FCntUp=(?),NFCntDown=(?),AFCntDown=(?), AppSKey=(?),FNwkSIntKey=(?),'
                     'SNwkSIntKey=(?),NwkSEncKey=(?),JoinNonce=(?),Home_NetID=(?),DevAddr=(?),RxDelay=(?),'
                     'OptNeg=(?),RX1DRoffset=(?),RX2DataRate=(?), RX2Freq=(?) WHERE rowid=(?)',
                     (0, 0, 0, packet['AppSKey'], packet['FNwkSIntKey'], packet['SNwkSIntKey'], packet['NwkSEncKey'],
                      packet['JoinNonce'], packet['Home_NetID'],
                      packet['DevAddr'], packet['RxDelay'], packet['OptNeg'], packet['RX1DRoffset'],
                      packet['RX2DataRate'], 923.3, packet['session id']))

    if new_conn:
        conn.close()
    return packet


def encode_join_accept(packet, conn=None):
    new_conn = False
    if not conn:
        conn = sqlite3.connect(DB_FILE_PROXY, timeout=60)
        conn.row_factory = sqlite3.Row
        new_conn = True

    device = dict(conn.execute("SELECT * from device WHERE DevEui=(?)", (packet['DevEui'],)).fetchone())

    mhdr = "%02x" % int(packet['MType'] + '0000' + packet['Major'], 2)

    dl_settings = "%02x" % int(
        packet['OptNeg'] + bin(packet['RX1DRoffset'])[2:].zfill(3) + bin(packet['RX2DataRate'])[2:].zfill(4), 2)

    mic_cal = mhdr + packet['JoinNonce'] + packet['Home_NetID'] + packet['DevAddr'] + dl_settings + "%02x" % packet['RxDelay'] + packet['CFList']
    # packet["mic_calc"] = calc_cmac(device['NwkKey'], mic_cal)
    
    if packet["mic"] == "random":
        packet["mic"] = ('%08x' % random.randint(0, 2 ** 32 - 1)).lower()
    else:
        packet["mic"] = calc_cmac(device['NwkKey'], mic_cal)
    decrypted = packet['JoinNonce'] + packet['Home_NetID'] + packet['DevAddr'] + dl_settings + "%02x" % packet['RxDelay'] + packet['CFList'] + packet["mic"]
    encrypted = decrypt_aes(device['NwkKey'], decrypted)

    if new_conn:
        conn.close()

    print(mhdr + encrypted)
    return base64.b64encode(bytes.fromhex(mhdr + encrypted)).decode(), len(mhdr + encrypted) / 2


def encode_data(packet, conn=None):
    new_conn = False
    if not conn:
        conn = sqlite3.connect(DB_FILE_PROXY, timeout=60)
        conn.row_factory = sqlite3.Row
        new_conn = True

    mhdr = "%02x" % int(packet['MType'] + '0000' + packet['Major'], 2)

    session = conn.execute("SELECT rowid, * from session WHERE DevAddr = (?) ORDER BY time DESC LIMIT 1",
                           (packet['DevAddr'],)).fetchone()
    if not session:
        packet['error'] = 'no session information'

        if new_conn:
            conn.close()
        return None

    mac_payload = packet['DevAddr']

    if packet['MType'] == '010' or packet['MType'] == '100':  # unconfirmed/confirmed uplink
        direction = True
    else:
        direction = False

    if direction:  # unconfirmed/confirmed uplink
        if session["requireACKdown"]:
            packet['ACK'] = "1"
        else:
            packet['ACK'] = "0"
    
        f_ctrl_bin = packet['ADR'] + packet['ADRACKReq'] + packet['ACK'] + packet['ClassB']
    else:
        if session["requireACKup"]:
            packet['ACK'] = "1"
        else:
            packet['ACK'] = "0"
            
        f_ctrl_bin = packet['ADR'] + '0' + packet['ACK'] + packet['FPending']

    if "FOpts" in packet:
        f_opts = packet["FOpts"]
    else:
        f_opts = ""
    f_opts_len = int(len(f_opts) / 2)

    f_ctrl_bin += bin(f_opts_len)[2:].zfill(4)
    f_ctrl = "%02x" % int(f_ctrl_bin, 2)

    mac_payload += f_ctrl
    
    f_cnt = "%04x" % (packet["FCnt"])
    f_cnt_int = packet["FCnt"]

    f_cnt = f_cnt[2:4] + f_cnt[0:2]
    mac_payload += f_cnt
    mac_payload += f_opts

    if 'FPort' in packet and packet["FPort"] >= 0:
        if packet['FPort'] != 0:
            if direction:
                frm_payload_encrypt = decrypt_frame_payload(packet['FRMPayload'], session['AppSKey'], '00',
                                                            packet['DevAddr'], f_cnt_int)
            else:
                frm_payload_encrypt = decrypt_frame_payload(packet['FRMPayload'], session['AppSKey'], '01',
                                                            packet['DevAddr'], f_cnt_int)
        else:
            if direction:
                frm_payload_encrypt = decrypt_frame_payload(packet['FRMPayload'], session['NwkSEncKey'], '00',
                                                            packet['DevAddr'], f_cnt_int)
            else:
                frm_payload_encrypt = decrypt_frame_payload(packet['FRMPayload'], session['NwkSEncKey'], '01',
                                                            packet['DevAddr'], f_cnt_int)
        mac_payload = mac_payload + '%02x' % packet['FPort'] + frm_payload_encrypt

    phy_payload = mhdr + mac_payload
    
    
    if len(packet["mic"]) <= 8:
        if direction:
            mic = calc_mic_up(phy_payload, session['FNwkSIntKey'], packet['DevAddr'], f_cnt_int)
        else:
            mic = calc_mic_down(phy_payload, session['FNwkSIntKey'], packet['DevAddr'], f_cnt_int)
    else:
        mic = packet["mic"][:8]

    phy_payload = phy_payload + mic
    
    '''
    if direction:
        conn.execute("UPDATE session SET FCntUp=(?) WHERE rowid = (SELECT rowid FROM session WHERE DevAddr = (?) ORDER BY time DESC LIMIT 1)", (f_cnt_int, packet['DevAddr']))
    else:
        if packet["FCnt"] >= session["AFCntDown"]:
            conn.execute("UPDATE session SET AFCntDown=(?) WHERE rowid = (SELECT rowid FROM session WHERE DevAddr = (?) ORDER BY time DESC LIMIT 1)", (f_cnt_int, packet['DevAddr']))
    conn.commit()
    '''
    
    if new_conn:
        conn.close()
    return base64.b64encode(bytes.fromhex(phy_payload)).decode(), len(phy_payload) / 2


def decode_data(pkt, conn=None):
    new_conn = False
    if not conn:
        conn = sqlite3.connect(DB_FILE_PROXY, timeout=60)
        conn.row_factory = sqlite3.Row
        new_conn = True

    packet = {}

    phy_payload = base64.b64decode(pkt['data']).hex()
    mhdr = phy_payload[:2]
    mhdr_bin = bin(int(mhdr, 16))[2:].zfill(8)
    m_type = mhdr_bin[:3]

    if m_type == '010' or m_type == '100':  # unconfirmed/confirmed uplink
        direction = True
    else:
        direction = False

    mac_payload = phy_payload[2:]

    packet['DevAddr'] = mac_payload[:8]
    session = conn.execute("SELECT * from session WHERE DevAddr = (?) ORDER BY time DESC LIMIT 1",
                           (packet['DevAddr'],)).fetchone()
    if not session:
        packet['error'] = 'no session information'

        if new_conn:
            conn.close()
        return packet

    session = dict(session)

    packet['DevEui'] = session['DevEui']
    packet['region'] = session["region"]

    f_ctrl = mac_payload[8:10]
    f_ctrl_bin = bin(int(f_ctrl, 16))[2:].zfill(8)

    if direction:  # unconfirmed/confirmed uplink
        packet['ADR'] = f_ctrl_bin[0]
        packet['ADRACKReq'] = f_ctrl_bin[1]
        packet['ACK'] = f_ctrl_bin[2]
        packet['ClassB'] = f_ctrl_bin[3]
    else:
        packet['ADR'] = f_ctrl_bin[0]
        packet['ACK'] = f_ctrl_bin[2]
        packet['FPending'] = f_ctrl_bin[3]

    packet['FOptsLen'] = int(f_ctrl_bin[4:8], 2)

    f_cnt = mac_payload[10:14]
    f_cnt_int = int(f_cnt[2:4] + f_cnt[0:2], 16)
    packet['FCnt'] = f_cnt_int

    if direction:
        mic_calc = calc_mic_up(phy_payload[:-8], session['FNwkSIntKey'], packet['DevAddr'], f_cnt_int)
    else:
        mic_calc = calc_mic_down(phy_payload[:-8], session['FNwkSIntKey'], packet['DevAddr'], f_cnt_int)

    mic = mac_payload[-8:]
    packet['mic'] = mic

    if mic_calc != mic:
        packet['error'] = 'MIC error'
        packet['mic calc'] = mic_calc

        if new_conn:
            conn.close()
        return packet

    if direction:
        conn.execute("UPDATE session SET FCntUp=(?) WHERE rowid = (SELECT rowid FROM session WHERE DevAddr = (?) ORDER BY time DESC LIMIT 1)", 
        (f_cnt_int, packet['DevAddr']))
        conn.execute("UPDATE session SET requireACKup=(?) WHERE rowid = (SELECT rowid FROM session WHERE DevAddr = (?) ORDER BY time DESC LIMIT 1)", 
        (int(m_type == "100"), packet['DevAddr']))
    else:
        conn.execute("UPDATE session SET AFCntDown=(?) WHERE rowid = (SELECT rowid FROM session WHERE DevAddr = (?) ORDER BY time DESC LIMIT 1)", 
        (f_cnt_int, packet['DevAddr']))
        conn.execute("UPDATE session SET requireACKdown=(?) WHERE rowid = (SELECT rowid FROM session WHERE DevAddr = (?) ORDER BY time DESC LIMIT 1)", (int(m_type == "101"), packet['DevAddr']))
        
    conn.commit()

    packet['FOpts'] = mac_payload[14:14 + 2 * packet['FOptsLen']]

    mac_commands = packet['FOpts']

    f_port_frm_payload = mac_payload[14 + 2 * packet['FOptsLen']:-8]
    if len(f_port_frm_payload) > 0:
        f_port = f_port_frm_payload[:2]
        packet['FPort'] = int(f_port, 16)

        frm_payload = f_port_frm_payload[2:]

        if f_port != '00':
            if direction:
                decrypted = decrypt_frame_payload(frm_payload, session['AppSKey'], '00', packet['DevAddr'], f_cnt_int)
            else:
                decrypted = decrypt_frame_payload(frm_payload, session['AppSKey'], '01', packet['DevAddr'], f_cnt_int)
            packet['FRMPayload'] = decrypted
        else:
            if direction:
                decrypted = decrypt_frame_payload(frm_payload, session['NwkSEncKey'], '00', packet['DevAddr'], f_cnt_int)
            else:
                decrypted = decrypt_frame_payload(frm_payload, session['NwkSEncKey'], '01', packet['DevAddr'], f_cnt_int)
            packet['FRMPayload'] = decrypted
            if mac_commands:
                packet['error'] = "Error, FOpts and port 0 used in the same packet"
                return packet
            else:
                mac_commands = decrypted
    else:
        packet['FPort'] = -1
        packet['FRMPayload'] = ""

    packet['MAC Commands'] = lib_packet_command.MacCommandDecoder(mac_commands, direction)

    if new_conn:
        conn.close()
    return packet


def decode_uplink(pkt, conn=None):
    packet = {}

    phy_payload = base64.b64decode(pkt['data']).hex()
    mhdr = phy_payload[:2]
    mhdr_bin = bin(int(mhdr, 16))[2:].zfill(8)
    m_type = mhdr_bin[:3]

    packet['MType'] = m_type
    packet['Major'] = mhdr_bin[7]

    if m_type == '000':
        packet = {**packet, **decoder_join_request(pkt, conn)}
    else:
        if m_type == '010' or m_type == '100':
            packet = {**packet, **decode_data(pkt, conn)}
        else:
            packet["error"] = "unknown MType"

    return packet


def encode_uplink(packet, conn = None):
    #  no support for join request now, as not necessary
    if packet["MType"] in ["010", "100"]:
        return encode_data(packet, conn)
    return "", -1


def encode_downlink(packet, conn = None):
    if packet["MType"] in ["001"]:
        return encode_join_accept(packet, conn)
    if packet["MType"] in ["011", "101"]:
        return encode_data(packet, conn)
    return "", -1


def decode_downlink(pkt, conn=None):
    packet = {}

    phy_payload = base64.b64decode(pkt['data']).hex()
    mhdr = phy_payload[:2]
    mhdr_bin = bin(int(mhdr, 16))[2:].zfill(8)
    m_type = mhdr_bin[:3]

    packet['MType'] = m_type
    packet['Major'] = mhdr_bin[7]

    if m_type == '001':
        packet = {**packet, **decode_join_accept(pkt, conn)}
    else:
        if m_type == '011' or m_type == '101':
            packet = {**packet, **decode_data(pkt, conn)}
        else:
            packet["error"] = "unknown MType"
    return packet


def mac_commands(pkt, conn = None):
    packet = {}

    phy_payload = base64.b64decode(pkt['data']).hex()
    mhdr = phy_payload[:2]
    mhdr_bin = bin(int(mhdr, 16))[2:].zfill(8)
    m_type = mhdr_bin[:3]

    packet['MType'] = m_type
    packet['Major'] = mhdr_bin[7]

    if m_type == '001':
        packet = {**packet, **decode_join_accept(pkt, conn)}
    else:
        if m_type == '011' or m_type == '101':
            packet = {**packet, **decode_data(pkt, conn)}
        else:
            packet["error"] = "unknown MType"
    return packet


def mpsrange(a, b):
    '''
    Mac Payload Size range.
    return a list of [a, b], a <= arange(a,b) <= b
    '''
    a += 5  # MHDR + MIC
    b += 6  # MHDR + MIC + 1
    return range(a, b)


def get_toa(n_size, datr, enable_auto_ldro=True, enable_ldro=False,
            enable_eh=True, enable_crc=True, n_cr=1, n_preamble=8):
    datr = datr[2:].split("BW")
    n_bw = int(datr[1])
    n_sf = int(datr[0])

    r_sym = (n_bw * 1000.) / math.pow(2, n_sf)
    t_sym = 1000. / r_sym
    t_preamble = (n_preamble + 4.25) * t_sym
    # LDRO
    v_de = 0
    if enable_auto_ldro:
        if t_sym > 16:
            v_de = 1
    elif enable_ldro:
        v_de = 1
    v_ih = 0
    if not enable_eh:
        v_ih = 1
    v_crc = 1
    if enable_crc == False:
        v_crc = 0
    a = 8. * n_size - 4. * n_sf + 28 + 16 * v_crc - 20. * v_ih
    b = 4. * (n_sf - 2. * v_de)
    v_ceil = a / b
    n_payload = 8 + max(math.ceil(a / b) * (n_cr + 4), 0)
    t_payload = n_payload * t_sym
    t_packet = t_preamble + t_payload

    ret = {}
    ret["r_sym"] = r_sym
    ret["t_sym"] = t_sym
    ret["n_preamble"] = n_preamble
    ret["t_preamble"] = t_preamble
    ret["v_DE"] = v_de
    ret["v_ceil"] = v_ceil
    ret["n_sym_payload"] = n_payload
    ret["t_payload"] = t_payload
    ret["t_packet"] = t_packet

    return ret["t_packet"]/1000
