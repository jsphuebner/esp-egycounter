#!/usr/bin/python3

import Adafruit_BBIO.GPIO as GPIO
import paho.mqtt.client as mqtt
import time, json, os

def on_message(client, userdata, msg):
    global ccsState, invState, controlState, switchState, config
    
    if msg.topic == "pyPlc/fsm_state":
        ccsState = msg.payload.decode("utf-8")
    elif msg.topic == "sungrow/system_state":
        invState = msg.payload.decode("utf-8")
    
    if ccsState == "PreCharging":
        GPIO.output(config["ccsctrl"]["prechargepin"], GPIO.HIGH)
    else:
        GPIO.output(config["ccsctrl"]["prechargepin"], GPIO.LOW)
       
    if controlState == "RunStationary":
        level = GPIO.input(config["ccsctrl"]["ledpin"])
        #toggle LED, sampling switch state is only possible when LED is on
        if level:
            switchState = GPIO.input(config["ccsctrl"]["enablepin"])
            GPIO.output(config["ccsctrl"]["ledpin"], GPIO.LOW)            
        else:
            GPIO.output(config["ccsctrl"]["ledpin"], GPIO.HIGH)
            
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
        GPIO.output(config["ccsctrl"]["ledpin"], GPIO.HIGH) #Turn on solid LED
        if ccsState == "CurrentDemand" and invState == "Stop":
            GPIO.output(config["ccsctrl"]["changeoverpin"], GPIO.HIGH) # change over to CCS
            client.publish("sungrow/start_stop/set", "Start") #Start inverter
            controlState = "RunCCS"
    elif controlState == "RunCCS":
        switchState = GPIO.input(config["ccsctrl"]["enablepin"])
        if not switchState or ccsState != "CurrentDemand":
            controlState = "StopCCS"
    elif controlState == "StopCCS":
        client.publish("sungrow/start_stop/set", "Stop")
        mqttclient.publish("pyPlc/enabled", 0)
        controlState = "SwitchToStationary"
    elif controlState == "SwitchToStationary":
        if invState == "Stop":
            GPIO.output(config["ccsctrl"]["changeoverpin"], GPIO.LOW) # change over to stationary battery
            client.publish("sungrow/start_stop/set", "Start") #Start inverter
            controlState = "RunStationary"
            
    client.publish("pyPlc/controlstate", controlState)

with open("config.json") as configFile:
    config = json.load(configFile)

GPIO.setup(config["ccsctrl"]["enablepin"], GPIO.IN) #Enable switch
GPIO.setup(config["ccsctrl"]["ledpin"], GPIO.OUT) #LED of enable switch
GPIO.setup(config["ccsctrl"]["prechargepin"], GPIO.OUT) #HV precharge supply
GPIO.setup(config["ccsctrl"]["changeoverpin"], GPIO.OUT) #change over relay between V2G and stationary battery
#PWM.start("P9_42", 95, 1000) #CP PWM

with open(config["ccsctrl"]["pwmbase"] + "period", "w") as f:
    f.write("1000000")
    
with open(config["ccsctrl"]["pwmbase"] + "duty_cycle", "w") as f:
    f.write("50000")
    
with open(config["ccsctrl"]["pwmbase"] + "enable", "w") as f:
    f.write("1")
    
os.system("/usr/bin/config-pin " + config["ccsctrl"]["pwmpin"] + " pwm")

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

