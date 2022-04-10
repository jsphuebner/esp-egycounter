#!/usr/bin/python

import json, urllib3
import paho.mqtt.client as mqtt

def on_message(client, userdata, msg):
	if msg.topic == "/ebz/readings":
		try:
			data = json.loads(msg.payload)
			data['pbat'] = on_message.pbat
			data = json.dumps(data)
			r = on_message.http.request('GET',"https://johanneshuebner.com/ebz/?key=<yourkey>&data=" + data)
		except ValueError:
			print("Error in JSON string " + msg.payload)
	elif msg.topic == "/battery/power":
		on_message.pbat = float(msg.payload)

client = mqtt.Client("submitToLogger")
client.on_message = on_message
client.connect("localhost", 1883, 60)
client.subscribe("/ebz/readings")
client.subscribe("/battery/power")
on_message.pbat = 0
on_message.http = urllib3.PoolManager()

client.loop_forever()

