#file      lib_db.py

#brief      database funtions definition

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

import sqlite3
import os, sys
import logging
import numpy as np
import threading


from lib_base import DB_FILE_PROXY, DB_FILE_BACKUP, DB_FILE_CONTROLLER, log_time, POWER_FOLDER, \
    deduplication_threshold, CACHE_STATE


TABLES = {
    'testInstance': {
        'sql': ("CREATE TABLE IF NOT EXISTS testInstance (TestInstID INTEGER PRIMARY KEY, "
                "DevEui TEXT, BenchID TEXT NOT NULL, Cat TEXT, SubCat TEXT, Criteria TEXT, "
                "Parameter INTEGER, CurrentPara INTEGER, Config TEXT, AddTime real, StartTime real NOT NULL, "
                "FinishTime real, UpdateTime real, Passed INTEGER, VerificationMsg TEXT, "
                "ErrorMsg TEXT, Ready INTEGER, Operator TEXT, Comments TEXT, Picture BLOB, "
                "UNIQUE(BenchID, StartTime) ON CONFLICT IGNORE)"),
        'nKeys': 20,
        'has_link': True,
        'linked_table': ('session', 'packet', 'delay', 'power'),
        'primary_key': 'TestInstID',
        'unique_key': ('BenchID', 'StartTime')
    },
    'device': {
        'sql': ("CREATE TABLE IF NOT EXISTS device (DevEui TEXT PRIMARY KEY NOT NULL UNIQUE ON CONFLICT IGNORE, "
                "SkuID INTEGER REFERENCES regionSKU (SkuID) NOT NULL, AppEui TEXT, AppKey TEXT, NwkKey TEXT)"),
        'nKeys': 5
    },
    'session': {
        'sql': ("CREATE TABLE IF NOT EXISTS session (SessionID INTEGER PRIMARY KEY, "
                "TestInstID INTEGER REFERENCES testInstance (TestInstID) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL, "
                "JoinEUI TEXT, DevNonce TEXT, JSEncKey TEXT, "
                "JSIntKey TEXT, FNwkSIntKey TEXT, SNwkSIntKey TEXT, NwkSEncKey TEXT, AppSKey TEXT, "
                "JoinNonce TEXT, Home_NetID TEXT, DevAddr TEXT, FCntUp INTEGER,  NFCntDown INTEGER, "
                "AFCntDown INTEGER, RX1DRoffset INTEGER, RX2DataRate INTEGER, RxDelay INTEGER, JoinDelay REAL, "
                "RX2Freq REAL, OptNeg TEXT, time REAL NOT NULL, JoinReqType TEXT, "
                "UNIQUE(TestInstID, time) ON CONFLICT IGNORE)"),
        'nKeys': 24
    },
    'packet': {
        'sql': ("CREATE TABLE IF NOT EXISTS packet (packetID  INTEGER PRIMARY KEY, "
                "TestInstID INTEGER REFERENCES testInstance (TestInstID) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL, "
                "tmst INTEGER, chan INTEGER, rfch INTEGER, freq REAL, "
                "stat INTEGER, modu TEXT, datr TEXT, codr TEXT, lsnr REAL, rssi INTEGER, fdev REAL, powe INTEGER, "
                "prea INTEGER, size INTEGER, data TEXT, time REAL NOT NULL, direction TEXT, json TEXT, "
                "toa REAL, UNIQUE (TestInstID, time)  ON CONFLICT IGNORE)"),
        'nKeys': 21
    },
    'delay': {
        'sql': ("CREATE TABLE IF NOT EXISTS delay (delayID INTEGER PRIMARY KEY, "
                "TestInstID INTEGER REFERENCES testInstance (TestInstID) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL, "
                "token TEXT, time_gen REAL NOT NULL, time_ack REAL, "
                "dst TEXT, UNIQUE (TestInstID, time_gen) ON CONFLICT IGNORE)"),
        'nKeys': 6
    },
    'power': {
        'sql': ("CREATE TABLE IF NOT EXISTS power (powerID INTEGER PRIMARY KEY, "
                "TestInstID INTEGER REFERENCES testInstance (TestInstID) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL, "
                "time INTEGER NOT NULL, average INTEGER, "
                "max INTEGER, duration INTEGER, value BLOB, UNIQUE (TestInstID, time, duration) ON CONFLICT IGNORE)"),
        'nKeys': 7
    },
    'vendor': {
        'sql': ("CREATE TABLE IF NOT EXISTS vendor (VendorID INTEGER PRIMARY KEY, "
                "CompanyName TEXT NOT NULL UNIQUE ON CONFLICT IGNORE, "
                "Address TEXT, PostalCode TEXT, "
                "City TEXT, Country TEXT, URL TEXT, Phone TEXT)"),
        'nKeys': 8,
        'has_link': True,
        'linked_table': ('contact', 'product'),
        'primary_key': 'VendorID',
        'unique_key': ('CompanyName',)
    },
    'contact': {
        "sql": ("CREATE TABLE IF NOT EXISTS contact (ContactID INTEGER PRIMARY KEY, "
                "VendorID INTEGER REFERENCES vendor (VendorID) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL, "
                "ContactPerson TEXT NOT NULL, Title TEXT, Email TEXT UNIQUE ON CONFLICT IGNORE NOT NULL, "
                "Phone TEXT, MobilePhone TEXT)"),
        'nKeys': 7
    },
    'product': {
        'sql': ("CREATE TABLE IF NOT EXISTS product (ProductID INTEGER PRIMARY KEY, "
                "VendorID INTEGER REFERENCES vendor (VendorID) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL, "
                "Name TEXT NOT NULL, Vertical TEXT, Version TEXT NOT NULL, Series TEXT, "
                "ProductWebPage TEXT, HardwareVersion TEXT NOT NULL, SoftwareVersion TEXT NOT NULL, "
                "FirmwareVersion TEXT, SupportsOTAA BOOLEAN, TestModeAvailable BOOLEAN, "
                "ADR BOOLEAN, OptionalDataRate TEXT, TestSpec TEXT, DevEUIRange TEXT, ProductJPG BLOB,"
                "UNIQUE (VendorID, Name, Version, HardwareVersion, SoftwareVersion) ON CONFLICT IGNORE)"),
        'nKeys': 17,
        'has_link': True,
        'linked_table': ('productDocs', 'regionSKU', 'joinProcess', 'powerSpec', 'security', 'qrCode', 'networkLoss', 'upLink'),
        'primary_key': 'ProductID',
        'unique_key': ('Name', 'Version', 'HardwareVersion', 'SoftwareVersion')
    },
    'report': {
        'sql': ("CREATE TABLE IF NOT EXISTS report (ReportID INTEGER PRIMARY KEY, "
                "VendorName  TEXT, ProductName TEXT, RegionName TEXT, TestList TEXT, CreateTime real NOT NULL, SummaryText TEXT)"),
        'nKeys': 7
    },
    'productDocs': {
        'sql': ("CREATE TABLE IF NOT EXISTS productDocs (DocID INTEGER PRIMARY KEY, "
                "ProductID INTEGER REFERENCES product (ProductID) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL, "
                "DocLink TEXT UNIQUE ON CONFLICT IGNORE NOT NULL)"),
        'nKeys': 3
    },
    'regionSKU': {
        'sql': ("CREATE TABLE IF NOT EXISTS regionSKU (SkuID INTEGER PRIMARY KEY, "
                "ProductID INTEGER REFERENCES product (ProductID) ON DELETE CASCADE ON UPDATE CASCADE NOT NULL, "
                "PartNumber TEXT NOT NULL, Region TEXT, MaxEIRP REAL, NumTxStep INTEGER, "
                "TxSteps TEXT, US915Using64chForJoinReq BOOLEAN, US915DefaultSubBand INTEGER, "
                "UNIQUE (ProductID, PartNumber) ON CONFLICT IGNORE)"),
        'nKeys': 9,
        'has_link': True,
        'linked_table': ('device',),
        'primary_key': 'SkuID',
        'unique_key': ('PartNumber',)
    },
    'joinProcess': {
        'sql': ("CREATE TABLE IF NOT EXISTS joinProcess (JoinID INTEGER PRIMARY KEY, "
                "ProductID INTEGER REFERENCES product (ProductID)  "
                "ON DELETE CASCADE ON UPDATE CASCADE UNIQUE ON CONFLICT IGNORE NOT NULL, "
                "TransmissionTime1hr REAL, TransmissionTime10hr REAL, TransmissionTime24hr REAL)"),
        'nKeys': 5
    },
    'powerSpec': {
        'sql': ("CREATE TABLE IF NOT EXISTS powerSpec (PowerSpecID INTEGER PRIMARY KEY, "
                "ProductID INTEGER REFERENCES product (ProductID)  "
                "ON DELETE CASCADE ON UPDATE CASCADE UNIQUE ON CONFLICT IGNORE NOT NULL, "
                "UsableCapacity REAL, TypicalSelfDischarge REAL, MaxDischarge REAL, "
                "CurrentSleepMode REAL, MaxPower REAL, ReplacementVoltage REAL)"),
        'nKeys': 8
    },
    'security': {
        'sql': ("CREATE TABLE IF NOT EXISTS security (SecureID INTEGER PRIMARY KEY, "
                "ProductID INTEGER REFERENCES product (ProductID) "
                "ON DELETE CASCADE ON UPDATE CASCADE UNIQUE ON CONFLICT IGNORE NOT NULL, "
                "SupportsJoinServer BOOLEAN, OTAAProcedureDocumented BOOLEAN, OTAAProcedureReference TEXT, "
                "OUI TEXT, DevEUIRange TEXT, OUIJoinServer TEXT)"),
        'nKeys': 8
    },
    'qrCode': {
        'sql': ("CREATE TABLE IF NOT EXISTS qrCode (QRCodeID INTEGER PRIMARY KEY, "
                "ProductID INTEGER REFERENCES product (ProductID) "
                "ON DELETE CASCADE ON UPDATE CASCADE UNIQUE ON CONFLICT IGNORE NOT NULL, "
                "QrAvailable BOOLEAN, QrLocation TEXT, QrLocationOther TEXT, QrCodeContent TEXT)"),
        'nKeys': 6
    },
    'networkLoss': {
        'sql': ("CREATE TABLE IF NOT EXISTS networkLoss (LossID INTEGER PRIMARY KEY, "
                "ProductID INTEGER REFERENCES product (ProductID) "
                "ON DELETE CASCADE ON UPDATE CASCADE UNIQUE ON CONFLICT IGNORE NOT NULL, "
                "KeepAlive BOOLEAN, KeepAlivePeriod REAL, KeepAliveReconnect BOOLEAN, "
                "KeepAliveReconnectPeriod REAL, ExpectsDownLink BOOLEAN, ExpectsDownLinkPeriod REAL, "
                "ExpectsDownLinkReconnect BOOLEAN, ExpectsDownLinkReconnectPeriod REAL, "
                "ConfirmUpLinkRetries INTEGER, ConfirmUpLinkRetriesPeriod REAL)"),
        'nKeys': 12
    },
    'upLink': {
        'sql': ("CREATE TABLE IF NOT EXISTS upLink (upLinkID INTEGER PRIMARY KEY, "
                "ProductID INTEGER REFERENCES product (ProductID) "
                "ON DELETE CASCADE ON UPDATE CASCADE UNIQUE ON CONFLICT IGNORE NOT NULL, "
                "UpLinksperDay INTEGER, PeriodicUpLink BOOLEAN, UpLinkPeriod REAL, "
                "UpLinkPeriodCustomizable BOOLEAN, UpLinkPeriodCustomReference TEXT)"),
        'nKeys': 7
    }
}

