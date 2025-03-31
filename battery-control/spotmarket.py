#!/usr/bin/python3

import time, json, urllib.request
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
	client.publish("/spotmarket/pricelist", data, retain=True)
	priceList = json.loads(data)
	priceListObtained = getUnixTime()
	print('Obtained pricelist')
	
def getCurrentPrice():
	global priceList

	timeNow = getUnixTime() * 1000
	for item in priceList['data']:
		if item['end_timestamp'] > timeNow:
			return float(item['marketprice'])

with open("config.json") as configFile:
	config = json.load(configFile)
	
client = mqtt.Client(client_id = "spotmarket")
client.connect(config['broker']['address'], 1883, 60)

priceList = { "data": [] }
priceListObtained = 0
#updatePriceList()
#print (getCurrentPrice())

while True:
	if (getUnixTime() - priceListObtained) >= 3600:
		updatePriceList()
		client.publish("/spotmarket/pricenow", getCurrentPrice(), retain=True)

	client.publish("/spotmarket/pricenow", getCurrentPrice(), retain=True)
	client.loop(timeout=0.1)
	time.sleep(10)
