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

import sys, datetime, sqlite3, traceback, time, json, socket, subprocess, logging
import os
import RPi.GPIO as GPIO
from logging.handlers import RotatingFileHandler

if sys.platform == "win32":
    splitter = "\\"
else:
    splitter = "/"


#config = json.load(open(os.path.join(os.path.dirname(__file__), "config.json")))
config = json.load(open("config.json"))

GW_ID = config['gateway_id']
DB_FOLDER = config["folder"]["backup"]
DB_FILE_PROXY = config["file"]["database_proxy"]
DB_FILE_CONTROLLER = config["file"]["database_controller"]
DB_FILE_BACKUP = config["file"]["database_backup"]
FILE_PC_CONTEXT = config["file"]["pc_context"]

POWER_FOLDER = config["folder"]["power"] + splitter
CACHE_FOLDER = config["folder"]["cache"]
PCAP_FOLDER = config["folder"]["pcap"]

DB_BACKUP_INTERVAL = 3600
POWER_TB_BACKUP_INTERVAL = 600

LOG_FILE = 'tmp' + splitter + 'log.log'

addr_ns = (config["network_address"]["network_server"]["ip"], config["network_address"]["network_server"]["port"])
addr_tc = (config["network_address"]["test_controller"]["ip"], config["network_address"]["test_controller"]["port"])
addr_pc = (config["network_address"]["pytest_controller"]["ip"], config["network_address"]["pytest_controller"]["port"])
addr_pf = (config["network_address"]["packet_forwarder"]["ip"], config["network_address"]["packet_forwarder"]["port"])
addr_report = (config["network_address"]["error_report"]["ip"], config["network_address"]["error_report"]["port"])
udp_ports = (addr_ns[1], addr_tc[1], addr_pc[1], addr_pf[1])
deduplication_threshold = float(config["deduplication_threshold"])

gw_mac = bytes.fromhex(config["gateway_id"])
use_internal_gateway = config["use_internal_gateway"]
MAX_TX_POWER = config["gateway_max_power"]

NUM_LOG_FILES = config["num_log_files"]

PROC_MSG = {
    "GW_PUSH_DATA":        0,
    "NS_PUSH_ACK":         1,
    "GW_PULL_DATA":        2,
    "NS_PULL_RSP":         3,
    "NS_PULL_ACK":         4,
    "GW_TX_ACK":           5,
    "TC_DATA":             6,
    "TC_SETUP_TEST":       7,
    "TC_GET_PACKET":       8,
    "TC_TEARDOWN_TEST":    9,
    "TC_STOP_RSP":         10,
    "WB_POST_SEQUENCE":    11,
    "WB_GET_SEQUENCE":     12,
    "WB_DEL_SEQUENCE":     13,
    "WB_QUERY_TEST_STATE": 14
}

TEST_STATE = {
    'RUNNING': 0,
    'PASSED': 1,
    'FAILED': -1,
    'ABORTED': -2,
    'OBSERVATION': -3,
    'NA': -4
}

CACHE_STATE = {
    'NONE': 0,
    'GENERATING': 1,
    'READY': 2
}

JOIN_REQUEST          = '000'
JOIN_ACCEPT           = '001'
UNCONFIRMED_DATA_UP   = '010'
UNCONFIRMED_DATA_DOWN = '011'
CONFIRMED_DATA_UP     = '100'
CONFIRMED_DATA_DOWN   = '101'
REJOIN_REQUEST        = '110'
PROPRIETARY           = '111'
UPLINK_PACKETS        = [JOIN_REQUEST, UNCONFIRMED_DATA_UP, CONFIRMED_DATA_UP]
DNLINK_PACKETS        = [JOIN_ACCEPT, UNCONFIRMED_DATA_DOWN, CONFIRMED_DATA_DOWN]

def config_logger(file=None):
    if not os.path.exists("log"):
        os.mkdir("log")

    logger = logging.getLogger()
    logger.setLevel(logging.NOTSET)

    timestamp = time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime())
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    if not file:
        file = os.path.join("log", "ctb_" + timestamp + ".log")
    fh = RotatingFileHandler(file, maxBytes=100000, backupCount=128)
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)
    logger.addHandler(fh)


