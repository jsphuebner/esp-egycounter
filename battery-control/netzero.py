#!/usr/bin/python

import time, sys, json
import paho.mqtt.client as mqtt
	
def setChargePower(client, gridPower):
	global lastChargerPower
	global chargerPower
	global inverterPower
	
	solarpower = lastChargerPower - gridPower
	
	if lastInverterPower > 10:
		client.publish("/charger/setpoint/power", 0)
	else:
		client.publish("/charger/setpoint/power", max(0, solarpower - 10))
	
def setInverterPower(client, gridPower):
	global lastChargerVoltage
	global lastChargerPower
	global maxInverterPower

	powerSetpoint = gridPower + setInverterPower.errSum / 5				

	if powerSetpoint < maxInverterPower:
		setInverterPower.errSum = setInverterPower.errSum + gridPower
		
	if powerSetpoint > 20 and lastChargerPower < 20:
		voltagePowerLimit = (lastChargerVoltage - 44) * 500
		powerSetpoint = min(voltagePowerLimit, powerSetpoint)
	else:
		powerSetpoint = 0
		setInverterPower.errSum = 0
		
	client.publish("/inverter/setpoint/power", powerSetpoint)		

def publishBatteryPower(client):
	global lastChargerPower
	global lastInverterPower

	if lastInverterPower > lastChargerPower:
		client.publish("/battery/power", -lastInverterPower)
	else:
		client.publish("/battery/power", lastChargerPower)


def on_message(client, userdata, msg):
	global lastChargerPower
	global lastChargerVoltage
	global lastInverterPower
	global maxInverterPower
	global lastGridPower

	if msg.topic == "/ebz/readings":
		try:
			data = json.loads(msg.payload)
			ptotal = data['ptotal']
			lastGridPower = (ptotal + lastGridPower) / 2
			setChargePower(client, lastGridPower)
			setInverterPower(client, lastGridPower)
		except ValueError:
			return
	elif msg.topic == "/charger/info/voltage":
		chargerVoltage = float(msg.payload)
		lastChargerVoltage = (chargerVoltage + lastChargerVoltage * 3) / 4 #IIR Filter
		client.publish("/battery/voltage", lastChargerVoltage)
	elif msg.topic == "/charger/info/power":
		chargerPower = float(msg.payload)
		lastChargerPower = round((chargerPower + lastChargerPower) / 2, 2) #IIR filter
		publishBatteryPower(client)
	elif msg.topic == "/inverter/info/power":
		inverterPower = float(msg.payload)		
		lastInverterPower = (inverterPower + lastInverterPower) / 2 #IIR Filter
		publishBatteryPower(client)
	elif msg.topic == "/inverter/info/maxpower":
		maxInverterPower = float(msg.payload)
	
client = mqtt.Client("netZeroController")
client.on_message = on_message
client.connect("localhost", 1883, 60)
client.subscribe("/ebz/readings")
client.subscribe("/charger/info/maxpower")
client.subscribe("/charger/info/voltage")
client.subscribe("/charger/info/power")
client.subscribe("/inverter/info/power")
client.subscribe("/inverter/info/maxpower")

client.publish("/charger/setpoint/voltage", 52.6)

maxInverterPower = 0
lastChargerPower = 0
lastInverterPower = 0
lastGridPower = 0
lastChargerVoltage = 0

setInverterPower.errSum = 0

client.loop_forever()

