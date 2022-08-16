#!/usr/bin/python3

import can
import paho.mqtt.client as mqtt
import time

def on_message(client, hcs, msg):
	global powerTimeout
	global voltage
	global maxVoltage
	global powerSetpoint
	
	if msg.topic == "/charger/setpoint/voltage":
		maxVoltage = float(msg.payload)
	elif msg.topic == "/charger/setpoint/power":
		power = float(msg.payload)
		
		#When transitioning to 0 power preload integrator to a sag of 1V potentially caused by inverter
		if power == 0 and powerSetpoint > 0:
			powerRegulator.errsum = (voltage - 1) / ki
			
		powerSetpoint = power
		powerTimeout = 20
		
def powerRegulator(actualPower, wantedPower, minVoltage, maxVoltage, kp, ki):
	err = wantedPower - actualPower
	errSumTemp = powerRegulator.errsum + err
	
	output = kp * err + ki * errSumTemp
	outputLimited = min(output, maxVoltage)
	outputLimited = max(outputLimited, minVoltage)
	
	if output == outputLimited:
		powerRegulator.errsum = errSumTemp
		
	return outputLimited

with open("config.json") as configFile:
	config = json.load(configFile)

client = mqtt.Client("flatpackCharger")
client.on_message = on_message
client.connect("localhost", 1883, 60)
client.subscribe("/charger/setpoint/power")
client.subscribe("/charger/setpoint/voltage")

minVoltage = 43
voltage = minVoltage
maxVoltage = 0
maxCurrent = 20
powerSetpoint = 0
powerTimeout = 0
kp = 0.001
ki = 0.0001
serial = False

powerRegulator.errsum = minVoltage / ki

bus=can.interface.Bus(bustype='socketcan', channel=config['charger']['can'], bitrate=125000)

while True:
	message = bus.recv(0)
	
	if message:
		if message.arbitration_id == 0x05014400:
			serial = message.data
			#Send walkin
			msg = can.Message(arbitration_id=0x05004804, data=serial, is_extended_id=True)
			bus.send(msg)
			print("Sent walkin to serial " + str(serial))
		elif message.arbitration_id == 0x05014004:
			temperature = message.data[0]
			current = (message.data[1] + message.data[2] * 256) / 10
			voltage = (message.data[3] + message.data[4] * 256) / 100
			power = voltage * current
			client.publish("/charger/info/voltage", voltage)
			client.publish("/charger/info/current", current)
			client.publish("/charger/info/power", power)
			client.publish("/charger/info/maxpower", voltage * maxCurrent)
			regulatedVoltage = powerRegulator(power, powerSetpoint, minVoltage, maxVoltage, kp, ki) * 100
			lobyte = int(regulatedVoltage % 256)
			hibyte = int(regulatedVoltage / 256)
			print ("Received status, temperature={0} current={1}, voltage={2}, power={3}, setpoint={4}".format(temperature, current, voltage, power, regulatedVoltage / 100))
			msg = can.Message(arbitration_id=0x05FF4005, data=[maxCurrent * 10, 0, lobyte, hibyte, lobyte, hibyte, lobyte, hibyte + 1] , is_extended_id=True)
			bus.send(msg)
	client.loop(timeout=0.1)
