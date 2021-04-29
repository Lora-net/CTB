#file      lib_packet.py

#brief      general packet processing functions definition

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
import logging

from lib_base import DB_FILE_PROXY
import lib_packet_command

from lib_crypto import calc_cmac, encrypt_aes, decrypt_aes, pad16, decrypt_frame_payload, calc_mic_up, calc_mic_down


class Codec:
    def __init__(self, conn, test_inst_id, device=None):
        self.conn = conn
        self.test_inst_id = test_inst_id
        self.device = device
        self.sessions = []
        self.session = {}


    def decode_join_request(self, pkt):
        packet = {}
        phy_payload = base64.b64decode(pkt['data']).hex()
        join_request_payload = phy_payload[2:-8]
        packet['DevEui'] = join_request_payload[16:32]

        if not self.device or packet["DevEui"] != self.device["DevEui"]:
            logging.warning("DevEui {} is not the device under test".format(packet["DevEui"]))
            packet["error"] = 'no device key'
            return packet

        packet["device"] = self.device

        packet["region"] = self.device["region"]

        cmac = calc_cmac(self.device["NwkKey"], phy_payload[:-8])
        packet["mic"] = phy_payload[-8:]

        if cmac != packet["mic"]:
            packet['error'] = 'MIC error'
            return packet

        packet['JoinEUI'] = join_request_payload[:16]
        packet['DevNonce'] = join_request_payload[32:36]

        if 'error' not in packet:
            self.session = {}
            self.session['DevEui'] = packet['DevEui']
            self.session['JoinEUI'] = packet['JoinEUI']
            self.session['DevNonce'] = packet['DevNonce']
            self.session['JoinDelay'] = 5
            self.session['JoinReqType'] = 'ff'
            self.session['time'] = time.time()
            self.session['region'] = self.device['region']
            self.sessions.append(self.session)
            self.add_session()
            logging.debug("new session: {}".format(self.session))

        return packet


    def decode_join_accept(self, pkt):
        packet = {}
        phy_payload = base64.b64decode(pkt['data']).hex()

        if 'DevNonce' not in self.session or 'JoinNonce' in self.session:
            packet['error'] = 'no session information'
            return packet

        packet["region"] = self.session['region']
        packet['DevEui'] = self.session['DevEui']
        packet["device"] = self.device

        mhdr = phy_payload[:2]
        mhdr_bin = bin(int(mhdr, 16))[2:].zfill(8)

        major = mhdr_bin[7]
        if major == "1":
            packet['error'] = 'mayjor bit error'
            return packet

        decrypted = encrypt_aes(self.device['NwkKey'], phy_payload[2:])
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
            packet['AppSKey'] = encrypt_aes(self.device['NwkKey'],
                                            pad16('02' + packet['JoinNonce'] + packet['Home_NetID'] + self.session['DevNonce']))
            packet['FNwkSIntKey'] = encrypt_aes(self.device['NwkKey'], pad16(
                '01' + packet['JoinNonce'] + packet['Home_NetID'] + self.session['DevNonce']))
            packet['SNwkSIntKey'] = packet['FNwkSIntKey']
            packet['NwkSEncKey'] = packet['FNwkSIntKey']

            # pldCmac = phy_payload[:2] + decrypted[:-8]
            # cmac = calCMAC(device['NwkKey'], pldCmac)
        else:
            packet['error'] = "LoRaWAN 1.1 not supported"
            return packet

        if 'error' not in packet:
            self.session['FCntUp'] = 0
            self.session['NFCntDown'] = 0
            self.session['AFCntDown'] = 0
            for key in ['AppSKey', 'FNwkSIntKey', 'SNwkSIntKey', 'NwkSEncKey', 'JoinNonce',
                        'Home_NetID', 'DevAddr', 'RxDelay', 'OptNeg', 'RX1DRoffset', 'RX2DataRate']:
                self.session[key] = packet[key]
            self.session['RX2Freq'] = 923.3
            self.update_session()
            logging.debug("update session: {}".format(self.session))
        return packet


    def encode_join_accept(self, packet):
        mhdr = "%02x" % int(packet['MType'] + '0000' + packet['Major'], 2)

        dl_settings = "%02x" % int(
            packet['OptNeg'] + bin(packet['RX1DRoffset'])[2:].zfill(3) + bin(packet['RX2DataRate'])[2:].zfill(4), 2)

        mic_cal = mhdr + packet['JoinNonce'] + packet['Home_NetID'] + packet['DevAddr'] + dl_settings + "%02x" % packet['RxDelay'] + packet['CFList']

        if packet["mic"] == "random":
            packet["mic"] = ('%08x' % random.randint(0, 2 ** 32 - 1)).lower()
        else:
            packet["mic"] = calc_cmac(self.device['NwkKey'], mic_cal)
        decrypted = packet['JoinNonce'] + packet['Home_NetID'] + packet['DevAddr'] + dl_settings + "%02x" % packet['RxDelay'] + packet['CFList'] + packet["mic"]
        encrypted = decrypt_aes(self.device['NwkKey'], decrypted)

        print(mhdr + encrypted)
        return base64.b64encode(bytes.fromhex(mhdr + encrypted)).decode(), len(mhdr + encrypted) // 2


    def encode_data(self, packet):
        mhdr = "%02x" % int(packet['MType'] + '0000' + packet['Major'], 2)

        if self.session['DevAddr'] != packet['DevAddr']:
            packet['error'] = 'no session information'
            return None

        mac_payload = packet['DevAddr']

        if packet['MType'] == '010' or packet['MType'] == '100':  # unconfirmed/confirmed uplink
            direction = True
        else:
            direction = False

        if direction:  # unconfirmed/confirmed uplink
            if "requireACKdown" in self.session and  self.session["requireACKdown"]:
                packet['ACK'] = "1"
            else:
                packet['ACK'] = "0"

            f_ctrl_bin = packet['ADR'] + packet['ADRACKReq'] + packet['ACK'] + packet['ClassB']
        else:
            if "requireACKup" in self.session and self.session["requireACKup"]:
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
                    frm_payload_encrypt = decrypt_frame_payload(packet['FRMPayload'], self.session['AppSKey'], '00',
                                                                packet['DevAddr'], f_cnt_int)
                else:
                    frm_payload_encrypt = decrypt_frame_payload(packet['FRMPayload'], self.session['AppSKey'], '01',
                                                                packet['DevAddr'], f_cnt_int)
            else:
                if direction:
                    frm_payload_encrypt = decrypt_frame_payload(packet['FRMPayload'], self.session['NwkSEncKey'], '00',
                                                                packet['DevAddr'], f_cnt_int)
                else:
                    frm_payload_encrypt = decrypt_frame_payload(packet['FRMPayload'], self.session['NwkSEncKey'], '01',
                                                                packet['DevAddr'], f_cnt_int)
            mac_payload = mac_payload + '%02x' % packet['FPort'] + frm_payload_encrypt

        phy_payload = mhdr + mac_payload


        if len(packet["mic"]) <= 8:
            if direction:
                mic = calc_mic_up(phy_payload, self.session['FNwkSIntKey'], packet['DevAddr'], f_cnt_int)
            else:
                mic = calc_mic_down(phy_payload, self.session['FNwkSIntKey'], packet['DevAddr'], f_cnt_int)
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
        # needs to return size as int to work with ChirpStack
        return base64.b64encode(bytes.fromhex(phy_payload)).decode(), len(phy_payload) // 2 


    def decode_data(self, pkt):
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
        if 'DevAddr' not in self.session or not self.session['DevAddr']:
            packet['error'] = 'no session information'
            return packet

        packet['DevEui'] = self.session['DevEui']
        packet['region'] = self.session["region"]

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
            mic_calc = calc_mic_up(phy_payload[:-8], self.session['FNwkSIntKey'], packet['DevAddr'], f_cnt_int)
        else:
            mic_calc = calc_mic_down(phy_payload[:-8], self.session['FNwkSIntKey'], packet['DevAddr'], f_cnt_int)

        mic = mac_payload[-8:]
        packet['mic'] = mic

        if mic_calc != mic:
            packet['error'] = 'MIC error'
            packet['mic calc'] = mic_calc
            return packet

        if direction:
            self.session['FCntUp'] = f_cnt_int
            self.session['requireACKup'] = int(m_type == "100")
        else:
            self.session['FCntDown'] = f_cnt_int
            self.session['requireACKdown'] = int(m_type == "101")
        self.update_count(direction)

        packet['FOpts'] = mac_payload[14:14 + 2 * packet['FOptsLen']]

        mac_commands = packet['FOpts']

        f_port_frm_payload = mac_payload[14 + 2 * packet['FOptsLen']:-8]
        if len(f_port_frm_payload) > 0:
            f_port = f_port_frm_payload[:2]
            packet['FPort'] = int(f_port, 16)

            frm_payload = f_port_frm_payload[2:]

            if f_port != '00':
                if direction:
                    decrypted = decrypt_frame_payload(frm_payload, self.session['AppSKey'], '00', packet['DevAddr'], f_cnt_int)
                else:
                    decrypted = decrypt_frame_payload(frm_payload, self.session['AppSKey'], '01', packet['DevAddr'], f_cnt_int)
                packet['FRMPayload'] = decrypted
            else:
                if direction:
                    decrypted = decrypt_frame_payload(frm_payload, self.session['NwkSEncKey'], '00', packet['DevAddr'], f_cnt_int)
                else:
                    decrypted = decrypt_frame_payload(frm_payload, self.session['NwkSEncKey'], '01', packet['DevAddr'], f_cnt_int)
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

        return packet

    def decode_uplink(self, pkt):
        packet = {}

        phy_payload = base64.b64decode(pkt['data']).hex()
        mhdr = phy_payload[:2]
        mhdr_bin = bin(int(mhdr, 16))[2:].zfill(8)
        m_type = mhdr_bin[:3]

        packet['MType'] = m_type
        packet['Major'] = mhdr_bin[7]

        if m_type == '000':
            packet = {**packet, **self.decode_join_request(pkt)}
        else:
            if m_type == '010' or m_type == '100':
                packet = {**packet, **self.decode_data(pkt)}
            else:
                packet["error"] = "unknown MType"

        return packet


    def encode_uplink(self, packet):
        #  no support for join request now, as not necessary
        if packet["MType"] in ["010", "100"]:
            return self.encode_data(packet)
        return "", -1


    def encode_downlink(self, packet):
        if packet["MType"] in ["001"]:
            return self.encode_join_accept(packet)
        if packet["MType"] in ["011", "101"]:
            return self.encode_data(packet)
        return "", -1


    def decode_downlink(self, pkt):
        packet = {}

        phy_payload = base64.b64decode(pkt['data']).hex()
        mhdr = phy_payload[:2]
        mhdr_bin = bin(int(mhdr, 16))[2:].zfill(8)
        m_type = mhdr_bin[:3]

        packet['MType'] = m_type
        packet['Major'] = mhdr_bin[7]

        if m_type == '001':
            packet = {**packet, **self.decode_join_accept(pkt)}
        else:
            if m_type == '011' or m_type == '101':
                packet = {**packet, **self.decode_data(pkt)}
            else:
                packet["error"] = "unknown MType"
        return packet


    def mac_commands(self, pkt):
        packet = {}

        phy_payload = base64.b64decode(pkt['data']).hex()
        mhdr = phy_payload[:2]
        mhdr_bin = bin(int(mhdr, 16))[2:].zfill(8)
        m_type = mhdr_bin[:3]

        packet['MType'] = m_type
        packet['Major'] = mhdr_bin[7]

        if m_type == '001':
            packet = {**packet, **self.decode_join_accept(pkt)}
        else:
            if m_type == '011' or m_type == '101':
                packet = {**packet, **self.decode_data(pkt)}
            else:
                packet["error"] = "unknown MType"
        return packet


    def add_session(self):
        self.session['rowid'] = \
        self.conn.execute(
            'INSERT OR REPLACE INTO session (TestInstID, JoinEUI, DevNonce, JoinDelay, JoinReqType, time)\
            VALUES (?,?,?,?,?,?)',
            (self.test_inst_id, self.session['JoinEUI'], self.session['DevNonce'],
             self.session['JoinDelay'], self.session['JoinReqType'], self.session['time'])).lastrowid
        self.conn.commit()


    def update_session(self):
        self.conn.execute('UPDATE session SET FCntUp=(?),NFCntDown=(?),AFCntDown=(?), AppSKey=(?),FNwkSIntKey=(?),'
                          'SNwkSIntKey=(?),NwkSEncKey=(?),JoinNonce=(?),Home_NetID=(?),DevAddr=(?),RxDelay=(?),'
                          'OptNeg=(?),RX1DRoffset=(?),RX2DataRate=(?), RX2Freq=(?) WHERE rowid=(?)',
                          (self.session['FCntUp'], self.session['NFCntDown'], self.session['AFCntDown'],
                           self.session['AppSKey'], self.session['FNwkSIntKey'], self.session['SNwkSIntKey'],
                           self.session['NwkSEncKey'], self.session['JoinNonce'], self.session['Home_NetID'],
                           self.session['DevAddr'], self.session['RxDelay'], self.session['OptNeg'],
                           self.session['RX1DRoffset'], self.session['RX2DataRate'], self.session['RX2Freq'],
                           self.session['rowid']))
        self.conn.commit()


    def update_count(self, direction):
        if direction:
            self.conn.execute("UPDATE session SET FCntUp=(?) WHERE rowid = (?)",
            (self.session['FCntUp'], self.session['rowid']))
        else:
            self.conn.execute("UPDATE session SET AFCntDown=(?) WHERE rowid = (?)",
            (self.session['FCntUp'], self.session['rowid']))
        self.conn.commit()


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
