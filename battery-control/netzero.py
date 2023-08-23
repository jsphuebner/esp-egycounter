#!/usr/bin/python3

import time, sys, json, urllib.request
from datetime import datetime
import paho.mqtt.client as mqtt

def getUnixTime():  
	return (datetime.now() - datetime(1970, 1, 1)).total_seconds()
	
def updatePriceList():
	global priceListObtained
	global priceList
	global config

	req = urllib.request.urlopen(config['netzero']['priceuri'])
	data = req.read()
	priceList = json.loads(data)
	priceListObtained = getUnixTime()
	print('Obtained pricelist')
	
def getCurrentPrice():
	global priceList

	timeNow = getUnixTime() * 1000
	for item in priceList['data']:
		if item['end_timestamp'] > timeNow:
			return float(item['marketprice'])

def setChargePower(client, gridPower):
	global lastChargerPower
	global maxChargePower
	global lastInverterPower
	global config
	
	solarpower = lastChargerPower - gridPower
	solarpower = min(solarpower, maxChargePower)

	if getCurrentPrice() < config['netzero']['gridchargethresh']:
		solarpower = min(1000, maxChargePower)
	
	if lastInverterPower > 10:
		client.publish("/charger/setpoint/power", 0)
	else:
		client.publish("/charger/setpoint/power", max(0, solarpower))
	
def setInverterPower(client, gridPower):
	global config
	global lastBatteryVoltage
	global lastChargerPower
	global maxInverterPower
	global maxDischargePower
	global lastInverterPower
	
	ki = config['netzero']['powerki']
	setInverterPower.errSum = setInverterPower.errSum + gridPower
	setInverterPower.errSum = max(0, setInverterPower.errSum)
	setInverterPower.errSum = min(maxDischargePower / ki, maxInverterPower / ki, setInverterPower.errSum)

	powerSetpoint = gridPower * config['netzero']['powerkp'] + setInverterPower.errSum * ki
	powerSetpoint = min(powerSetpoint, maxInverterPower, maxDischargePower)
	
	if getCurrentPrice() < config['netzero']['nobatterypowerthresh']:
		powerSetpoint = 0
	
	if lastInverterPower < 25 or lastChargerPower > 10 or maxDischargePower < 50:
	   powerSetpoint = 0
	   setInverterPower.errSum = 0
			
	lastInverterPower = powerSetpoint
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
	global maxChargePower
	global maxDischargePower
	global priceListObtained

	if msg.topic == config['meter']['topic']:
		try:
			if (getUnixTime() - priceListObtained) >= 3600:
				updatePriceList()
			data = json.loads(msg.payload)
			ptotal = data['ptotal']
			lastGridPower = (ptotal + lastGridPower) / 2
			setChargePower(client, lastGridPower)
			setInverterPower(client, lastGridPower)
			client.publish("/meter/power", ptotal)
			client.publish("/meter/energy", data['etotal'])
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
	elif msg.topic == "/bms/info/chargepower":
		maxChargePower = float(msg.payload)
	elif msg.topic == "/bms/info/dischargepower":
		maxDischargePower = float(msg.payload)

with open("config.json") as configFile:
	config = json.load(configFile)
	
client = mqtt.Client("netZeroController")
client.on_message = on_message
client.connect(config['broker']['address'], 1883, 60)
client.subscribe(config['meter']['topic'])
client.subscribe("/charger/info/maxpower")
client.subscribe("/charger/info/power")
client.subscribe("/inverter/info/power")
client.subscribe("/inverter/info/maxpower")
client.subscribe("/inverter/info/udc")
client.subscribe("/bms/info/chargepower")
client.subscribe("/bms/info/dischargepower")

client.publish("/charger/setpoint/voltage", config['netzero']['chargevoltage'])

maxInverterPower = 0
lastChargerPower = 0
lastInverterPower = 0
lastGridPower = 0
maxChargePower = 500
maxDischargePower = 500
lastBatteryVoltage = config['netzero']['uvlohyst']

setInverterPower.errSum = 0
setInverterPower.uvlo = False
priceList = { "data": [] }
priceListObtained = 0
updatePriceList()
print (getCurrentPrice())

client.loop_forever()

