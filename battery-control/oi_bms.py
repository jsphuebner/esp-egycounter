#!/usr/bin/python3

import urllib.request, socket
import paho.mqtt.client as mqtt
import can, time, json

with open("config.json") as configFile:
	config = json.load(configFile)

client = mqtt.Client(client_id="oibms")
client.keepalive = 10
client.will_set("/bms/info/chargepower", 0)
client.will_set("/bms/info/dischargepower", 0)
client.connect(config['broker']['address'], 1883, 60)
lastPublish = { 0x1f4: 0, 0x1f5: 0 }

filters = [{"can_id": 0x1F4, "can_mask": 0x7F0, "extended": False}]
bus=can.interface.Bus(bustype='socketcan', channel=config['bms']['can'], can_filters = filters)
counters = {}

for cobId in range(500, 501 + config['bms']['modulecount']):
    counters[cobId] = [ 0, 1, 2, 3 ]
    counters[cobId][0] = time.time()
    counters[cobId][1] = time.time()
    counters[cobId][2] = time.time()
    counters[cobId][3] = time.time()

def checkCounters(counters):
    alive = True
    for cobId in counters:
        for timestamp in counters[cobId]:
            alive = alive and (timestamp - time.time()) < 2
    return alive

for message in bus:
    counter = message.data[7] >> 6 if message.arbitration_id == 0x1F4 else message.data[3] >> 6
    counters[message.arbitration_id][counter] = time.time()
    if message.arbitration_id == 0x1F4:
        ccl = float(message.data[0]) / 10
        dcl = float((message.data[1] >> 3) + ((message.data[2] & 0x3f) << 5)) / 10
        soc = float((message.data[2] >> 6) + (message.data[3] << 2)) / 10
        current = float(int.from_bytes(message.data[4:6], byteorder='little', signed=True)) / 10
        packVoltage = message.data[6] + ((message.data[7] & 0x3) << 8)
        
        if soc < 10:
            soc = 10 #Don't allow SoC < 10%
            
        if not checkCounters(counters):
            ccl = 0
            dcl = 0
        
        if (time.time() - lastPublish[0x1f4]) >= 1:
            client.publish("/bms/info/dischargepower", dcl * packVoltage)
            client.publish("/bms/info/chargepower", ccl * packVoltage)
            client.publish("/bms/info/soc", soc)
            client.publish("/bms/info/current", current)
            client.publish("/bms/info/packvoltage", packVoltage)
            lastPublish[0x1f4] = time.time()
            client.loop()

    elif message.arbitration_id == 0x1F5:
        umin = message.data[0] + (message.data[1] << 8)
        umax = message.data[2] + ((message.data[3] & 0x3f) << 8)
        
        if (time.time() - lastPublish[0x1f5]) >= 1:
            client.publish("/bms/info/umin", umin)
            client.publish("/bms/info/umax", umax)
            lastPublish[0x1f5] = time.time()


