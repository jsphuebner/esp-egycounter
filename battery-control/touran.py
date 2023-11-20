#!/usr/bin/python3

import urllib.request, socket
import paho.mqtt.client as mqtt
import time, json

def on_message(client, userdata, msg):
    global price
    
    price = float(msg.payload)

with open("config.json") as configFile:
	config = json.load(configFile)

client = mqtt.Client("touran")
client.on_message = on_message
client.connect(config['broker']['address'], 1883, 60)
client.subscribe("/spotmarket/pricenow")

price = 200

while True:
    try:
        req = urllib.request.urlopen(config['touran']['uri'] + "get%20soc,iacobc,uacobc,obcsoclimit", timeout=1)
        data = req.read().split()
        soc = float(data[0])
        iac = float(data[1])
        uac = float(data[2])
        soclim = float(data[3])
        power = uac * iac
        client.publish("/touran/soc", soc)
        client.publish("/touran/power", power)
        
        if float(msg.payload) < config['touran']['startprice'] and soclim < 50:
            urllib.request.urlopen(config['touran']['uri'] + "set%20obcsoclimit%20" + config['touran']['stopsoc'], timeout=1)
    except urllib.error.URLError:
        time.sleep(10)
        continue
    except socket.timeout:
        time.sleep(10)
        continue
        
    client.loop(timeout=0.1)
    time.sleep(1)
