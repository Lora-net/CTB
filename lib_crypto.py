#file      lib_crypto.py

#brief      encryption/decryption functions definition

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

from Crypto.Hash import CMAC
from Crypto.Cipher import AES
import numpy as np


def calc_cmac(key, data):
    cmac = CMAC.new(bytes.fromhex(key), ciphermod=AES).update(bytes.fromhex(data))

    return cmac.hexdigest()[:8]


def encrypt_aes(key, data):
    encryptor = AES.new(bytes.fromhex(key), AES.MODE_CBC, IV=bytes.fromhex('00000000000000000000000000000000'))
    return encryptor.encrypt(bytes.fromhex(data)).hex()


def decrypt_aes(key, data):
    #encryptor = AES.new(bytes.fromhex(key), AES.MODE_CBC, IV=bytes.fromhex('00000000000000000000000000000000'))
    encryptor = AES.new(bytes.fromhex(key), AES.MODE_ECB)
    return encryptor.decrypt(bytes.fromhex(data)).hex()


def pad16(data):
    length = int(np.ceil(len(data)/32))*32
    for i in range(length-len(data)):
        data = data + '0'
    return data


def get_fcnt_string(cnt):
    return bytes(reversed(bytes.fromhex('%08x' % int(cnt)))).hex()


def decrypt_frame_payload(frm_payload, key, direction, dev_addr, f_cnt):
    k = int(np.ceil(len(frm_payload) / 32))
    s = ''
    for i in range(k):
        s = s + encrypt_aes(key, '01' + '00000000' + direction + dev_addr + get_fcnt_string(f_cnt) + '00' +
                            '%02x' % (i + 1))
    decrypted = ''
    for i in range(len(frm_payload)):
        decrypted = decrypted + '%1x' % (int(s[i], 16) ^ int(frm_payload[i], 16))
    return decrypted


def calc_mic_up(msg, key, dev_addr, f_cnt_int):
    b0 = '49' + '00000000' + '00' + dev_addr + get_fcnt_string(f_cnt_int) + '00' + '%02x' % int(len(msg) / 2)
    mic = calc_cmac(key, b0 + msg)
    return mic


def calc_mic_down(msg, key, dev_addr, f_cnt_int, conf_f_cnt='00'):
    b0 = '49' + get_fcnt_string(conf_f_cnt)[:4] + '0000' + '01' + dev_addr + get_fcnt_string(f_cnt_int) + '00' + \
         '%02x' % int(len(msg) / 2)
    mic = calc_cmac(key, b0 + msg)
    return mic