TABLE_SETS = {
    'questionnaire_tables': {'vendor', 'product', 'contact', 'productDocs', 'regionSKU', 'joinProcess', 'powerSpec',
                             'security', 'qrCode', 'networkLoss', 'upLink'},
    'blob_tables': {'power': 'value', 'product': 'ProductJPG', 'testInstance': 'Picture'},
}

def create_db_tables_backup():
    conn = sqlite3.connect(DB_FILE_BACKUP, timeout=60)
    conn.row_factory = sqlite3.Row
    for table in TABLES:
        conn.execute(TABLES[table]['sql'])
    conn.execute("CREATE INDEX IF NOT EXISTS power_time_duration ON power(time, duration)")
    conn.close()


def create_db_tables_proxy():
    for DB_FILE in [DB_FILE_PROXY, DB_FILE_BACKUP]:
        conn = sqlite3.connect(DB_FILE, timeout=60)
        conn.row_factory = sqlite3.Row

        conn.execute(TABLES['session']['sql'])
        conn.execute(TABLES['packet']['sql'])
        conn.execute("CREATE INDEX IF NOT EXISTS packet_time ON packet(time)")
        conn.execute(TABLES['delay']['sql'])
        conn.execute("CREATE INDEX IF NOT EXISTS delay_time ON delay(time_gen)")
        conn.commit()
        conn.close()


