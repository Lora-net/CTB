#file      lib_db.py

#brief      database funtions definition

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

import sqlite3
import os
import logging
import numpy as np


from lib_base import DB_FILE_PROXY, DB_FILE_BACKUP, DB_FILE_CONTROLLER, DB_FILE_PM, log_time, POWER_FOLDER



def create_db_tables_proxy():
    for DB_FILE in [DB_FILE_PROXY, DB_FILE_BACKUP]:
        conn = sqlite3.connect(DB_FILE, timeout=60)
        conn.row_factory = sqlite3.Row

        conn.execute("CREATE TABLE IF NOT EXISTS device (DevEui TEXT PRIMARY KEY, AppKey TEXT, NwkKey TEXT, "
                     "region TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS session (DevEui TEXT, JoinEUI TEXT, DevNonce TEXT, JSEncKey TEXT, "
                     "JSIntKey TEXT, FNwkSIntKey TEXT, SNwkSIntKey TEXT, NwkSEncKey TEXT, AppSKey TEXT, "
                     "JoinNonce TEXT, Home_NetID TEXT, DevAddr TEXT, FCntUp INTEGER,  NFCntDown INTEGER, "
                     "AFCntDown INTEGER, RX1DRoffset INTEGER, RX2DataRate INTEGER, RxDelay INTEGER, JoinDelay REAL, "
                     "RX2Freq REAL, OptNeg TEXT, time REAL, JoinReqType TEXT, region TEXT, requireACKup INTEGER, requireACKdown INTEGER, "
                     "UNIQUE(DevEui, DevNonce))")
        conn.execute("CREATE TABLE IF NOT EXISTS packet (tmst INTEGER, chan INTEGER, rfch INTEGER, freq REAL, "
                     "stat INTEGER, modu TEXT, datr TEXT, codr TEXT, lsnr REAL, rssi INTEGER, fdev REAL, powe INTEGER, "
                     "prea INTEGER, size INTEGER, data TEXT, time REAL, direction TEXT, json TEXT, test TEXT, "
                     "toa REAL, UNIQUE (time))")
        conn.execute("CREATE INDEX IF NOT EXISTS packet_time ON packet(time)")
        conn.execute("CREATE TABLE IF NOT EXISTS delay (token TEXT, time_gen REAL, time_ack REAL, dst TEXT, UNIQUE (time_gen, token))")
        conn.execute("CREATE INDEX IF NOT EXISTS delay_time ON delay(time_gen)")
        conn.commit()
        conn.close()


def create_db_tables_tc():
    for DB_FILE in [DB_FILE_CONTROLLER, DB_FILE_BACKUP]:
        conn = sqlite3.connect(DB_FILE, timeout=60)
        conn.row_factory = sqlite3.Row

        conn.execute("CREATE TABLE IF NOT EXISTS schedule (DevEui TEXT, Cat TEXT, SubCat TEXT, Criteria TEXT, "
                     "Parameter INTEGER, CurrentPara INTEGER, Config TEXT, AddTime real, StartTime real, "
                     "FinishTime real, UpdateTime real, Passed INTEGER, Ready INTEGER, UNIQUE(DevEui, AddTime))")
        conn.commit()
        conn.close()


def create_db_tables_pm():
    conn = sqlite3.connect(DB_FILE_PM, timeout=60)
    conn.execute("CREATE TABLE IF NOT EXISTS power (time INTEGER, average INTEGER, max INTEGER, duration INTEGER, value BLOB, UNIQUE (time, duration))")
    conn.execute("CREATE INDEX IF NOT EXISTS power_time_duration ON power(time, duration)")
    conn.commit()
    conn.close()


def backup_db_tc():
    if not os.path.exists(DB_FILE_CONTROLLER):
        return
    if not os.path.exists(DB_FILE_BACKUP):
        create_db_tables_tc()
        
    conn_src = sqlite3.connect(DB_FILE_CONTROLLER, timeout=60)
    conn_dst = sqlite3.connect(DB_FILE_BACKUP, timeout=60)


    logging.debug("Start controller db backup")
    count = {"schedule": 12}

    for table in ["schedule"]:
        data = conn_src.execute("SELECT * FROM " + table).fetchall()
        conn_dst.execute("DELETE FROM " + table)
        conn_dst.commit()
        conn_dst.executemany("INSERT OR REPLACE INTO "+table+" VALUES (" + "?,"*count[table] + "?)", data)
        conn_dst.commit()

    logging.debug("done controller db backup")
    
    conn_src.close()
    conn_dst.close()


def recover_db_tc():
    if not os.path.exists(DB_FILE_CONTROLLER):
        create_db_tables_tc()
        
    if not os.path.exists(DB_FILE_BACKUP):
        return
        
    logging.debug("start controller db recover")
    
    conn_src = sqlite3.connect(DB_FILE_BACKUP, timeout=60)
    conn_dst = sqlite3.connect(DB_FILE_CONTROLLER, timeout=60)

    count = {"schedule": 12}
    
    for table in ["schedule"]:
        data = conn_src.execute("SELECT * FROM " + table).fetchall()
        conn_dst.execute("DELETE FROM " + table)
        conn_dst.commit()
        conn_dst.executemany("INSERT OR REPLACE INTO " + table + " VALUES (" + "?," * count[table] + "?)", data)
    conn_dst.commit()
    
    conn_dst.execute("VACUUM")
    conn_dst.commit()
    
    conn_dst.close()
    conn_src.close()
    logging.debug("done controller db recover")


