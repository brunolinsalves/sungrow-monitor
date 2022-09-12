#!/usr/bin/env python

# Copyright (c) 2019 Thomas Fairbank
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

from collections.abc import Mapping
from pymodbus.payload import BinaryPayloadDecoder
from pymodbus.constants import Endian
from pymodbus.client.sync import ModbusTcpClient
from pymodbus.exceptions import ModbusIOException
from pytz import timezone
import config
import json
import time
import datetime
import requests
import traceback
from threading import Thread
import SungrowModbusTcpClient as sungrow
import sys
import paho.mqtt.client as mqtt

MIN_SIGNED   = -2147483648
MAX_UNSIGNED =  4294967295

MQTT_BROKER   = sys.argv[1]
MQTT_PORT     = sys.argv[2]
MQTT_USERNAME = sys.argv[3]
MQTT_PASSWORD = sys.argv[4]
INVERTER_HOST = sys.argv[5]
INVERTER_PORT = sys.argv[6]
PVOUTPUT_API = sys.argv[7]
PVOUTPUT_SID = sys.argv[8]

MQTT_VOLTAGE_TOPIC          = "home/sungrow_monitor/voltage"
MQTT_POWER_GENERATION_TOPIC = "home/sungrow_monitor/power_gen"

print ("Load config %s" % config.model)
print ("Timezone is %s" % config.timezone)
print ("The current time is %s" % (str(datetime.datetime.now(timezone(config.timezone))).partition('.')[0]) )

# modbus datatypes and register lengths
sungrow_moddatatype = {
  'S16':1,
  'U16':1,
  'S32':2,
  'U32':2,
  'STR16':8
  }

#TODO: change this to be able to be overridden by a file in the config directory if config path has file import form there otherwise do the below
# Load the modbus map from config
modmap_file = "modbus-" + config.model
modmap = __import__(modmap_file)

#client = ModbusTcpClient(config.inverter_ip,
#                         timeout=config.timeout,
#                         RetryOnEmpty=True,
#                         retries=3,
#						 ZeroMode=True,
#                         port=config.inverter_port)


client = sungrow.SungrowModbusTcpClient(host=INVERTER_HOST,
                                        timeout=config.timeout,
                                        RetryOnEmpty=True,
                                        retries=3,
                                        port=INVERTER_PORT)

inverter = {}
power_gen = []
power_con = []
voltage_1 = []
voltage_2 = []
#if upload_consumption hasn't been defined in the config, then assume false. If its explicitly false let it be that, otherwise its true
try:
	config.upload_consumption
except AttributeError:
	upload = False
else:
	upload = config.upload_consumption
bus = json.loads(modmap.scan)

