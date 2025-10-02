#!/usr/bin/python3

import time, sys, json, re, math
from datetime import datetime
import paho.mqtt.client as mqtt
from picontroller import PiController

def calculateNetzero(ptotal):
    global config, v2gController
    
    v2gSpnt = v2gController.run(ptotal, 0)
    return v2gSpnt

def setControllerLimits():
    global config, v2gController
    
    chargeLimit = config['netzero']['evpower']
    if mqttVal('pyPlc/fsm_state') == "CurrentDemand":
        chargeLimit = min(chargeLimit, mqttVal('pyPlc/target_current') * mqttVal('pyPlc/charger_voltage'))
        if mqttVal('evfull'):
            chargeLimit = 0
    else:
        chargeLimit = min(chargeLimit, mqttVal('/bms/info/chargepower'))
    dischargeLimit = min(config['netzero']['evpower'], mqttVal('/bms/info/dischargepower'))
               
    if mqttVal('sungrow/system_state') == "Forced Run":
        v2gController.setMinMax(-chargeLimit, dischargeLimit)
    else:
        v2gController.setMinMax(0, 0)

def calculateSpotmarket(batSpnt):
    global config, batController

    price = mqttVal("/spotmarket/pricenow")        
    
    #We are connected to the EV battery and it is not yet full
    if mqttVal('pyPlc/fsm_state') == "CurrentDemand": 
        #if price > mqttVal('/grid/dischargethresh'):
        #    batSpnt = min(mqttVal('/bms/info/dischargepower'), mqttVal("/inverter/info/maxpower"))
        if price < mqttVal("/grid/evchargethresh"):
            batSpnt = mqttVal('pyPlc/target_current') * mqttVal('pyPlc/charger_voltage')
            batSpnt = -min(batSpnt, config['netzero']['evpower'])
            v2gController.resetIntegrator()
    else:
        if price < mqttVal('/grid/chargethresh') and mqttVal('/grid/chargepower') > -batSpnt:
            batSpnt = -min(mqttVal('/grid/chargepower'), mqttVal('/bms/info/chargepower'))
            v2gController.resetIntegrator()
    
    if batSpnt > 0 and price < mqttVal('/grid/dischargethresh'):
        batSpnt = 0
        v2gController.resetIntegrator()

    return batSpnt

def regulate(ptotal):
    mqttData['ptotal'] = ptotal
    setControllerLimits()
    v2gSpnt = calculateNetzero(ptotal)
    v2gSpnt = calculateSpotmarket(v2gSpnt)
    client.publish("/bidi/setpoint/power", -v2gSpnt)
    
    if mqttVal('pyPlc/fsm_state') == "CurrentDemand":
        client.publish("/bidi/power", mqttVal("sungrow/signed_battery_power"))
        client.publish("/battery/power", 0)
    else:
        client.publish("/bidi/power", 0)
        client.publish("/battery/power", mqttVal("sungrow/signed_battery_power"))

def on_message(client, userdata, msg):
    global mqttData

    if msg.topic == config['meter']['topic']:
        try:
            data = json.loads(msg.payload)
            ptotal = data['ptotal']
            client.publish("/meter/power", ptotal)
            client.publish("/meter/energy", data['etotal'])
            ptotal = (mqttVal('ptotal') + ptotal) / 2
            regulate(ptotal)
        except ValueError:
            return
    elif msg.topic == 'pyPlc/soc':
        soc = float(msg.payload)
        mqttData[msg.topic] = soc
        if soc >= mqttVal('pyPlc/soclimit', 85):
            mqttData['evfull'] = True
        elif soc < (mqttVal('pyPlc/soclimit', 85) - 3):
            mqttData['evfull'] = False
    else:
        val = msg.payload.decode("utf-8")
        if bool(re.match(r'^-?\d+[\.,]*\d*$', val)):
            val = float(val)
        mqttData[msg.topic] = val

def mqttVal(key, default = 0):
    global mqttData
    
    if key in mqttData:
        return mqttData[key]
    return default

with open("config.json") as configFile:
	config = json.load(configFile)
	
client = mqtt.Client(client_id = "netZeroController2")
client.on_message = on_message
client.connect(config['broker']['address'], 1883, 60)
client.subscribe(config['meter']['topic'])
client.subscribe("/charger/info/maxpower")
client.subscribe("/charger/info/power")
client.subscribe("/inverter/info/power")
client.subscribe("/inverter/info/maxpower")
client.subscribe("/bms/info/utotal")
client.subscribe("/bms/info/chargepower")
client.subscribe("/bms/info/dischargepower")
client.subscribe("pyPlc/soclimit")
client.subscribe("pyPlc/soc")
client.subscribe("pyPlc/charger_voltage")
client.subscribe("pyPlc/target_current")
client.subscribe("pyPlc/fsm_state")
client.subscribe("/grid/chargethresh")
client.subscribe("/grid/evchargethresh")
client.subscribe("/grid/dischargethresh")
client.subscribe("/grid/chargepower")
client.subscribe("/spotmarket/pricenow")
client.subscribe("sungrow/system_state")
client.subscribe("sungrow/total_active_power")
client.subscribe("sungrow/signed_battery_power")

client.publish("/charger/setpoint/voltage", config['netzero']['chargevoltage'])

mqttData = {}
v2gController = PiController(config['netzero']['powerkp'], config['netzero']['powerki'], -config['netzero']['evpower'], config['netzero']['evpower'])

client.loop_forever()