def create_db_tables_tc():
    for DB_FILE in [DB_FILE_CONTROLLER, DB_FILE_BACKUP]:
        conn = sqlite3.connect(DB_FILE, timeout=60)
        conn.row_factory = sqlite3.Row

        conn.execute(TABLES['testInstance']['sql'])
        conn.commit()
        conn.close()


def backup_db_tc():
    if not os.path.exists(DB_FILE_CONTROLLER):
        return
    if not os.path.exists(DB_FILE_BACKUP):
        create_db_tables_tc()

    conn_src = sqlite3.connect(DB_FILE_CONTROLLER, timeout=60)
    conn_src.row_factory = sqlite3.Row
    conn_dst = sqlite3.connect(DB_FILE_BACKUP, timeout=60)
    conn_dst.row_factory = sqlite3.Row


    logging.debug("Start controller db backup")

    src_inst = conn_src.execute("SELECT * FROM testInstance ORDER BY rowid desc limit 1").fetchone()
    if src_inst:
        dst_inst = conn_dst.execute("SELECT testInstID, FinishTime FROM testInstance WHERE BenchID=(?) AND StartTime=(?)", (src_inst['BenchID'], src_inst['StartTime'])).fetchone()
        if dst_inst and not dst_inst['FinishTime']:
            conn_dst.execute("UPDATE testInstance SET UpdateTime=(?), CurrentPara=(?) WHERE rowid=(?)", (src_inst['UpdateTime'], src_inst['CurrentPara'], dst_inst['testInstID']))
            conn_dst.commit()

    logging.debug("done controller db backup")

    conn_src.close()
    conn_dst.close()


