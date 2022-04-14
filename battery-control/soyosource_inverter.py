#!/usr/bin/python

import time, sys, serial
import paho.mqtt.client as mqtt

#Soyosource control found here
#https://github.com/syssi/esphome-soyosource-gtn-virtual-meter/tree/main/components

def on_message(client, serSoyo, msg):
	bytes = [ 0x24, 0x56, 0x0, 0x21, 0x2, 0x00, 0x80, 0xE0 ]
	
	if msg.topic == "/inverter/setpoint/power":
		finalPower = float(msg.payload)
		finalPower = int(min(900, max(0, finalPower)))

		print("Setting output power to " + str(finalPower))
		sys.stdout.flush()
		client.publish("/inverter/info/power", finalPower)
		
		bytes[4] = finalPower / 256
		bytes[5] = finalPower & 255
		bytes[7] = (264 - bytes[4] - bytes[5]) & 255
		serSoyo.write(bytes)

serSoyo = serial.Serial('/dev/ttyUSB0', 4800, timeout=0.1)

client = mqtt.Client("soyoSource", userdata=serSoyo)
client.on_message = on_message
client.connect("localhost", 1883, 60)
client.subscribe("/inverter/setpoint/power")

client.publish("/inverter/info/maxpower", 900, retain=True)

while True:
	#TODO: collect some info from the inverter and publish it
	client.loop(timeout=0.2)