def config_console():
    logger = logging.getLogger()
    logger.setLevel(logging.NOTSET)

    timestamp = time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime())
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    # add stdout handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.DEBUG)
    console.setFormatter(formatter)
    logger.addHandler(console)


def log_time(data_in):
    logging.info(data_in)
    #output = datetime.datetime.strftime(datetime.datetime.utcnow(), "%Y-%m-%d %H:%M:%S.%f") + " " + str(data_in)
    #print(output)


datrLUT = {
    "US": {
        "up": {
            "SF10BW125": 0,
            "SF9BW125": 1,
            "SF8BW125": 2,
            "SF7BW125": 3,
            "SF8BW500": 4
        },
        "down": {
            "SF12BW500": 8,
            "SF11BW500": 9,
            "SF10BW500": 10,
            "SF9BW500": 11,
            "SF8BW500": 12,
            "SF7BW500": 13
        }
    },
    "EU": {
        "up": {
            "SF12BW125": 0,
            "SF11BW125": 1,
            "SF10BW125": 2,
            "SF9BW125":  3,
            "SF8BW125":  4,
            "SF7BW125":  5,
            "SF7BW250":  6,
        },
        "down": {
            "SF12BW125": 0,
            "SF11BW125": 1,
            "SF10BW125": 2,
            "SF9BW125": 3,
            "SF8BW125": 4,
            "SF7BW125": 5,
            "SF7BW250": 6,
        }
    }
}

datrLUTrev = {
    "US": {
        0: "SF10BW125",
        1: "SF9BW125",
        2: "SF8BW125",
        3: "SF7BW500",
        4: "SF8BW500",
        8: "SF12BW500",
        9: "SF11BW500",
        10: "SF10BW500",
        11: "SF9BW500",
        12: "SF8BW500",
        13: "SF7BW500"
    },
    "EU": {
        0: "SF12BW125",
        1: "SF11BW125",
        2: "SF10BW125",
        3: "SF9BW125",
        4: "SF8BW125",
        5: "SF7BW125",
        6: "SF8BW125"
    }
}


def reverse_eui(dev_eui):
    reversed_dev_eui = ""
    for i in range(0, 16, 2):
        reversed_dev_eui = reversed_dev_eui + dev_eui[14 - i: 16 - i]
    return reversed_dev_eui.lower()


def reliable_run(method, loop = False):
    if loop:
        while True:
            try:
                method()
            except:
                error_str = traceback.format_exc()
                for line in error_str.split("\n"):
                    logging.critical(error_str)

                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    sock.sendto(error_str.encode(), addr_report)
                    sock.close()
                except:
                    pass

                time.sleep(1)
                continue
    else:
        try:
            method()
        except:
            error_str = traceback.format_exc()
            for line in error_str.split("\n"):
                logging.critical(error_str)

            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.sendto(error_str.encode(), addr_report)
                sock.close()
            except:
                pass

            time.sleep(1)


def report_ip():
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        response = subprocess.check_output(['ifconfig'])
        sock.sendto(response, addr_report)
        sock.close()
        for line in response.decode().split("\n"):
            logging.log(logging.NOTSET, line)
    except:
        pass


def device_on(on=True):
    GPIO.setmode(GPIO.BCM)
    pin1 = 26
    pin2 = 19
    GPIO.setup(pin1, GPIO.OUT)
    GPIO.setup(pin2, GPIO.OUT)
    if on:
        GPIO.output(pin1, 1)
        GPIO.output(pin2, 1)
    else:
        GPIO.output(pin1, 0)
        GPIO.output(pin2, 0)


def start_pcap():
    ports = " or ".join([str(port) for port in udp_ports]).split()
    cmd = ["tcpdump", "port"]
    cmd += ports
    cmd += ["-i", "any", "-w", time.strftime("%Y-%m-%d_%H-%M-%S") + '.pcap', "-s", "0"]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    return process
