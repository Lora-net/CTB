import sys, datetime, sqlite3, traceback, time, json, socket, subprocess, logging

if sys.platform == "win32":
    splitter = "\\"
else:
    splitter = "/"


config = json.load(open("config.json"))


DB_FOLDER = config["folder"]["backup"]
DB_FILE_PROXY = config["file"]["database_proxy"]
DB_FILE_CONTROLLER = config["file"]["database_controller"]
DB_FILE_BACKUP = config["file"]["database_backup"]
DB_FILE_PM = config["file"]["database_power"]

POWER_FOLDER = config["folder"]["power"] + splitter
CACHE_FOLDER = config["folder"]["cache"]

DB_BACKUP_INTERVAL = 3600

LOG_FILE = 'tmp' + splitter + 'log.log'

addr_ns = (config["network_address"]["network_server"]["ip"], config["network_address"]["network_server"]["port"])
addr_tc = (config["network_address"]["test_controller"]["ip"], config["network_address"]["test_controller"]["port"])
addr_pf = (config["network_address"]["packet_forwarder"]["ip"], config["network_address"]["packet_forwarder"]["port"])
addr_report = (config["network_address"]["error_report"]["ip"], config["network_address"]["error_report"]["port"])
deduplication_threshold = float(config["deduplication_threshold"])

gw_mac = bytes.fromhex(config["gateway_id"])
use_internal_gateway = config["use_internal_gateway"]

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
            logging.debug(line)
    except:
        pass