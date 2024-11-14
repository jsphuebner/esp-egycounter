#!/usr/bin/python3

import urllib.request
import paho.mqtt.client as mqtt
import time, json, re

with open("config.json") as configFile:
	config = json.load(configFile)

client = mqtt.Client("keba")
client.connect(config['broker']['address'], 1883, 60)

while True:
    try:
        req = urllib.request.urlopen(config['keba']['uri'])
        html = req.read().decode("utf-8")
        power = float(re.search(r'Power --><b>([0-9,]+)', html).group(1).replace(',', '.'))
        energy = float(re.search(r'Energy --><b>([0-9,]+)', html).group(1).replace(',', '.'))
        total = float(re.search(r'EnTotal --><b>([0-9,]+)', html).group(1).replace(',', '.'))
        client.publish("/evse/energy", energy)
        client.publish("/evse/power", power)
        client.publish("/evse/total", total)
    except urllib.error.URLError:
        continue
        
    time.sleep(1)
