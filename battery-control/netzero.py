#!/usr/bin/python

import time, sys, json
import paho.mqtt.client as mqtt
	
def setChargePower(client, gridPower):
	global lastChargerPower
	
	solarpower = lastChargerPower - gridPower
	
	if lastInverterPower > 10:
		client.publish("/charger/setpoint/power", 0)
	else:
		client.publish("/charger/setpoint/power", max(0, solarpower - 10))
	
def setInverterPower(client, gridPower):
	global config
	global lastBatteryVoltage
	global lastChargerPower
	global maxInverterPower

	powerSetpoint = gridPower * config['netzero']['powerkp'] + setInverterPower.errSum * config['netzero']['powerki']				

	if powerSetpoint < maxInverterPower:
		setInverterPower.errSum = setInverterPower.errSum + gridPower
		
	if lastBatteryVoltage <= config['netzero']['uvlothresh']:
		setInverterPower.uvlo = True
	elif lastBatteryVoltage > config['netzero']['uvlohyst']:
		setInverterPower.uvlo = False
		
	if powerSetpoint > 20 and lastChargerPower < 20 and not setInverterPower.uvlo:
		voltagePowerLimit = (lastBatteryVoltage - config['netzero']['uvlothresh']) * config['netzero']['voltagekp']
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
	global config
	global lastChargerPower
	global lastBatteryVoltage
	global lastInverterPower
	global maxInverterPower
	global lastGridPower

	if msg.topic == config['meter']['topic']:
		try:
			data = json.loads(msg.payload)
			ptotal = data['ptotal']
			lastGridPower = (ptotal + lastGridPower) / 2
			setChargePower(client, lastGridPower)
			setInverterPower(client, lastGridPower)
		except ValueError:
			return
	elif msg.topic == "/inverter/info/udc":
		batteryVoltage = float(msg.payload)
		lastBatteryVoltage = (batteryVoltage + lastBatteryVoltage * 3) / 4 #IIR Filter
		client.publish("/battery/voltage", lastBatteryVoltage)
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

with open("config.json") as configFile:
	config = json.load(configFile)
	
client = mqtt.Client("netZeroController")
client.on_message = on_message
client.connect("localhost", 1883, 60)
client.subscribe(config['meter']['topic'])
client.subscribe("/charger/info/maxpower")
client.subscribe("/charger/info/power")
client.subscribe("/inverter/info/power")
client.subscribe("/inverter/info/maxpower")
client.subscribe("/inverter/info/udc")

client.publish("/charger/setpoint/voltage", config['netzero']['chargevoltage'])

maxInverterPower = 0
lastChargerPower = 0
lastInverterPower = 0
lastGridPower = 0
lastBatteryVoltage = config['netzero']['uvlohyst']

setInverterPower.errSum = 0
setInverterPower.uvlo = False

client.loop_forever()