def backup_db_proxy():
    if not os.path.exists(DB_FILE_PROXY):
        return
    if not os.path.exists(DB_FILE_BACKUP):
        create_db_tables_proxy()
    
    conn_src = sqlite3.connect(DB_FILE_PROXY, timeout=60)
    conn_dst = sqlite3.connect(DB_FILE_BACKUP, timeout=60)

    logging.debug("start proxy db backup")

    count = {"packet": 19,
             "session": 25,
             "delay": 3,
             "device": 3}

    data = {}
    for table in ["packet", "session", "delay", "device"]:
        data[table] = conn_src.execute("SELECT rowid, * FROM " + table).fetchall()
        if table in ["packet", "delay"]:
            conn_src.executemany("DELETE FROM " + table + " WHERE rowid = (?)", [(p[0], ) for p in data[table]])
        conn_src.commit()
    
    logging.debug("done proxy db reading")
    
    for table in ["packet", "session", "delay", "device"]:
        if table in ["device", "session"]:
            conn_dst.execute("DELETE FROM " + table)
        conn_dst.executemany("INSERT OR REPLACE INTO "+table+" VALUES (" + "?,"*count[table] + "?)",
                             [(p[1:]) for p in data[table]])
    conn_dst.commit()
    
    conn_src.execute("vacuum")
    conn_src.commit()

    logging.debug("done proxy db writing")
    
    conn_dst.close()
    conn_src.close()


def recover_db_proxy():
    if not os.path.exists(DB_FILE_PROXY):
        create_db_tables_proxy()
        
    if not os.path.exists(DB_FILE_BACKUP):
        return
        
    logging.debug("start db proxy recover")
    conn_src = sqlite3.connect(DB_FILE_BACKUP, timeout=60)
    conn_dst = sqlite3.connect(DB_FILE_PROXY, timeout=60)

    count = {"packet": 19,
             "session": 25,
             "delay": 3,
             "device": 3}

    for table in ["session", "device"]:
        data = conn_src.execute("SELECT * FROM " + table).fetchall()
        conn_dst.executemany("INSERT OR REPLACE INTO "+table+" VALUES (" + "?,"*count[table] + "?)", data)
    
    conn_dst.commit()
    conn_dst.close()
    conn_src.close()
    logging.debug("done db proxy recover")


def backup_db_pm():

    logging.debug("start power db backup")

    if not os.path.exists(DB_FILE_PM):
        create_db_tables_pm()
    files = reversed(sorted(os.listdir(POWER_FOLDER)))

    last_file = True
    
    data_insert = []
    
    conn = sqlite3.connect(DB_FILE_PM, timeout=60)
    conn.row_factory = sqlite3.Row
    
    for file in files:
        if last_file:
            last_file = False
            continue
            
        src = POWER_FOLDER + file
        
        with open(src, "rb") as f:
            bytes = f.read()
            
            logging.debug(file + " " + str(len(bytes)))
            currents = [int.from_bytes(bytes[i:i+4], byteorder='little', signed = True) for i in range(0, len(bytes), 4)]
            
            
            if currents:
                avg = int(np.mean(currents))
                max_current = max(currents)
                data_insert.append((int(file[:-4]), avg, max_current, 1, bytes))
            
        os.remove(src)
            
    conn.executemany("INSERT OR REPLACE INTO power (time,average,max,duration,value) VALUES (?,?,?,?,?)", data_insert)
    conn.commit()
    
    step = 60
    
    start_time = conn.execute("SELECT MAX(time) FROM power WHERE duration = (?)", (step,)).fetchone()["MAX(time)"]
    if not start_time:
        start_time = conn.execute("SELECT MIN(time) FROM power WHERE duration = (?)", (1, )).fetchone()["MIN(time)"]
    else:
        start_time += step
    
    end_time = conn.execute("SELECT MAX(time) FROM power WHERE duration = (?)", (1, )).fetchone()["MAX(time)"]
    
    if end_time:
        end_time -= step
    
        data_insert = []
        for time in range(start_time, end_time, step):
            avg = conn.execute('SELECT AVG(average) FROM power WHERE duration=1 AND time >= (?) AND time < (?)', (time, time + step)).fetchone()["AVG(average)"]            
            
            if avg:
                peak = conn.execute('SELECT MAX(max) FROM power WHERE duration=1 AND time > (?) AND time < (?)', (time, time + step)).fetchone()["MAX(max)"]
                data_insert.append((time, int(avg), peak, step))
            
        conn.executemany("INSERT OR REPLACE INTO power (time,average,max,duration) VALUES (?,?,?,?)", data_insert)
        conn.commit()
    
    logging.debug("done power db backup")

    conn.close()
    return
