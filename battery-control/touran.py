#!/usr/bin/python3

import urllib.request
import paho.mqtt.client as mqtt
import time, json

def on_message(client, userdata, msg):
    global config
	
    if float(msg.payload) < config['touran']['startprice']:
        req = urllib.request.urlopen("http://192.168.188.21/cmd?cmd=get%20obcsoclim", timeout=1)
        if float(req.read()) < 50:
            urllib.request.urlopen("http://192.168.188.21/cmd?cmd=set%20obcsoclim {0}".format(config['touran']['stopsoc']), timeout=1)
            print(req.read())

with open("config.json") as configFile:
	config = json.load(configFile)

client = mqtt.Client("touran")
client.on_message = on_message
client.connect(config['broker']['address'], 1883, 60)
client.subscribe("/spotmarket/pricenow")

while True:
    try:
        req = urllib.request.urlopen("http://192.168.188.21/cmd?cmd=get%20soc,iacobc,uacobc", timeout=1)
        data = req.read().split()
        soc = float(data[0])
        iac = float(data[1])
        uac = float(data[2])
        power = uac * iac
        client.publish("/touran/soc", soc)
        client.publish("/touran/power", power)
    except urllib.error.URLError:
        continue
        
    client.loop(timeout=0.1)
    time.sleep(1)
