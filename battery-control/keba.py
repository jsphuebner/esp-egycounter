#!/usr/bin/python3

import urllib.request
import paho.mqtt.client as mqtt
import time, json, re

with open("config.json") as configFile:
	config = json.load(configFile)

def setupOutput():
    # config['keba']['output'] = {"type": "gpio"|"numato", "port": "P9_16" | "/dev/ttyACM0:0"}
    out = config['keba'].get('output', {})
    otype = out.get('type')
    port = out.get('port')
    if otype == 'gpio':
        import Adafruit_BBIO.GPIO as GPIO
        GPIO.setup(port, GPIO.OUT)
        return lambda on: GPIO.output(port, GPIO.HIGH if on else GPIO.LOW)
    elif otype == 'numato':
        import serial
        dev, relay = port.rsplit(':', 1)
        def setRelay(on):
            with serial.Serial(dev, 19200, timeout=1) as ser:
                ser.write(("relay %s %s\r" % ("on" if on else "off", relay)).encode())
        return setRelay
    return None

setEnable = setupOutput()

def on_message(client, userdata, msg):
    if msg.topic == "/evse/enable" and setEnable is not None:
        try:
            setEnable(int(float(msg.payload)) == 1)
        except (ValueError, OSError) as e:
            print("Failed to set enable:", e)

client = mqtt.Client("keba")
client.on_message = on_message
client.connect(config['broker']['address'], 1883, 60)
client.subscribe("/evse/enable")
client.loop_start()

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
