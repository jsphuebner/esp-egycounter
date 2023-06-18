#!/usr/bin/python3

import can, time, json
import paho.mqtt.client as mqtt

with open("config.json") as configFile:
    config = json.load(configFile)

client = mqtt.Client("oibms")
client.will_set("/bms/info/dischargepower", 0)
client.will_set("/bms/info/chargepower", 0)
client.connect(config['broker']['address'], 1883, 60)
cobId = 0x580 + config['bms']['nodeid'];

filters = [{"can_id": cobId, "can_mask": 0x7FF, "extended": False}]
bus=can.interface.Bus(bustype='socketcan', channel=config['bms']['can'], can_filters = filters)
idx = 0;
items = config['bms']['values']
names = list(items)
lookupById = dict((v,k) for k,v in items.items())
lookupById[5] = "balance"

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
            
            if name == config['bms']['minvtgname']:
                maxDischargePower = config['bms']['plimit'] * (value - config['bms']['cellmin']) / 30
                maxDischargePower = min(maxDischargePower, config['bms']['plimit'])
                maxDischargePower = max(maxDischargePower, 0)
                client.publish("/bms/info/dischargepower", maxDischargePower)
                bytes[0] = 0x23
                bytes[1] = 0
                bytes[3] = 5
                if value > config['bms']['balancestart']: #enable balancing
                    bytes[4] = 32
                else: #disable balancing
                    bytes[4] = 0
                msg = can.Message(arbitration_id=0x600 + config['bms']['nodeid'], data=bytes, is_extended_id=False)
                bus.send(msg)
            elif name == config['bms']['maxvtgname']:
                maxChargePower = config['bms']['plimit'] * (config['bms']['cellmax'] - value) / 30
                maxChargePower = min(maxChargePower, config['bms']['plimit'])
                maxChargePower = max(maxChargePower, 0)
                client.publish("/bms/info/chargepower", maxChargePower)
            elif name == config['bms']['totalvtgname']:
                client.publish("/battery/voltage", value / 1000 + 3.3)
                

    client.loop(timeout=0.1)
    time.sleep(0.1)
