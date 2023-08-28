#!/usr/bin/python3

import paho.mqtt.client as mqtt
import json, random
from datetime import datetime

def tibber_to_pulse_message(client, userdata, msg):
    global localclient

    localclient.publish(msg.topic, msg.payload)
    print("Forwarding '%s' to '%s'" % (msg.payload, msg.topic))
    
def onMeterData(localclient, userdata, msg):
    global meterDataRaw
    meterDataRaw = msg.payload.decode().replace('\r\n\r\n', '\r\n').encode()

def tibber_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to Tibber MQTT Broker!")
    else:
        print("Failed to connect, return code %d\n", rc)
        
def SendTjhMetric(client, tjhMetric, unix_timestamp, pubCnt):
    global config
    global mqttBaseTopic
    global startTime

    tjhMetric['ts'] = unix_timestamp
    tjhMetric['device_id'] = config['tibber']['bridgeid']
    tjhMetric['status']['nodes'][0]['eui'] = config['tibber']['eui']
    #I don't know how much tibber care about these but lets make em plausible and add some noise
    tjhMetric['status']['uptime'] = unix_timestamp - startTime + 7
    tjhMetric['status']['efr_uptime'] = unix_timestamp - startTime
    tjhMetric['status']['vacrms'] = 225 + random.randint(0, 300) / 100
    tjhMetric['status']['heap'] = 124808 + random.randint(-1000, 1000)
    tjhMetric['status']['pubcnt'] = pubCnt
    jstr = json.dumps(tjhMetric)
    topic = mqttBaseTopic + "/TJH01/" + config['tibber']['bridgeid'] + "/metric"
    client.publish(topic, jstr)
    print("Sent TJH01 metric to " + topic)

def SendTfdMetric(client, tfdMetric, unix_timestamp):
    global config
    global mqttBaseTopic
    global startTime
    
    tfdMetric['node_status']['node_temperature'] = 28 + random.randint(0, 100) / 100
    tfdMetric['node_status']['node_uptime_ms'] = ((unix_timestamp - startTime) * 1000) % 4294967296
    tfdMetric['node_status']['time_in_em0_ms'] = tfdMetric['node_status']['time_in_em0_ms'] + 15
    tfdMetric['node_status']['time_in_em1_ms'] = tfdMetric['node_status']['time_in_em1_ms'] + 1
    tfdMetric['node_status']['time_in_em2_ms'] = tfdMetric['node_status']['time_in_em2_ms'] + 9000
    jstr = json.dumps(tfdMetric)
    topic = mqttBaseTopic + "/TFD01/" + config['tibber']['eui'] + "/metric"
    client.publish(topic, jstr)
    print("Sent TFD01 metric to " + topic)
               
with open("tibber/TFD01_metric.json") as jsonFile:
	tfdMetric = json.load(jsonFile)

with open("tibber/TJH01_metric.json") as jsonFile:
	tjhMetric = json.load(jsonFile)

with open("tibber/TJH01_event.json") as jsonFile:
	tjhEvent = jsonFile.read()
	
with open("config.json") as configFile:
	config = json.load(configFile)
	
client = mqtt.Client(config['tibber']['bridgeid'])
client.on_message = tibber_to_pulse_message
client.on_connect = tibber_connect
client.tls_set("tibber/ca.pem", "tibber/cert.pem", "tibber/private.pem")
client.connect(config['tibber']['broker'], 8883)

localclient = mqtt.Client("tibberSender")
localclient.on_message = onMeterData
localclient.connect(config['broker']['address'], 1883, 60)
localclient.subscribe(config['meter']['rawtopic'])
unix_timestamp = (datetime.now() - datetime(1970, 1, 1)).total_seconds()
lastTjhMetricTs = unix_timestamp
lastTfdMetricTs = unix_timestamp - 60
startTime = unix_timestamp
lastObisTs = unix_timestamp
pubCnt = 0
meterDataRaw = False
mqttBaseTopic = "$aws/rules/ingest_tibber_bridge_data/tibber-bridge/" + config['tibber']['uid'] + "/publish"
streamTopic = mqttBaseTopic + "/TFD01/" + config['tibber']['eui'] + "/obis_stream"
client.publish(mqttBaseTopic + "/TJH01/" + config['tibber']['bridgeid'] + "/event", tjhEvent)

while True:
    unix_timestamp = (datetime.now() - datetime(1970, 1, 1)).total_seconds()
    
    if unix_timestamp >= (lastTjhMetricTs + 120):
        lastTjhMetricTs = unix_timestamp
        SendTjhMetric(client, tjhMetric, unix_timestamp, pubCnt)

    if unix_timestamp >= (lastTfdMetricTs + 300):
        lastTfdMetricTs = unix_timestamp
        SendTfdMetric(client, tfdMetric, unix_timestamp)
        
    if meterDataRaw and unix_timestamp >= (lastObisTs + 2):            
        res = client.publish(streamTopic, meterDataRaw)
        lastObisTs = unix_timestamp
        pubCnt = pubCnt + 1
            
        if res.rc != mqtt.MQTT_ERR_SUCCESS:
            print("Publish error %d, reconnecting\n" % res.rc)
            client.reconnect()
    
    client.loop(timeout=0.1)
    localclient.loop(timeout=0.1)

