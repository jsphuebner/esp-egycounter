#!/usr/bin/python

import time, sys, mansonlib
import paho.mqtt.client as mqtt

def on_message(client, hcs, msg):
	global powerTimeout
	global voltage
	
	if msg.topic == "/charger/setpoint/voltage":
		hcs.SetOutputVoltage(float(msg.payload))
	elif msg.topic == "/charger/setpoint/power" and voltage:
		current = float(msg.payload) / voltage
		current = min(maxCurrent, current)
		current = max(0, current)
		hcs.SetOutputCurrent(current)
		print("Setting output current to " + str(current))
		sys.stdout.flush()
		powerTimeout = 20

hcs=mansonlib.HCS()
hcs.OpenPort('/dev/ttyUSB1')
maxVoltage = False
maxCurrent = False
voltage = 0
powerTimeout = 0

while not maxVoltage:
	maxVoltage = hcs.GetMaxSet('V')
	time.sleep(0.1)

while not maxCurrent:
	maxCurrent = hcs.GetMaxSet('C')
	time.sleep(0.1)

maxPower = maxVoltage * maxCurrent

client = mqtt.Client("mansonCharger", userdata=hcs)
client.on_message = on_message
client.connect("localhost", 1883, 60)
client.subscribe("/charger/setpoint/power")
client.subscribe("/charger/setpoint/voltage")

client.publish("/charger/info/maxvoltage", maxVoltage, retain=True)
client.publish("/charger/info/maxpower", maxPower, retain=True)
client.publish("/charger/setpoint/voltage", hcs.GetOutputSetting('V'), retain=True)

while True:
	try:
		voltage = hcs.GetOutputReading('V')
		current = hcs.GetOutputReading('C')
		hcs.SetRearMode()
		
		if voltage == False:
			voltage = 0
			current = 0
		
		client.publish("/charger/info/voltage", voltage)
		client.publish("/charger/info/current", current)
		client.publish("/charger/info/power", voltage * current)
		client.publish("/charger/info/maxpower", voltage * maxCurrent)
		
		if powerTimeout == 0:
			print("Timeout")
			hcs.SetOutputCurrent(0)
		else:
			powerTimeout = powerTimeout - 1
			
		client.loop(timeout=0.2)

	#These can occur when the device is turned off or back on		
	except UnicodeDecodeError:
		continue
	except ValueError:
		continue

