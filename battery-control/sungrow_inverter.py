#!/usr/bin/python3

from pymodbus.client.sync import ModbusTcpClient
import paho.mqtt.client as mqtt
import sys, time, yaml, json, logging, signal

def on_message(client, modbusclient, msg):
    global ccsState, powerRequest, simulatedInletVoltage
    
    if msg.topic == "/bidi/setpoint/power":
        if ccsState == "CurrentDemand":
            powerRequest = int(msg.payload);
        else:
            powerRequest = 0
    elif msg.topic == "pyPlc/fsm_state":
        ccsState = msg.payload.decode("utf-8")
        #if we leave CurrentDemand immediately shut down inverter
        if ccsState != "CurrentDemand":
            powerRequest = 0

        if "CableCheck" in ccsState:
            simulatedInletVoltage = 0
        if "PreCharging" in ccsState:
            client.publish("pyPlc/inlet_voltage", simulatedInletVoltage)
            simulatedInletVoltage = simulatedInletVoltage + 15

def decodeRegisters(mqttClient, registers, description):
    global localStore
    
    for i in range(0, len(description)):
        if "type" in description[i]:
            topic = "sungrow/" + description[i]['name']
            dataType = description[i]['type']
            scaling = 1
            value = registers[i]
            
            if 'scaling' in description[i]:
                 scaling = description[i]['scaling']
            
            if dataType == "S16":
                if value > 32767:
                    value = value - 65536
            elif dataType == "U32":
                value = value + (registers[i + 1] << 16)
            elif dataType == "S32":
                value = value + (registers[i + 1] << 16)
                if value > 2147483647:
                    value = value - 4294967296
            value = value * scaling
            
            if "enum" in description[i]:
                if hex(value) in description[i]["enum"]:
                    value = description[i]["enum"][hex(value)]
                
            mqttClient.publish(topic, value)
            localStore[description[i]['name']] = value

def readAllRegisters(modbusClient, mqttClient, regs, regType):
    regs = regs[regType]
    
    for reg in regs:
        try:
            if regType == "input":
                result = modbusClient.read_input_registers(reg['start'] - 1, count = reg['count'], unit=1)
            elif regType == "holding":
                result = modbusClient.read_holding_registers(reg['start'] - 1, count = reg['count'], unit=1)
        except Exception as err:
            print(f"{str(err)}')")
            
        if result.isError():
            print(f"Connection failed {reg['start']}:{reg['count']} {result}")
            return
        elif not hasattr(result, 'registers'):
            print("No registers returned")
        elif len(result.registers) != reg['count']:
            print("Count mismatch")
        else:
            decodeRegisters(mqttClient, result.registers, reg['items'])

def writePowerRegister(modbusClient, baseReg, power):
    direction = 0xCC;
    
    if power > 0:
        direction = 0xAA
    elif power < 0:
        direction = 0xBB
    modbusclient.write_registers(baseReg - 1, [direction, abs(power)])
    
def sendToPyplc(mqttClient):
    global localStore, ccsState
    
    if "battery_current" in localStore and "bus_voltage" in localStore and "battery_power" in localStore:
        current = localStore['battery_current']
        voltage = localStore['bus_voltage']
        power = localStore['battery_power']
        batCurrent = current
        
        if voltage < 400 and voltage > 50:
            batVoltage = voltage
        elif current != 0:
            batVoltage = power / current
        else:
            batVoltage = 340
        
        #in precharging we simulate rising voltage for now in the mqtt handler
        if not "PreCharging" in ccsState:
            mqttClient.publish("pyPlc/inlet_voltage", batVoltage)
        mqttClient.publish('pyPlc/target_current', current)

def signal_handler(sig, frame):
    print('You pressed Ctrl+C!')
    modbusclient.close()
    sys.exit(0)
    
with open("config.json") as configFile:
    config = json.load(configFile)

client_config = {
    "host":     config['sungrow']['host'],
    "port":     config['sungrow']['port'],
    "timeout":  0.1,
    "retries":  3,
    "RetryOnEmpty": False,
}    

logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(message)s',
    level=logging.ERROR,
    datefmt='%Y-%m-%d %H:%M:%S')
log = logging.getLogger()
signal.signal(signal.SIGINT, signal_handler)

modbusclient = ModbusTcpClient(**client_config)
modbusclient.connect()
mqttclient = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, "sungrow", userdata=modbusclient)
mqttclient.on_message = on_message
mqttclient.connect(config['broker']['address'], 1883, 60)
mqttclient.subscribe("/bidi/setpoint/power")
mqttclient.subscribe("pyPlc/fsm_state")
ccsState = ""
simulatedInletVoltage = 0
mqttclient.loop_start()
powerRequest = 0
localStore = {}
ccsState = ""
# Send this once for initializing the inverter for the first time
#modbusclient.write_register(13083, 7) #Set Start Charging Power to 70 W, the lowest possible
#modbusclient.write_register(13084, 7) #Set Start Discharging Power to 70 W, the lowest possible
#modbusclient.write_register(13049, 2) #Set battery control mode to manual
#modbusclient.write_register(5005, 0xCF) #Start operation

while True:
    if not modbusclient.is_socket_open():
        modbusclient.connect()
    time.sleep(config['sungrow']['scan_interval'])
    writePowerRegister(modbusclient, config['sungrow']['registers']['power'], powerRequest)
    readAllRegisters(modbusclient, mqttclient, config['sungrow']['registers'], 'input')
    readAllRegisters(modbusclient, mqttclient, config['sungrow']['registers'], 'holding')
    sendToPyplc(mqttclient)