def load_register(registers):
  from pymodbus.payload import BinaryPayloadDecoder
  from pymodbus.constants import Endian

  #moved connect to here so it reconnect after a failure
  client.connect()

  #iterate through each avaialble register in the modbus map
  for thisrow in registers:
    name = thisrow[0]
    startPos = thisrow[1]-1 #offset starPos by 1 as zeromode = true seems to do nothing for client
    data_type = thisrow[2]
    format = thisrow[3]

    #try and read but handle exception if fails
    try:
      received = client.read_input_registers(address=startPos,
                                             count=sungrow_moddatatype[data_type],
                                             unit=config.slave)

    except:
      thisdate = str(datetime.datetime.now(timezone(config.timezone))).partition('.')[0]
      thiserrormessage = thisdate + ': Connection not possible. Check settings or connection.'
      print (thiserrormessage)
      time.sleep(10 * 60)

      if (count % 10 == 0):
        error_time = datetime.datetime.now( timezone(config.timezone) )
        querystring = {"d":"%s" % error_time.strftime("%Y%m%d"),"t":"%s" % error_time.strftime("%H:%M"),"v2": "0", "v6": "0"}
        headers = {
          'X-Pvoutput-Apikey': "%s" % PVOUTPUT_API,
          'X-Pvoutput-SystemId': "%s" % PVOUTPUT_SID,
          'Content-Type': "application/x-www-form-urlencoded",
          'cache-control': "no-cache"
        }
        response = requests.request("POST", url=config.pv_url, headers=headers, params=querystring)
        if response.status_code != requests.codes.ok:
            print ("Erro ao enviar dados para o PVOutput: Voltage: 0.0V e Power: 0.0W")
        else:
            print ("Dados enviados com sucesso para PVOutput: Voltage: 0.0V e Power: 0.0W")

      return

    # 32bit double word data is encoded in Endian.Little, all byte data is in Endian.Big
    if '32' in data_type:
        message = BinaryPayloadDecoder.fromRegisters(received.registers, byteorder=Endian.Big, wordorder=Endian.Little)
    else:
        message = BinaryPayloadDecoder.fromRegisters(received.registers, byteorder=Endian.Big, wordorder=Endian.Big)
    #decode correctly depending on the defined datatype in the modbus map
    if data_type == 'S32':
      interpreted = message.decode_32bit_int()
    elif data_type == 'U32':
      interpreted = message.decode_32bit_uint()
    elif data_type == 'U64':
      interpreted = message.decode_64bit_uint()
    elif data_type == 'STR16':
      interpreted = message.decode_string(16).rstrip('\x00')
    elif data_type == 'STR32':
      interpreted = message.decode_string(32).rstrip('\x00')
    elif data_type == 'S16':
      interpreted = message.decode_16bit_int()
    elif data_type == 'U16':
      interpreted = message.decode_16bit_uint()
    else: #if no data type is defined do raw interpretation of the delivered data
      interpreted = message.decode_16bit_uint()

    #check for "None" data before doing anything else
    if ((interpreted == MIN_SIGNED) or (interpreted == MAX_UNSIGNED)):
      displaydata = None
    else:
      #put the data with correct formatting into the data table
      if format == 'FIX3':
        displaydata = float(interpreted) / 1000
      elif format == 'FIX2':
        displaydata = float(interpreted) / 100
      elif format == 'FIX1':
        displaydata = float(interpreted) / 10
      else:
        displaydata = interpreted

    inverter[name] = displaydata

  #Add timestamp based on PC time rather than inverter time
  inverter["0000 - Timestamp"] = str(datetime.datetime.now(timezone(config.timezone))).partition('.')[0]

#define a loop timer that can account for drift to keep upload in sync
def loop_timer(delay, task):
  next_time = time.time() + delay
  while True:
    time.sleep(max(0, next_time - time.time()))
    try:
      task()
    except Exception:
      traceback.print_exc()
      # in production code you might want to have this instead of course:
      # logger.exception("Problem while executing repetitive task.")
    # skip tasks if we are behind schedule:
    next_time += (time.time() - next_time) // delay * delay + delay

#dumb loop counter to trigger send
count=0

