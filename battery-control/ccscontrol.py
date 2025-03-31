import Adafruit_BBIO.GPIO as GPIO
import Adafruit_BBIO.PWM as PWM
import paho.mqtt.client as mqtt
import time, json

def on_message(client, userdata, msg):
    global socLimit, ccsState
    
    if msg.topic == "pyPlc/soclimit":
        socLimit = float(msg.payload)
    elif msg.topic == "pyPlc/fsm_state":
        ccsState = msg.payload.decode("utf-8")

GPIO.setup("P8_7", GPIO.IN)
GPIO.setup("P8_8", GPIO.OUT)
GPIO.setup("P9_23", GPIO.OUT)
PWM.start("P8_13", 95, 1000)

with open("config.json") as configFile:
    config = json.load(configFile)

mqttclient = mqtt.Client(client_id = "ccscontrol")
mqttclient.on_message = on_message
mqttclient.connect(config['broker']['address'], 1883, 60)
mqttclient.subscribe("pyPlc/fsm_state")
mqttclient.subscribe("pyPlc/soclimit")
socLimit = 0
mqttclient.loop_start()
time.sleep(0.1)
ccsState = "None"
switchOffTime = 0
lastSocLimit = socLimit
switchState = False

while True:
    if ccsState == "CurrentDemand":
        GPIO.output("P8_8", GPIO.HIGH)
        switchState = GPIO.input("P8_7")

        if switchOffTime == 1:
            lastSocLimit = socLimit
            mqttclient.publish("pyPlc/soclimit", 0)
        if switchOffTime == 5:
            mqttclient.publish("pyPlc/enabled", 0)
    else:
        level = GPIO.input("P8_8")
        #toggle LED, sampling switch state is only possible when LED is on
        if level:
            switchState = GPIO.input("P8_7")
            GPIO.output("P8_8", GPIO.LOW)            
        else:
            GPIO.output("P8_8", GPIO.HIGH)
            
        if switchState:
            mqttclient.publish("pyPlc/enabled", 1)
            if lastSocLimit != socLimit:
                mqttclient.publish("pyPlc/soclimit", lastSocLimit)
        else:
            mqttclient.publish("pyPlc/enabled", 0)

    if ccsState not in ["Waiting f AppHandShake", "Session established", "ContractAuthentication", "CableCheck", "PreCharging", "PowerDelivery"]:
        GPIO.output("P9_23", GPIO.LOW)
    else:
        GPIO.output("P9_23", GPIO.HIGH)
        
    if switchState:
        switchOffTime = 0
    else:
        switchOffTime = switchOffTime + 1
    
    time.sleep(1)
