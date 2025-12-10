#!/usr/bin/python3

import time, sys, serial, json, crcmod.predefined
import paho.mqtt.client as mqtt
#from smllib import SmlStreamReader

def hex_to_int(hex):
    i = int(hex, 16)
    if i & 0x80000000:    # MSB set -> neg.
        return -((~i & 0xffffffff) + 1)
    else:
        return i


def on_message(client, userdata, msg):
    crc16_func = crcmod.predefined.mkCrcFun('x25')
    crc = crc16_func(msg.payload[0:-2])
    actualCrc = int.from_bytes(msg.payload[-2:], 'little')
    
    if crc == actualCrc:
        data = msg.payload.hex()
        
        search = '0177070100600100ff01'
        pos = data.find(search)
        if (pos > -1):
            pos = pos + len(search) + 8
            serial = data[pos:pos + 20]
            
        search = '0177070100010800ff'
        pos = data.find(search)
        if (pos > -1):
            pos = pos + len(search) + 34
            value = data[pos:pos + 16]
            try:
                etotal = float(hex_to_int(value)) / 10000 + 13146.35839844
            except:
                etotal = 0.0
        
        search = '0177070100100700ff01'
        pos = data.find(search)
        if (pos > -1):
            pos = pos + len(search) + 26
            value = data[pos:pos + 8]
            try:
                power = float(hex_to_int(value)) 
            except:
                power = 0.0
            
        cluster = {}
        cluster['id'] = serial
        cluster['ptotal'] = power
        cluster['etotal'] = etotal
        cluster['pphase'] = [0, 0, 0]
        client.publish(userdata, json.dumps(cluster))
		
with open("config.json") as configFile:
	config = json.load(configFile)

client = mqtt.Client(client_id = "smldecoder", userdata = config['meter']['topic'])
client.on_message = on_message
client.connect(config["broker"]["address"], 1883, 60)
client.subscribe(config['meter']['rawtopic'])

while True:
	client.loop(timeout=0.1)
	time.sleep(0.2)

