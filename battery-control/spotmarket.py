#!/usr/bin/python3

import time, json, urllib.request
from datetime import datetime, timedelta
import paho.mqtt.client as mqtt

def getUnixTime():  
	return (datetime.now() - datetime(1970, 1, 1)).total_seconds()

def getTimeStampPlusMinutes(dt, mins):
	return int((datetime.fromisoformat(dt)+timedelta(minutes=mins)).timestamp()*1000)
    
def updatePriceList():
	global priceListObtained
	global priceList
	global config

	req = urllib.request.urlopen(config['spotmarket']['priceuri'])
	data = req.read()
	priceList = json.loads(data)
	if config['spotmarket']['tstype'] == "iso":
		priceList['data'] = list(map(lambda x: ({
			'start_timestamp': getTimeStampPlusMinutes(x['date'], 0), 
			'end_timestamp': getTimeStampPlusMinutes(x['date'], 15), 
			'marketprice': x['value'] * 10}), priceList['data']))

	client.publish("/spotmarket/pricelist", json.dumps(priceList), retain=True)
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
	
client = mqtt.Client(client_id = "spotmarket2")
client.connect(config['broker']['address'], 1883, 60)

priceList = { "data": [] }
priceListObtained = 0

while True:
	if (getUnixTime() - priceListObtained) >= 3600:
		updatePriceList()
		client.publish("/spotmarket/pricenow", getCurrentPrice(), retain=True)

	client.publish("/spotmarket/pricenow", getCurrentPrice(), retain=True)
	client.loop(timeout=0.1)
	time.sleep(10)