def backup_db_proxy():
    if not os.path.exists(DB_FILE_PROXY):
        return
    if not os.path.exists(DB_FILE_BACKUP):
        create_db_tables_proxy()
    
    conn_src = sqlite3.connect(DB_FILE_PROXY, timeout=60)
    conn_dst = sqlite3.connect(DB_FILE_BACKUP, timeout=60)

    logging.debug("start proxy db backup")

    data = {}
    for table in ["packet", "session", "delay"]:
        data[table] = conn_src.execute("SELECT * FROM " + table).fetchall()
        if table in ["packet", "delay"]:
            conn_src.executemany("DELETE FROM " + table + " WHERE rowid = (?)", [(p[0], ) for p in data[table]])
        conn_src.commit()
    
    logging.debug("done proxy db reading")

    for table in ["packet", "session", "delay"]:
        conn_dst.executemany("INSERT OR REPLACE INTO "+table+" VALUES (" + "?,"*(TABLES[table]['nKeys']-1) + "?)",
                             [((None,)+p[1:]) for p in data[table]])
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
    
    conn_dst.commit()
    conn_dst.close()
    conn_src.close()
    logging.debug("done db proxy recover")


def backup_db_pm(test_inst_id=None):
    logging.debug("start power db backup, test_inst_id: {}".format(test_inst_id))

    power_dir = os.path.join(os.path.dirname(__file__), POWER_FOLDER)
    files = sorted(os.listdir(power_dir))

    data_insert = []
    for file in files[:-1]:
        src = power_dir + file

        with open(src, "rb") as f:
            bytes = f.read()

            logging.log(logging.NOTSET, file + " " + str(len(bytes)))
            currents = [int.from_bytes(bytes[i:i+4], byteorder='little', signed = True) for i in range(0, len(bytes), 4)]

            if currents:
                avg = int(np.mean(currents))
                max_current = max(currents)
                data_insert.append((test_inst_id, int(file[:-4]), avg, max_current, 1, bytes))

        os.remove(src)

    conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), DB_FILE_BACKUP), timeout=60)
    conn.row_factory = sqlite3.Row

    conn.executemany("INSERT OR REPLACE INTO power (TestInstID, time,average,max,duration,value) VALUES (?,?,?,?,?,?)", data_insert)
    conn.commit()

    calc_db_pm(test_inst_id, conn)

    logging.debug("done power db backup")


