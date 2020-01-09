import os
import sys
import time
from os import listdir
from os.path import isfile, join
import csv
import json
import unicodedata
import serial
import subprocess

# Function to subsitute diacritics
def _cleanticks(text):
    import re
    rep = {
        "ě":"e",
        "š":"s",
        "č":"c",
        "ř":"r",
        "ž":"z",
        "ý":"y",
        "á":"a",
        "í":"i",
        "é":"e"
    }

    rep = dict((re.escape(k), v) for k, v in rep.items())
    pattern = re.compile("|".join(rep.keys()))
    return pattern.sub(lambda m: rep[re.escape(m.group(0))], text)


# Read json file containing configuration data
def config(file_path):

    '''
    cfg = config("/home/pi/.romill/romill_conf/romill_config.json")
    print(cfg["devices"])

    dev_1 = cfg_data["devices"]["1"]
    '''

    # Open file and parse it
    try:
        cfg_file = open(file_path, "r")
        cfg_data = json.load(cfg_file)
        
    except IsADirectoryError:
        sys.stderr.write(str(file_path))
        sys.stderr.write("error while loading json\n")
        raise "config loading failed"
    
    except FileNotFoundError:
        sys.stderr.write(str(file_path))
        sys.stderr.write("file not found \n")
        raise
    
    # Return values
    return cfg_data

# Make config varianbles available for functions
cfg = config("/home/pi/.romill/romill_conf/romill_config.json")


def getdata(device_number):
    #cfg = config(config_path)
    dev_dictionary = dict()
    run_dictionary = dict()
    
    dev = str(device_number)
    dev_config = json.dumps(cfg["devices"][dev], separators=(',', ':'))
    path = cfg["devices"][dev]['dir']
    start_row = cfg["devices"][dev]['startFromRow']
    error_log_file = cfg["devices"][dev]['errorLog']
    property_name = "rml" + str(device_number)
    
    response = ping(device_number)
    mount = mount_rml(device_number)
    
    run_dictionary["ping"] = response
    run_dictionary["mount"] = mount
    
    last_file, _ = list_rml(path)
    run_dictionary["lastFile"] = last_file
    
    last_line = last_entry(path, last_file, start_row, error_log_file, 1)
    
    #dev_dictionary[property_name]["runData"] = run_dictionary
    dev_dictionary[property_name] = last_line
    
    ready_line = str(dev_dictionary).replace("'{", "{").replace("}'", "}").replace("'", '"')
    
    #serial_ok = toserial(ready_line)
    log_ok = logtofile(ready_line, cfg["rootDir"], cfg["devices"][dev]['outputFile'])
    #run_dictionary["serial"] = bool(serial_ok)
    run_dictionary["log"] = log_ok
    
    sys.stdout.write(str(ready_line))
    sys.stderr.write(str(json.dumps(run_dictionary, separators=(',', ':'))))
    
    return

# Function to get timestamp in UNIX format
def get_ts():
    
    # Format python time.time() result to UNIX standart
    value = int(time.time()*1000)
    return value


