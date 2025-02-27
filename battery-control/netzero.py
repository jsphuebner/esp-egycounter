#!/usr/bin/python3

import time, sys, json, re
from datetime import datetime
import paho.mqtt.client as mqtt
from picontroller import PiController

def calculateNetzero(ptotal):
    global config, controller, mqttData
    
    if mqttData['sungrow/system_state'] == "Forced Run" and not mqttData['evfull']:
        chargeLimit = mqttData['pyPlc/target_current'] * mqttData['pyPlc/charger_voltage']
        chargeLimit = min(chargeLimit, config['netzero']['evpower'])
        controller.setMinMax(-chargeLimit, config['netzero']['evpower'])
    else:
        controller.setMinMax(-min(mqttData['/bms/info/chargepower'], mqttData["/charger/info/maxpower"]),
                             min(mqttData['/bms/info/dischargepower'], mqttData["/inverter/info/maxpower"]))
    
    spnt = controller.run(ptotal, 5)
    return spnt

def calculateSpotmarket(netZeroPower):
    global config, controller, mqttData

    price = mqttData["/spotmarket/pricenow"]
    
    if mqttData['pyPlc/soc'] >= mqttData['pyPlc/soclimit']:
        mqttData['evfull'] = True
    elif mqttData['pyPlc/soc'] < (mqttData['pyPlc/soclimit'] - 3):
        mqttData['evfull'] = False
    
    if mqttData['sungrow/system_state'] == "Forced Run" and not mqttData['evfull']:
        if mqttData['sungrow/system_state'] == "Forced Run" and price < mqttData["/grid/evchargethresh"]:
            netZeroPower = -config['netzero']['evpower']
            controller.resetIntegrator()
    elif price < mqttData['/grid/chargethresh']:
        netZeroPower = -mqttData['/grid/chargepower']
        controller.resetIntegrator()
    elif price < mqttData['/grid/dischargethresh'] and netZeroPower > 0:
        netZeroPower = 0
        controller.resetIntegrator()
        
    return netZeroPower

def sendChargeDischargeCommand(power):
    global config, controller, mqttData
    
    if mqttData['sungrow/system_state'] == "Forced Run" and not mqttData['evfull']:
        client.publish("/charger/setpoint/power", 0)
        client.publish("/inverter/setpoint/power", 0)
        client.publish("/battery/power", -power)
        client.publish("/bidi/setpoint/power", -power)
    elif power < 0: #charge stationary battery
        client.publish("/charger/setpoint/power", -power)
        client.publish("/battery/power", -power)
        client.publish("/inverter/setpoint/power", 0)
        client.publish("/bidi/setpoint/power", 0)
    else: #discharge stationary battery
        client.publish("/charger/setpoint/power", 0)
        client.publish("/inverter/setpoint/power", power)
        client.publish("/battery/power", -power)
        client.publish("/bidi/setpoint/power", 0)

def on_message(client, userdata, msg):
    global mqttData

    if msg.topic == config['meter']['topic']:
        try:
            data = json.loads(msg.payload)
            ptotal = data['ptotal']
            client.publish("/meter/power", ptotal)
            client.publish("/meter/energy", data['etotal'])
            ptotal = (mqttData['ptotal'] + ptotal) / 2
            mqttData['ptotal'] = ptotal
            power = calculateNetzero(ptotal)
            power = calculateSpotmarket(power)
            sendChargeDischargeCommand(power)
        except ValueError:
            return
    else:
        val = msg.payload.decode("utf-8")
        if bool(re.match(r'^-?\d+[\.,]*\d*$', val)):
            val = float(val)
        mqttData[msg.topic] = val

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

client.publish("/charger/setpoint/voltage", config['netzero']['chargevoltage'])

mqttData = {
   '/bms/info/chargepower': 0,
   '/bms/info/dischargepower': 0,
   '/grid/evchargethresh"': 0,
   '/grid/chargethresh': 0,
   '/grid/dischargethresh': 0,
   '/grid/chargepower': 0,
   '/grid/evchargethresh': 0,
   '/spotmarket/pricenow': 0,
   'ptotal': 0,
   'evfull': False,
   '/charger/info/maxpower': 0,
   '/inverter/info/maxpower': 0,
   'pyPlc/fsm_state': 'Off',
   'pyPlc/charger_voltage': 0,
   'pyPlc/target_current': 0,
   'pyPlc/soc': 0,
   'pyPlc/soclimit': 85,
   'sungrow/system_state': ''
}
controller = PiController(config['netzero']['powerkp'], config['netzero']['powerki'], -1000, 1000)

client.loop_forever()

