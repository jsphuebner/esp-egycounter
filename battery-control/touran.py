#!/usr/bin/python3

import urllib.request
import paho.mqtt.client as mqtt
import time, json

with open("config.json") as configFile:
	config = json.load(configFile)

client = mqtt.Client("touran")
client.connect(config['broker']['address'], 1883, 60)

while True:
    try:
        req = urllib.request.urlopen("http://192.168.188.21/cmd?cmd=get%20soc,iacobc,uacobc")
        data = req.read().split()
        soc = float(data[0])
        iac = float(data[1])
        uac = float(data[2])
        power = uac * iac
        client.publish("/touran/soc", soc)
        client.publish("/touran/power", power)
    except urllib.error.URLError:
        continue
        
    time.sleep(1)