def calc_db_pm(test_inst_id, conn=None):
    if not conn:
        conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), DB_FILE_BACKUP), timeout=60)
        conn.row_factory = sqlite3.Row

    step = 60

    start_time = conn.execute("SELECT MAX(time) FROM power WHERE TestInstID=(?) AND duration = (?)",
                              (test_inst_id, step)).fetchone()["MAX(time)"]
    if not start_time:
        start_time = conn.execute("SELECT MIN(time) FROM power WHERE TestInstID=(?) AND duration = (?)",
                                  (test_inst_id, 1)).fetchone()["MIN(time)"]
    else:
        start_time += step

    end_time = conn.execute("SELECT MAX(time) FROM power WHERE TestInstID=(?) AND duration = (?)",
                            (test_inst_id, 1)).fetchone()["MAX(time)"]

    if end_time:
        end_time -= step

        data_insert = []
        for time in range(start_time, end_time, step):
            avg = conn.execute('SELECT AVG(average) FROM power WHERE testInstID=(?) AND duration=1 AND time >= (?) AND time < (?)',
                               (test_inst_id, time, time + step)).fetchone()["AVG(average)"]

            if avg is not None:
                peak = conn.execute('SELECT MAX(max) FROM power WHERE testInstID=(?) AND duration=1 AND time >= (?) AND time < (?)',
                                    (test_inst_id, time, time + step)).fetchone()["MAX(max)"]
                data_insert.append((test_inst_id, time, int(avg), peak, step))

        conn.executemany("INSERT OR REPLACE INTO power (TestInstID, time,average,max,duration) VALUES (?,?,?,?,?)", data_insert)
        conn.commit()
    conn.close()


def merge_linked_table(conn, table):
    unique_keys = ""
    conditions = ""
    for key in TABLES[table]['unique_key']:
        unique_keys += (table+".{0} as tmp{0}, ").format(key)
        conditions += " AND tmp.tmp{0} = t.{0}".format(key)
    conditions = conditions[5:]
    start_pos = len(TABLES[table]['unique_key'])+3
    for lk_table in TABLES[table]['linked_table']:
        logging.debug("merging linked table %s" % lk_table)
        conn.execute("CREATE TEMPORARY TABLE tmp AS "
                     "SELECT {3} {1}.* "
                     "FROM db2.{0}, db2.{1} "
                     "WHERE db2.{0}.{2} = db2.{1}.{2}".format(table, lk_table,
                                                              TABLES[table]['primary_key'],
                                                              unique_keys))
        data = conn.execute(("SELECT t.{0} as newID, tmp.* FROM tmp, {1} AS t "
                             "WHERE "+conditions).format(TABLES[table]['primary_key'],
                                                         table)).fetchall()
        logging.debug("number of data is {}".format(len(data)))
        # device table is different because it doesn't have a deviceID but a devEUI
        conn.executemany("INSERT INTO " + lk_table + " VALUES (" + "?," * (TABLES[lk_table]['nKeys'] - 1) + "?)",
                         [((p[2] if lk_table == "device" else None, p[0],) + p[start_pos:]) for p in data])

        conn.execute("DROP TABLE tmp")
        if 'has_link' in TABLES[lk_table] and TABLES[lk_table]['has_link']:
            merge_linked_table(conn, lk_table)

def generate_caches(responses):
    from web_result import generate_cache
    for response in responses:
        generate_cache(response)

