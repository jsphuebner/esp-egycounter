#!/usr/bin/python3

import json, urllib3, urllib
import paho.mqtt.client as mqtt

def on_message(client, userdata, msg):
	global config
	
	if msg.topic == config['meter']['topic']:
		try:
			data = json.loads(msg.payload)
			data['pbat'] = on_message.pbat
			data = json.dumps(data)
			r = on_message.http.request('GET',config['logger']['uri'] + urllib.parse.quote_plus(data), timeout=1.0)
		except ValueError:
			print("Error in JSON string " + msg.payload)
	elif msg.topic == "/battery/power":
		on_message.pbat = float(msg.payload)


with open("config.json") as configFile:
	config = json.load(configFile)

client = mqtt.Client("submitToLogger")
client.on_message = on_message
client.connect(config['broker']['address'], 1883, 60)
client.subscribe(config['meter']['topic'])
client.subscribe("/battery/power")
on_message.pbat = 0
on_message.http = urllib3.PoolManager()

client.loop_forever()

