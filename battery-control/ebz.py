#!/usr/bin/python

import serial, time, requests, sys

ser = serial.Serial('/dev/ttyUSB0', 9600, timeout=0.2)

ser.flushInput()
ser.write("GMOD\r")

print(ser.read_until('\r'))
ser.flushInput()

ser.write("VOLT488\r")
print(ser.read_until('\r'))

lastSolarPower = 0

while True:
	try:
		ser.flushInput()
		ser.write("GETD\r")
		output = ser.read_until('\r')
		r = requests.get("http://192.168.178.54/cmd?cmd=get%20ptotal")
		ptotal = float(r.text)
		if len(output) == 10:
			voltage = float(output[:4]) / 100
			current = float(output[4:-2]) / 100
			power = voltage * current
			solarpower = power - ptotal
			print ("Ubat: " + str(voltage) + "V Pbat: " + str(power) + "W Pgrid: " + str(ptotal) + "W Psolar: " + str(solarpower) + "W")
			if solarpower > 15 or power != 0:
				lastSolarPower = (max(-100, solarpower) + lastSolarPower) / 2 #IIR Filter
				newcurrent = min(16, max(0, (lastSolarPower / voltage) * 0.95))
			else:
				newcurrent = 0
			ser.flushInput()
			ser.write("CURR%.3d\r" % (newcurrent * 10))
			print("Setting new current setpoint to " + str(newcurrent) + "A ... " + ser.read_until('\r'))
			sys.stdout.flush()
	except requests.exceptions.ConnectionError:
		print ("Connection error, setting current to 0")
		ser.write("CURR000\r")
		continue