#main program loop
def main():
  global count, client
  try:
    global inverter
    inverter = {}

    if client == None:
      client = sungrow.SungrowModbusTcpClient(host=INVERTER_HOST,
                                              timeout=config.timeout,
                                              RetryOnEmpty=True,
                                              retries=3,
                                              port=INVERTER_PORT)

    load_register(modmap.sungrow_registers)

    if len(inverter) > 0: #only continue if we get a successful read
      if inverter["5031 - Total active power"] <90000: #sometimes the modbus give back a weird value
        power_gen.append(inverter["5031 - Total active power"])
        print ("Total active power = %s" % inverter["5031 - Total active power"])
      else:
        print ("Didn't get a read for Daily Power")
      if inverter["5011 - MPPT 1 voltage"] <9000: #sometimes the modbus give back a weird value
        voltage_1.append(inverter["5011 - MPPT 1 voltage"])
        print ("MPPT 1 Voltage = %s" % inverter["5011 - MPPT 1 voltage"])
      else:
        print ("Didn't get a read for MPPT 1 Voltage")
      if inverter["5013 - MPPT 2 voltage"] <9000: #sometimes the modbus give back a weird value
        voltage_2.append(inverter["5013 - MPPT 2 voltage"])
        print ("MPPT 2 Voltage = %s" % inverter["5013 - MPPT 2 voltage"])
      else:
        print ("Didn't get a read for MPPT 2 Voltage")
      #if config has elected to upload consumption data then we should store those registers if they are enabled
      if upload:
        if inverter["5097 - Daily import energy"] <50000: #sometimes the modbus give back a weird value
          power_con.append(inverter["5097 - Daily import energy"])
          print ("Daily import energy = %s" % inverter["5097 - Daily import energy"])
        else:
          print ("Didn't get a read for Daily Import Energy")
      # we are done with the connection for now so close it
    client.close()
  except ModbusIOException as err:
    print ("[ERROR1] %s" % err)
    print ("  - Exiting with error code 1 to home assistant restart the Addon...")
    client.close()
    client = None
    sys.exit(1)
  except Exception as err:
    print ("[ERROR2] %s" % err)
    client.close()
    client = None
  #increment counter
  count+=1

  # Count check error

  if count >= (60/config.scan_interval) * config.upload_interval and len(power_gen) >= 1 : #possibly spawn thread here and instead make counter be every 5 mins
    print ("%d individual observations were made (out of %d attempts) over the last %d minutes averaging %d Watts" % (len(power_gen), count, count*config.scan_interval/60,sum(power_gen)/len(power_gen)) )
    count = 0
    now = datetime.datetime.now(timezone(config.timezone))
    try:
      #average voltage to a single value for upload
      if max(voltage_2) > 0:
        v6 = ((sum(voltage_1)/len(voltage_1))+sum(voltage_2)/len(voltage_2))/2
      else:
        v6 = sum(voltage_1)/len(voltage_1)
      #v2 = power generation, v4 = power consumption, v6 = voltage
      if upload:
        querystring = {"d":"%s" % now.strftime("%Y%m%d"),"t":"%s" % now.strftime("%H:%M"),"v2":"%s" % (sum(power_gen)/len(power_gen)), "v4":"%s" % (sum(power_con)/len(power_con)) ,"v6":"%s" % v6}
      else:
        querystring = {"d":"%s" % now.strftime("%Y%m%d"),"t":"%s" % now.strftime("%H:%M"),"v2":"%s" % (sum(power_gen)/len(power_gen)), "v6":"%s" % v6}

      # MQTT connect and publish values
      try:
        mqtt_client = mqtt.Client('pv_data')
        mqtt_client.username_pw_set(MQTT_USERNAME, password=MQTT_PASSWORD)
        mqtt_client.connect(MQTT_BROKER, int(MQTT_PORT))
        mqtt_client.publish(MQTT_VOLTAGE_TOPIC,v6)
        mqtt_client.publish(MQTT_POWER_GENERATION_TOPIC, sum(power_gen)/len(power_gen) )
        print ("MQTT data published.")
        mqtt_client.disconnect()
      except Exception as e:
        mqtt_client = None
        print ("MQTT client connection failed")
        print (e)

      #wipe the array for next run
      del power_gen[:]
      del voltage_1[:]
      del voltage_2[:]
      del v6
      del power_con[:]
      headers = {
        'X-Pvoutput-Apikey': "%s" % PVOUTPUT_API,
        'X-Pvoutput-SystemId': "%s" % PVOUTPUT_SID,
        'Content-Type': "application/x-www-form-urlencoded",
        'cache-control': "no-cache"
      }
      response = requests.request("POST", url=config.pv_url, headers=headers, params=querystring)
      if response.status_code != requests.codes.ok:
          raise StandardError(response.text)
      else:
          print ("Successfully posted to %s" % config.pv_url)
    except ModbusIOException as err:
      print ("[ERROR3] %s" % err)
      print ("  - Exiting with error code 1 to home assistant restart the Addon...")
      client.close()
      sys.exit(1)
    except Exception as err:
      print ("[ERROR4] %s" % err)

  #sleep until next iteration
  print ("Loop %d of %d complete. Sleeping %ds...." % (count, (60/config.scan_interval)*config.upload_interval, config.scan_interval))

loop_timer(config.scan_interval, main)
