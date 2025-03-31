#!/usr/bin/python3

# This file was derived from Dalas BatteryEmulator for BYD batteries
# https://github.com/dalathegreat/Battery-Emulator/blob/main/Software/src/inverter/BYD-CAN.cpp

import paho.mqtt.client as mqtt
import time, json, can

def on_message(client, userdata, msg):
    global batSoc, batVoltage, maxCurrent, socLimit
    
    if msg.topic == "pyPlc/soc":
        batSoc = float(msg.payload)
    elif msg.topic == "pyPlc/soclimit":
        socLimit = float(msg.payload)
    elif msg.topic == "pyPlc/target_current":
        maxCurrent = float(msg.payload)
    elif msg.topic == "pyPlc/charger_voltage":
        batVoltage = float(msg.payload)

with open("config.json") as configFile:
    config = json.load(configFile)

client = mqtt.Client(client_id = "bydcan")
client.on_message = on_message
client.connect(config['broker']['address'], 1883, 60)
client.subscribe("pyPlc/soc")
client.subscribe("pyPlc/soclimit")
client.subscribe("pyPlc/target_current")
client.subscribe("pyPlc/charger_voltage")
batVoltage = 360
batSoc = 50
socLimit = 85
batCurrent = 1
maxCurrent = 15
runtime = 0

filters = [
{"can_id": 0x151, "can_mask": 0xFFF, "extended": False},
{"can_id": 0x091, "can_mask": 0xFFF, "extended": False},
{"can_id": 0x0D1, "can_mask": 0xFFF, "extended": False},
{"can_id": 0x111, "can_mask": 0xFFF, "extended": False},
]
bus=can.interface.Bus(interface='socketcan', channel='can0', can_filters = filters)

def sendInitialData(bus):
    #Send 25.5 kWh capacity
    msg = can.Message(arbitration_id=0x250, data=[0x03, 0x16, 0x00, 0x66, 0x00, 0xFF, 0x02, 0x09], is_extended_id=False)
    bus.send(msg)
    msg = can.Message(arbitration_id=0x290, data=[0x06, 0x37, 0x10, 0xD9, 0x00, 0x00, 0x00, 0x00], is_extended_id=False)
    bus.send(msg)
    msg = can.Message(arbitration_id=0x2D0, data=[0x00, 0x42, 0x59, 0x44, 0x00, 0x00, 0x00, 0x00], is_extended_id=False)
    bus.send(msg)
    msg = can.Message(arbitration_id=0x3D0, data=[0x00, 0x42, 0x61, 0x74, 0x74, 0x65, 0x72, 0x79], is_extended_id=False)
    bus.send(msg)
    msg = can.Message(arbitration_id=0x3D0, data=[0x01, 0x2D, 0x42, 0x6F, 0x78, 0x20, 0x50, 0x72], is_extended_id=False)
    bus.send(msg)
    msg = can.Message(arbitration_id=0x3D0, data=[0x02, 0x65, 0x6D, 0x69, 0x75, 0x6D, 0x20, 0x48], is_extended_id=False)
    bus.send(msg)
    msg = can.Message(arbitration_id=0x3D0, data=[0x03, 0x56, 0x53, 0x00, 0x00, 0x00, 0x00, 0x00], is_extended_id=False)
    bus.send(msg)
    
def send2SMessages(bus):
    global batSoc, socLimit
    
    limitedChargeCurrent = int(min(maxCurrent, 20) * 10)
    
    if batSoc >= socLimit:
        limitedChargeCurrent = 0

    msg = can.Message(arbitration_id=0x110, data=[0x0F, 0xA0, 0x0B, 0xB8, 0x00, 0xC8, 0x00, limitedChargeCurrent], is_extended_id=False)
    bus.send(msg)
    
def send10SMessages(bus):
    global batVoltage, batSoc, batCurrent
    socLo = int(batSoc * 100) & 0xFF
    socHi = int(batSoc * 100) >> 8
    vtgLo = int(batVoltage * 10) & 0xFF
    vtgHi = int(batVoltage * 10) >> 8
    curLo = int(batCurrent * 10) & 0xFF
    curHi = int(batCurrent * 10) >> 8
    
    msg = can.Message(arbitration_id=0x150, data=[socHi, socLo, 0x27, 0x10, 0x10, 0x27, 0x10, 0x27], is_extended_id=False)
    bus.send(msg)
    msg = can.Message(arbitration_id=0x1D0, data=[vtgHi, vtgLo, curHi, curLo, 0x00, 0xC8, 0x03, 0x08], is_extended_id=False)
    bus.send(msg)
    msg = can.Message(arbitration_id=0x210, data=[0x00, 0xC8, 0x00, 0xC8, 0x00, 0x00, 0x00, 0x00], is_extended_id=False)
    bus.send(msg)

def send60SMessages(bus):
    msg = can.Message(arbitration_id=0x190, data=[0x00, 0x00, 0x03, 0x00, 0x00, 0x00, 0x00, 0x00], is_extended_id=False)
    bus.send(msg)

#sendInitialData(bus)
client.loop_start()
lastReceived = 0

while True:
    message = bus.recv(0)
    
    if message:
        lastReceived = time.time()
        if message.arbitration_id == 0x151:
            if (message.data[0] & 0x01) == 0x01:
                print("Received indentification request")
                sendInitialData(bus);
        
    if (time.time() - lastReceived) < 15: #only send if inverter is alive
        send2SMessages(bus)
        
        if (runtime % 10) == 0:
            send10SMessages(bus)
        if (runtime % 60) == 0:
            send60SMessages(bus)

    time.sleep(2)
    runtime = runtime + 2