def merge_db_backup():
    conn = sqlite3.connect(DB_FILE_BACKUP, timeout=60)
    conn.row_factory = sqlite3.Row

    try:
        conn.execute("ATTACH DATABASE ? as db2", ("db/db_backup2.db",))

        data = {}
        for table in ["vendor", "testInstance"]:
            data[table] = conn.execute("SELECT * from db2."+table).fetchall()

        if data['testInstance']:
            keys = data['testInstance'][0].keys()
            ready_idx = keys.index('Ready')
            benchid_idx = keys.index('BenchID')
            start_time_idx = keys.index('StartTime')
            for test_inst in data['testInstance']:
                tmp = list(test_inst)
                tmp[ready_idx] = CACHE_STATE['GENERATING']
                test_inst = tmp
        for table in ["vendor", "testInstance"]:
            logging.debug("merging table %s" % table)
            conn.executemany("INSERT INTO "+table+" VALUES ("+"?,"*(TABLES[table]['nKeys']-1)+"?)",
                             [((None,)+p[1:]) for p in data[table]])
            if 'has_link' in TABLES[table] and TABLES[table]['has_link']:
                merge_linked_table(conn, table)
        responses = []
        for data in data['testInstance']:
            response = conn.execute('SELECT * FROM testInstance WHERE BenchID=(?) and StartTime=(?)',
                                     (data[benchid_idx], data[start_time_idx])).fetchone()
            if response['Ready'] == CACHE_STATE['GENERATING']:
                response = dict(response)
                response['rowid'] = response['TestInstID']
                responses.append(response)
        conn.commit()
        conn.execute("DETACH DATABASE db2")
        conn.close()
        threading.Thread(target=generate_caches, args = (responses, )).start()
    except:
        conn.close()
        raise


def get_table(table_name, test_inst_id):
    path = os.path.join(os.path.dirname(__file__), DB_FILE_BACKUP)

    conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), DB_FILE_BACKUP),
                           timeout=60)
    conn.row_factory = sqlite3.Row
    response = conn.execute(('SELECT tbl.* FROM testInstance as t, device as d, '
                             'regionSKU as r, {} as tbl WHERE t.TestInstID=(?) '
                             'AND t.DevEui=d.DevEui AND d.SkuID=r.SkuID '
                             'AND r.ProductID=tbl.ProductID').format(table_name),
                            (test_inst_id, )).fetchone()
    conn.close()
    if response:
        table = dict(response)
    else:
        table = {}

    return table


def get_power_spec(test_inst_id):
    power_spec = get_table("powerSpec", test_inst_id)

    if not power_spec["MaxDischarge"]:
        power_spec['MaxDischarge'] = 0.855
    if power_spec['CurrentSleepMode'] is None:
        power_spec['CurrentSleepMode'] = 0
    return power_spec


def delete_records(conn, table, key, rows):
    if 'has_link' in TABLES[table] and TABLES[table]['has_link']:
        if key != 'rowid':
            lk_rows = []
            for row in rows:
                responses = conn.execute('Select rowid FROM {} WHERE {}=(?)'.format(table, key),
                                         (row['rowid'],)).fetchall()
                for response in responses:
                    tmp = list(response)
                    lk_rows.append({'rowid': tmp[0]})
        else:
            lk_rows = rows
        for lk_table in TABLES[table]['linked_table']:
            delete_records(conn, lk_table, TABLES[table]['primary_key'], lk_rows)

    for row in rows:
        conn.execute('DELETE FROM {} WHERE {}=(?)'.format(table, key), (row['rowid'],))


def insert_records(conn, table, tables):
    keys = tuple(tables[table].keys())
    if table == 'device':
        tables[table]['DevEui'] = tables[table]['DevEui'].lower()

    # if a table has linked tables, cannot run "INSERT OR REPLACE INTO" directly
    # that would impact the existing linked tables

    if 'has_link' in TABLES[table] and TABLES[table]['has_link']:
        cursor = conn.execute('INSERT INTO ' + table + ' (' + ','.join(keys) + ') '
                              'VALUES (' + '?,' * (len(keys) - 1) + '?)',
                              [tables[table][key] for key in keys])
        if cursor.rowcount == 0:
            raise Exception("This {} record already exists! To modify it, delete it first.".format(table))
        else:
            id = cursor.lastrowid

            for lk_table in TABLES[table]['linked_table']:
                if lk_table in tables:
                    tables[lk_table][TABLES[table]['primary_key']] = id
                    insert_records(conn, lk_table, tables)
    else:
        conn.execute('INSERT OR REPLACE INTO ' + table + ' (' + ','.join(keys) + ') '
                              'VALUES (' + '?,' * (len(keys) - 1) + '?)',
                              [tables[table][key] for key in keys])
