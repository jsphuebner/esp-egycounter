#!/usr/bin/python3

import time, sys, serial, json
import paho.mqtt.client as mqtt

#Soyosource control found here
#https://github.com/syssi/esphome-soyosource-gtn-virtual-meter/tree/main/components

def on_message(client, ser485, msg):
	req = [ 0x24, 0x56, 0x0, 0x21, 0x2, 0x00, 0x80, 0xE0 ]
	
	if msg.topic == "/inverter/setpoint/power":
		finalPower = float(msg.payload)
		finalPower = int(min(800, max(0, finalPower)))

		print("Setting output power to " + str(finalPower))
		sys.stdout.flush()
		
		req[4] = int(finalPower / 256)
		req[5] = finalPower & 255
		cs = 264 - req[4] - req[5]
		if cs > 255:
			if finalPower > 250:	cs -= 256
			else:			cs -= 255
		req[7] = cs
		ser485.write(req)

def queryStatus(ser):
	req = [ 0x55, 0x01, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0xFE]
	ser.write(req)
	reply = ser.read(15)
	
	sum = 0xff
	for i in reply[1:14]:
		sum = (sum - i) & 0xff

	#if queryStatus.lastreply != reply:
	#	print (' '.join(format(x, '02x') for x in reply))
	#queryStatus.lastreply = reply
	
	if len(reply) == 15 and sum == reply[14]:
		return (True, reply[4], (reply[5]*256 + reply[6]) / 10, (reply[7]*256 + reply[8]) / 10, reply[10], reply[11] / 2, (reply[12]*256 + reply[13]) / 10 - 20)
	else:
		print("invalid checksum")
		return (False, 0, 0, 0, 0, 0, 0)

with open("config.json") as configFile:
	config = json.load(configFile)

ser485 = serial.Serial(config['inverter']['tty485'], 4800, timeout=0.1)
#Must be enabled with 
# > pinmode P9.11 uart
# > pinmode P9.13 uart  
serTtl = serial.Serial(config['inverter']['ttyTTL'], 9600, timeout=0.1)
queryStatus.lastreply = []

client = mqtt.Client("soyoSource", userdata=ser485)
client.on_message = on_message
client.connect(config["broker"]["address"], 1883, 60)
client.subscribe("/inverter/setpoint/power")

client.publish("/inverter/info/maxpower", config['inverter']['maxpower'], retain=True)

voltages = [ 0, 0, 0, 0, 0 ]

while True:
	(valid, opmode, dcVoltage, current, acVoltage, acFrq, tmpHs) = queryStatus(serTtl)
	
	if valid:
		#Calculate sliding median of inverter voltage as it contains glitches
		voltages.append(dcVoltage)
		voltages.pop(0)
		v = voltages.copy()
		v.sort()
		client.publish("/inverter/info/udc", v[2])
		client.publish("/inverter/info/idc", current)
		client.publish("/inverter/info/temp", tmpHs)
		client.publish("/inverter/info/power", v[2] * current)
		
	client.loop(timeout=0.1)
	time.sleep(0.2)

