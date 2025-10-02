#!/usr/bin/python3

import Adafruit_BBIO.GPIO as GPIO
import Adafruit_BBIO.PWM as PWM
import paho.mqtt.client as mqtt
import time, json

def on_message(client, userdata, msg):
    global ccsState, invState, controlState, switchState
    
    if msg.topic == "pyPlc/fsm_state":
        ccsState = msg.payload.decode("utf-8")
    elif msg.topic == "sungrow/system_state":
        invState = msg.payload.decode("utf-8")
        
    if controlState == "RunStationary":
        level = GPIO.input("P8_8")
        #toggle LED, sampling switch state is only possible when LED is on
        if level:
            switchState = GPIO.input("P8_7")
            GPIO.output("P8_8", GPIO.LOW)            
        else:
            GPIO.output("P8_8", GPIO.HIGH)
            
        if switchState:
            mqttclient.publish("pyPlc/enabled", 1)
        else:
            mqttclient.publish("pyPlc/enabled", 0)

        if ccsState == "CableCheck" or ccsState == "CurrentDemand":
            controlState = "SwitchOffInverter"
    elif controlState == "SwitchOffInverter":
        client.publish("sungrow/start_stop/set", "Stop")
        controlState = "SwitchToCCS"
    elif controlState == "SwitchToCCS":
        GPIO.output("P8_8", GPIO.HIGH) #Turn on solid LED
        if invState == "Stop":
            GPIO.output("P9_15", GPIO.HIGH) # change over to CCS
            client.publish("sungrow/start_stop/set", "Start") #Start inverter
            controlState = "RunCCS"
    elif controlState == "RunCCS":
        switchState = GPIO.input("P8_7")
        if not switchState or ccsState != "CurrentDemand":
            controlState = "StopCCS"
    elif controlState == "StopCCS":
        client.publish("sungrow/start_stop/set", "Stop")
        mqttclient.publish("pyPlc/enabled", 0)
        controlState = "SwitchToStationary"
    elif controlState == "SwitchToStationary":
        if invState == "Stop":
            GPIO.output("P9_15", GPIO.LOW) # change over to stationary battery
            client.publish("sungrow/start_stop/set", "Start") #Start inverter
            controlState = "RunStationary"
            
    client.publish("pyPlc/controlstate", controlState)

GPIO.setup("P8_7", GPIO.IN) #Enable switch
GPIO.setup("P8_8", GPIO.OUT) #LED of enable switch
GPIO.setup("P9_23", GPIO.OUT) #HV precharge supply
GPIO.setup("P9_15", GPIO.OUT) #change over relay between V2G and stationary battery
PWM.start("P8_13", 95, 1000)

with open("config.json") as configFile:
    config = json.load(configFile)

mqttclient = mqtt.Client(client_id = "ccscontrol")
mqttclient.on_message = on_message
mqttclient.connect(config['broker']['address'], 1883, 60)
mqttclient.subscribe("pyPlc/fsm_state")
mqttclient.subscribe("sungrow/system_state")
time.sleep(0.1)
ccsState = "None"
switchOffTime = 0
switchState = True
invState = "Start"
controlState = "RunStationary"
mqttclient.loop_forever()

