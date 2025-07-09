#!/usr/bin/python3

import time, sys, json, re, math
from datetime import datetime
import paho.mqtt.client as mqtt
from picontroller import PiController

def calculateNetzero(ptotal):
    global config, v2gController, batController
    
    v2gSpnt = v2gController.run(ptotal, 0)
    batSpnt = batController.run(ptotal, 0)
    return (batSpnt, v2gSpnt)

def setControllerLimits():
    global config, v2gController, batController
    
    price = mqttVal("/spotmarket/pricenow")
    if price > mqttVal('/grid/dischargethresh'):
        batDisLimit = 1
    else:
        batDisLimit = 0
        
    if mqttVal('evfull'):
        chargeLimit = 0
    else:
        chargeLimit = mqttVal('pyPlc/target_current') * mqttVal('pyPlc/charger_voltage')
        chargeLimit = min(chargeLimit, config['netzero']['evpower'])
        
    if mqttVal("/charger/info/power") > 50:
        disLimit = 0
    else:
        disLimit = config['netzero']['evpower'] * batDisLimit
        
    v2gController.setMinMax(-chargeLimit, disLimit)
    
    stationaryChargeLimit = -min(mqttVal('/bms/info/chargepower'), mqttVal("/charger/info/maxpower"))
    stationaryDisLimit = min(mqttVal('/bms/info/dischargepower') * batDisLimit, mqttVal("/inverter/info/maxpower"))
    
    if mqttVal('sungrow/system_state') == "Forced Run":
        if mqttVal('evfull') and mqttVal("sungrow/total_active_power") > 0:
            batController.setMinMax(stationaryChargeLimit, 0)
        else:
            batController.setMinMax(0, 0)
    else:
        batController.setMinMax(stationaryChargeLimit, stationaryDisLimit)

def calculateSpotmarket(batSpnt, v2gSpnt):
    global config, v2gController, batController

    price = mqttVal("/spotmarket/pricenow")
    
    if mqttVal('sungrow/system_state') == "Forced Run" and not mqttVal('evfull'):
        #if price > mqttVal('/grid/dischargethresh'):
        #    batSpnt = min(mqttVal('/bms/info/dischargepower'), mqttVal("/inverter/info/maxpower"))
        if price < mqttVal("/grid/evchargethresh"):
            v2gSpnt = mqttVal('pyPlc/target_current') * mqttVal('pyPlc/charger_voltage')
            v2gSpnt = -min(v2gSpnt, config['netzero']['evpower'])
            v2gController.resetIntegrator()
    
    if price < mqttVal('/grid/chargethresh') and mqttVal('/grid/chargepower') > -batSpnt:
        batSpnt = -mqttVal('/grid/chargepower')
        batController.resetIntegrator()
            
    return (batSpnt, v2gSpnt)

def sendChargeDischargeCommand(batSpnt, v2gSpnt):
    client.publish("/bidi/setpoint/power", -v2gSpnt)

    if batSpnt < 0: #charge stationary battery
        client.publish("/charger/setpoint/power", -batSpnt)
        client.publish("/battery/power", mqttVal("/charger/info/power"))
        client.publish("/inverter/setpoint/power", 0)
    else: #discharge stationary battery
        client.publish("/charger/setpoint/power", 0)
        client.publish("/inverter/setpoint/power", batSpnt)
        client.publish("/battery/power", -mqttVal("/inverter/info/power"))

def on_message(client, userdata, msg):
    global mqttData

    if msg.topic == config['meter']['topic']:
        try:
            data = json.loads(msg.payload)
            ptotal = data['ptotal']
            client.publish("/meter/power", ptotal)
            client.publish("/meter/energy", data['etotal'])
            ptotal = (mqttVal('ptotal') + ptotal) / 2
            mqttData['ptotal'] = ptotal
            setControllerLimits()
            (batSpnt, v2gSpnt) = calculateNetzero(ptotal)
            (batSpnt, v2gSpnt) = calculateSpotmarket(batSpnt, v2gSpnt)
            sendChargeDischargeCommand(batSpnt, v2gSpnt)
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

client.publish("/charger/setpoint/voltage", config['netzero']['chargevoltage'])

mqttData = {}
controller = PiController(config['netzero']['powerkp'], config['netzero']['powerki'])
batController = PiController(config['netzero']['powerkp'], config['netzero']['powerki'])
v2gController = PiController(config['netzero']['powerkp'], config['netzero']['powerki'], -config['netzero']['evpower'], config['netzero']['evpower'])

client.loop_forever()

