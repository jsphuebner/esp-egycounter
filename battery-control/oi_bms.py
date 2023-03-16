#!/usr/bin/python3

import can, time, json
import paho.mqtt.client as mqtt

with open("config.json") as configFile:
    config = json.load(configFile)

client = mqtt.Client("oibms")
client.connect("localhost", 1883, 60)
cobId = 0x580 + config['bms']['nodeid'];

filters = [{"can_id": cobId, "can_mask": 0x7FF, "extended": False}]
bus=can.interface.Bus(bustype='socketcan', channel=config['bms']['can'], can_filters = filters)
idx = 0;
items = config['bms']['values']
names = list(items)
lookupById = dict((v,k) for k,v in items.items())

while True:
    bytes = [ 0x40, items[names[idx]] >> 8, 0x21, items[names[idx]] & 0xFF, 0, 0, 0, 0]
    msg = can.Message(arbitration_id=0x600 + config['bms']['nodeid'], data=bytes, is_extended_id=False)
    bus.send(msg)
    idx = (idx + 1) % len(items)
    message = bus.recv(0)
	
    if message:
        if message.arbitration_id == cobId:
            value = (message.data[4] + (message.data[5] << 8) + (message.data[6] << 16)) / 32
            name = lookupById[message.data[1] * 256 + message.data[3]]
            client.publish("/bms/info/" + name, value)

    client.loop(timeout=0.1)
    time.sleep(0.1)
