#!/usr/bin/python3

import time, sys, json, re, math
from datetime import datetime
import paho.mqtt.client as mqtt
from picontroller import PiController

def calculateNetzero(ptotal):
    global config, controller
    
    if mqttVal('sungrow/system_state', '') == "Forced Run" and not mqttVal('evfull'):
        chargeLimit = mqttVal('pyPlc/target_current') * mqttVal('pyPlc/charger_voltage')
        chargeLimit = min(chargeLimit, config['netzero']['evpower'])
        controller.setMinMax(-chargeLimit, config['netzero']['evpower'])
    else:
        controller.setMinMax(-min(mqttVal('/bms/info/chargepower'), mqttVal("/charger/info/maxpower")),
                             min(mqttVal('/bms/info/dischargepower'), mqttVal("/inverter/info/maxpower")))
    
    spnt = controller.run(ptotal, 5)
    return spnt

def calculateSpotmarket(netZeroPower):
    global config, controller, mqttData

    price = mqttVal("/spotmarket/pricenow")
    
    if mqttVal('pyPlc/soc') >= mqttVal('pyPlc/soclimit', 85):
        mqttData['evfull'] = True
    elif mqttVal('pyPlc/soc') < (mqttVal('pyPlc/soclimit', 85) - 3):
        mqttData['evfull'] = False
    
    if mqttVal('sungrow/system_state') == "Forced Run" and not mqttVal('evfull'):
        if mqttVal('sungrow/system_state') == "Forced Run" and price < mqttVal("/grid/evchargethresh"):
            netZeroPower = -config['netzero']['evpower']
            controller.resetIntegrator()
        elif price < mqttVal('/grid/dischargethresh') and netZeroPower > 0:
            netZeroPower = 0
            controller.resetIntegrator()
    elif price < mqttVal('/grid/chargethresh'):
        netZeroPower = -mqttVal('/grid/chargepower')
        controller.resetIntegrator()
    elif price < mqttVal('/grid/dischargethresh') and netZeroPower > 0:
        netZeroPower = 0
        controller.resetIntegrator()
        
    return netZeroPower

def sendChargeDischargeCommand(power):
    global mqttData
    
    if mqttVal('sungrow/system_state') == "Forced Run" and not mqttVal('evfull'):
        client.publish("/charger/setpoint/power", 0)
        client.publish("/inverter/setpoint/power", 0)
        client.publish("/battery/power", math.copysign(mqttVal("sungrow/battery_power"), -power))
        client.publish("/bidi/setpoint/power", -power)
    elif power < 0: #charge stationary battery
        client.publish("/charger/setpoint/power", -power)
        client.publish("/battery/power", mqttVal("/charger/info/power"))
        client.publish("/inverter/setpoint/power", 0)
        client.publish("/bidi/setpoint/power", 0)
    else: #discharge stationary battery
        client.publish("/charger/setpoint/power", 0)
        client.publish("/inverter/setpoint/power", power)
        client.publish("/battery/power", -mqttVal("/inverter/info/power"))
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
client.subscribe("sungrow/battery_power")

client.publish("/charger/setpoint/voltage", config['netzero']['chargevoltage'])

mqttData = {
   'ptotal': 0
}
controller = PiController(config['netzero']['powerkp'], config['netzero']['powerki'], -1000, 1000)

client.loop_forever()

