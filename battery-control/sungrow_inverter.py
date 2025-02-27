#!/usr/bin/python3

from pymodbus.client.sync import ModbusTcpClient
import paho.mqtt.client as mqtt
import sys, time, yaml, json, logging, signal

def on_message(client, userdata, msg):
    global ccsState, invState, simulatedInletVoltage, batCurrent, busVoltage, batVoltage, batPower
    
    if msg.topic == "/bidi/setpoint/power":
        direction = "Stop"
        power = float(msg.payload)
        if ccsState == "CurrentDemand":
            if power > 0:
                direction = "Charge"
            elif power < 0:
                direction = "Discharge"
        client.publish("sungrow/charge_discharge_command/set", direction)
        client.publish("sungrow/charge_discharge_power/set", abs(power))
    elif msg.topic == "pyPlc/fsm_state":
        ccsState = msg.payload.decode("utf-8")
        #if we leave CurrentDemand immediately shut down inverter
        if ccsState != "CurrentDemand":
            client.publish("sungrow/charge_discharge_command/set", "Stop")

        #if "CableCheck" in ccsState:
        #    simulatedInletVoltage = 0
        #if "PreCharging" in ccsState:
        #    client.publish("pyPlc/charger_voltage", simulatedInletVoltage)
        #    simulatedInletVoltage = simulatedInletVoltage + 15
    elif msg.topic == "sungrow/system_state":
        invState = msg.payload.decode("utf-8")
    elif msg.topic == "sungrow/battery_current":
        batCurrent = float(msg.payload)
        if abs(batCurrent) > 1:
            vtg = batPower / batCurrent
            if vtg > 330 and vtg < 390:
                batVoltage = vtg
        client.publish('pyPlc/charger_current', batCurrent)   
    elif msg.topic == "sungrow/bus_voltage":
        busVoltage = float(msg.payload)
        if invState == "Standby" and busVoltage > 330:
            batVoltage = busVoltage
        client.publish("pyPlc/charger_voltage", batVoltage)
    elif msg.topic == "sungrow/battery_power":
        batPower = float(msg.payload)
    elif msg.topic == "pyPlc/target_voltage":
        # In precharge state the car delivers battery voltage via CCS
        if "PreCharging" in ccsState:
            batVoltage = float(msg.payload)

with open("config.json") as configFile:
    config = json.load(configFile)

mqttclient = mqtt.Client(client_id = "sungrow")
mqttclient.on_message = on_message
mqttclient.connect(config['broker']['address'], 1883, 60)
mqttclient.subscribe("/bidi/setpoint/power")
mqttclient.subscribe("pyPlc/fsm_state")
mqttclient.subscribe("sungrow/battery_current")
mqttclient.subscribe("sungrow/bus_voltage")
mqttclient.subscribe("sungrow/battery_power")
mqttclient.subscribe("sungrow/system_state")
mqttclient.subscribe("pyPlc/target_voltage")
#mqttclient.loop_start()
ccsState = ""
invState = ""
simulatedInletVoltage = 0
ccsState = ""
batCurrent = 0
busVoltage = 0
batVoltage = 360
batPower = 0
# Send this once for initializing the inverter for the first time
#modbusclient.write_register(13083, 7) #Set Start Charging Power to 70 W, the lowest possible
#modbusclient.write_register(13084, 7) #Set Start Discharging Power to 70 W, the lowest possible
#modbusclient.write_register(13049, 2) #Set battery control mode to manual
#modbusclient.write_register(5005, 0xCF) #Start operation

mqttclient.loop_forever()