# Function for mounting network shared folders using SMBv1 protocol
def mount_rml(rml_id):
    
    device_path = cfg["devices"][rml_id]['dir']
    device_ip = cfg["devices"][rml_id]['ip']
    
    # check mounted folders
    is_mounted = subprocess.call("mountpoint", device_path)
    
    # Mount details for device 1
    #if rml_id == 1:
    #    device_ip = cfg["devices"]["1"]['ip']
    #    device_path = cfg["devices"]["1"]['dir']     
    
    # Mount details for device 2
    #elif rml_id == 2:
    #   device_ip = cfg["devices"]["2"]['ip']
    #    device_path = cfg["devices"]["2"]['dir']
        
    # Mount details for testing purposes
    #if rml_id == 3:
    #    return True
    
    try:
        # Mounting function using system cli
        mount = subprocess.Popen(
            ["sudo", "mount.cifs", device_ip, device_path, "-o", "credentials=/home/pi/.romill/romill_conf/romill.txt,vers=1.0" ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
    
        # Get outputs separately into variables
        out, error = mount.communicate()
        return True
    except:
        return False


# Function to get most recent data log in folder_path
def list_rml(folder_path):
    
    # initiate variables for counters etc.
    file_index = 0
    file_ok = []
    file_ok_index = 0
    items = [f for f in listdir(folder_path) if isfile(join(folder_path, f))]

    # For loop looking for all files with .csv extension, makes list of them
    for file_name in items:
        file_index = file_index + 1

        if ".csv" in file_name:
            file_ok.append(file_name)
            file_ok_index = file_ok_index + 1
            file_ok.sort()
    
    # If folder is empty, return status "False"
    if file_index == 0:
        #raise "Folder empty"
        return

    # string containing filename of most recent file
    file_last = file_ok[file_ok_index - 1]
    
    # string containing list of all filenames that passed filter
    file_list = [file_ok]

    return file_last, file_list


# Read error logs last entry
def get_error_log(file_folder, file_name, entry_count):

    file = str(file_folder + file_name)

    try:
        # Open file, set encoding
        f = open(file, encoding="ISO-8859-1")
        # Using csv reader function parse file
        csv_f = csv.reader(f)

        rows = 0
        headers_index = 0
        rows_index = 0

        list = []
        data = []

        # loop over all rows of data
        for row_line in csv_f:
            rows = rows + 1
            list.append(row_line)

        for i in range(entry_count):
            #err_pack["1"] = dict()
            
            err_row = dict()
            
            data_line = str(list[(rows - 1 - i)])
            
            # From each entry parse data to python dictionary
            #err_row["err_date"] = data_line[2:12]
            #err_row["err_time"] = data_line[13:21]
            err_row["err_num"] = data_line[22:24]
            #err_row["err_name"] = str(data_line[25:]).replace("']", "").replace("\\", "")
            
            data.append(err_row)
            #print(data_line)

        return err_row

    except:
        print("error")
    finally:
        f.close()


# Function to get most recent entry in passed file
def last_entry(file_folder, file_name, head_row, error_file_name, error_count):
    
    # assign head_row int to variable
    headers_position = int(head_row)
    
    # Concatenate strings to make complete path to read from
    file = str(file_folder + file_name)
    
    # Get device number to variable
    if("1" in file_folder):
        device_number = 1
    elif("2" in file_folder):
        device_number = 2
    else:
        device_number = 0
    
    #print(device_number)
    
    try:
        # Open file, set encoding
        f = open(file, encoding="ISO-8859-1")
        
        # Using csv reader function parse file
        csv_f = csv.reader(f)

        #time.sleep(0.5)

        rows = 0
        headers_index = 0
        rows_index = 0

        list = []

        # loop over all rows of data
        for row_line in csv_f:
            rows = rows + 1
            list.append(row_line)

        # Processing of header line to list
        headers_raw = str(list[headers_position-1][0])  # Get unmodified string from file
        # Prepare raw string to be parsed to list data type
        headers_list = headers_raw.replace('"', '').replace(" ", "").replace(";", ",")
        headers = headers_list.split(",") # Split string elements to list
        #print(headers)

        # Processing of last data entry line to list
        row_raw = str(list[rows - 2]) # Get unmodified string from file
        row_list = row_raw.replace(',', '.').replace(";", ",").replace("'", "").replace(" ", "").replace("[", "").replace("]", "").replace('"', '')  # Prepare raw string to be parsed to list data type
        row = row_list.split(",") # Split string elements to list
        #print(row)

        # Substitute headers that process incorrectly returning trash
        headers[1] = "time"
        headers[2] = "conveyor"
        headers[3] = "odtah"
        headers[4] = "sensor_input"

        # Start dictionary by naming it with processed device name
        device_name = "romill_" + str(device_number) #(str(file_folder)).replace("/", "")
        device_dictionary = dict()
        device_dictionary["name"] = device_name

        # Add device connection status variable to dictionary
        #device_dictionary["state"] = ping(device_number)
               
        # Construct python dictionary from supplied lists
        data_dictionary = dict(zip(headers, row))

        # Count number of headers
        for i in headers:
            headers_index = headers_index + 1

        # Count number of values to be compared with header count.
        # If it is equal, nothing went missing during dictionary creation
        for i in row:
            rows_index = rows_index + 1

        # Include those values into final dictionary
        device_dictionary["hdr_count"] = headers_index
        device_dictionary["row_count"] = rows_index

        # Merge device and data dictionaries creating one object
        dictionary = dict()
        #dictionary["program"] = [""]
        dictionary["device"] = device_dictionary
        dictionary["data"] = data_dictionary
        dictionary["error"] = get_error_log(file_folder, error_file_name, error_count)

        file_to_save = json.dumps(dictionary, separators=(',', ':'))
        #print(file_to_save)
        #file_to_save = dictionary
        #print(str(get_error_log(file_folder, error_file_name, error_count)))

        return file_to_save
    except:
        return
    finally:
        f.close()

#log to file
def logtofile(string, file_path, file_name):
    
        # Parse function arguments
    try:
        file = str(file_path + file_name)
        #print(file)
    except:
        print("error while loading file")
        
    try:
        log = open(file,"w+")
        log.write(str(string))
        return True
    except:
        print("error while writing to log")
        return False
    finally:
        log.close()

# Function to open serial port ttyUSB0 and transmit passed argument
def toserial(string_to_write):
    # Strip spaces and encode to bytes so serial can handle it
    string_serial = (str((string_to_write)).replace(" ", "")).encode()
    #print(string_serial)
    try:
        # Open serial port for duration needed to send data
        #with serial.Serial('/dev/ttyAMA0', 9600, timeout=0.5) as ser: # Slower baud with ttyS0 port
        with serial.Serial('/dev/ttyAMA0', 115200, timeout=0.5) as ser: # Faster baud rate using ttyAMA0 serial port
            ser.write(string_serial)

        return True

    except serial.serialutil.SerialException:  # Handle exception such as device disconnected
        return False
    except:
        return False


# Ping host to check availability
def ping(device_no):

    ts, internet, dev_1, dev_2 = getpingfile(cfg['rootDir'], cfg['pingFile'])

    if(device_no == 0):
        set_host = internet
    elif(device_no == 1):
        set_host = dev_1
    elif(device_no == 2):
        set_host = dev_2
    else:
        print("no such device")
        set_host = internet

    if(set_host is not False):
        return True
    else:
        return False


# Read json file containing host availability updated by another program (in this case Node-red)
def getpingfile(file_path, file_name):

    # Create empty list for values to be stored in
    ret_list = []

    # Parse function arguments
    try:
        file = str(file_path + file_name)
        #print(file)
    except:
        print("error while loading file")

    # Open file and parse it
    try:
        with open(file, "r") as json_file:
            data = json.load(json_file)

            file_updated = int(data["ts"])

            hosts = data["hosts"]

            internet = hosts["internet"]
            ret_list.append(internet["status"])

            device_1 = hosts["1"]
            ret_list.append(device_1["status"])

            device_2 = hosts["2"]
            ret_list.append(device_2["status"])

    except:
        print("error while processing json")
        return
        raise
    # Return values
    return file_updated, internet["status"], device_1["status"], device_2["status"]


