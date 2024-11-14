#!/usr/bin/python3

import Adafruit_BBIO.GPIO as GPIO
import can
import paho.mqtt.client as mqtt
import time, json

def on_message(client, hcs, msg):
	global powerTimeout
	global batVoltage
	global maxVoltage
	global powerSetpoint
	global lastNonZeroCommand
	
	if msg.topic == "/charger/setpoint/voltage":
		maxVoltage = float(msg.payload)
	elif msg.topic == "/battery/voltage":
	    batVoltage = float(msg.payload)
	elif msg.topic == "/charger/setpoint/power":
		power = float(msg.payload)
		
		if power > 20:
			lastNonZeroCommand = time.time()
		
		#When transitioning to 0 power preload integrator to a sag of 1.3V potentially caused by inverter
		if power == 0:
			powerRegulator.errsum = max(batVoltage, 44) / ki
			
		powerSetpoint = power
		powerTimeout = 20
		
def powerRegulator(actualPower, wantedPower, minVoltage, maxVoltage, kp, ki):
	err = wantedPower - actualPower
	powerRegulator.errsum = powerRegulator.errsum + err
	powerRegulator.errsum = min(powerRegulator.errsum, maxVoltage / ki)
	powerRegulator.errsum = max(powerRegulator.errsum, minVoltage / ki)
	
	output = kp * err + ki * powerRegulator.errsum
	outputLimited = min(output, maxVoltage)
	outputLimited = max(outputLimited, minVoltage)
			
	return outputLimited

with open("config.json") as configFile:
	config = json.load(configFile)

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, "flatpackCharger")
client.on_message = on_message
client.connect(config['broker']['address'], 1883, 60)
client.subscribe("/charger/setpoint/power")
client.subscribe("/charger/setpoint/voltage")
client.subscribe("/battery/voltage")

minVoltage = 43
voltage = minVoltage
maxVoltage = 0
maxCurrent = 25
powerSetpoint = 0
filteredPowerSetpoint = 0
powerTimeout = 0
batVoltage = 45
kp = 0.001
ki = 0.0001
serial = False
lastNonZeroCommand = time.time() - 3570
chargerState = True

powerRegulator.errsum = minVoltage / ki

filters = [
{"can_id": 0x05014400, "can_mask": 0x1FFFFFFF, "extended": True},
{"can_id": 0x05014004, "can_mask": 0x1FFFFFFF, "extended": True},
{"can_id": 0x0501400C, "can_mask": 0x1FFFFFFF, "extended": True}
]

bus=can.interface.Bus(bustype='socketcan', channel=config['charger']['can'], can_filters = filters)
GPIO.setup(config['charger']['gpio'], GPIO.OUT)
GPIO.output(config['charger']['gpio'], GPIO.HIGH)

while True:
	message = bus.recv(0)
	
	if message:
		if message.arbitration_id == 0x05014400:
			serial = message.data
			#Send walkin
			msg = can.Message(arbitration_id=0x05004804, data=serial, is_extended_id=True)
			bus.send(msg)
			#print("Sent walkin to serial " + str(serial))
		elif message.arbitration_id == 0x05014004:
			temperature = message.data[7]
			current = (message.data[1] + message.data[2] * 256) / 10
			voltage = (message.data[3] + message.data[4] * 256) / 100
			power = voltage * current
			client.publish("/charger/info/temperature", temperature)
			client.publish("/charger/info/voltage", voltage)
			client.publish("/charger/info/current", current)
			client.publish("/charger/info/power", power)
			client.publish("/charger/info/maxpower", voltage * maxCurrent)
			regulatedVoltage = powerRegulator(power, powerSetpoint, minVoltage, maxVoltage, kp, ki) * 100
			lobyte = int(regulatedVoltage % 256)
			hibyte = int(regulatedVoltage / 256)
			msg = can.Message(arbitration_id=0x05FF4005, data=[maxCurrent * 10, 0, lobyte, hibyte, lobyte, hibyte, lobyte, hibyte + 1] , is_extended_id=True)
			bus.send(msg)
		elif message.arbitration_id == 0x0501400C:
			temperature = message.data[0]
			voltage = (message.data[3] + message.data[4] * 256) / 100
			client.publish("/charger/info/temperature", temperature)
			client.publish("/charger/info/voltage", voltage)
			client.publish("/charger/info/current", 0)
			client.publish("/charger/info/power", 0)
			client.publish("/charger/info/maxpower", 0)

	if (time.time() - lastNonZeroCommand) > 3600 and chargerState:
		GPIO.output(config['charger']['gpio'], GPIO.LOW)
		client.publish("/charger/info/state", "off")
		client.publish("/charger/info/power", 0)
		chargerState = False
	elif not chargerState and filteredPowerSetpoint > 60:
		GPIO.output(config['charger']['gpio'], GPIO.HIGH)
		client.publish("/charger/info/state", "on")
		chargerState = True
		
	filteredPowerSetpoint = (powerSetpoint + filteredPowerSetpoint * 31) / 32

	client.loop(timeout=0.1)
