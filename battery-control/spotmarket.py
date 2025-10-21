#!/usr/bin/python3

import time, json, requests
from datetime import datetime, date, timedelta
import paho.mqtt.client as mqtt

def getUnixTime():  
    return int(time.time()) # (datetime.now() - datetime(1970, 1, 1)).total_seconds()

def tibber_to_awattar(idx_and_item):
    i, x = idx_and_item
    return { 'start_timestamp': midnight + timedelta(minutes=i*15), 'end_timestamp': midnight + timedelta(minutes=(i+1)*15), 'marketprice': x['energy'] * 10 }
    
def updatePriceList():
    global priceListObtained
    global priceList
    global config

    if  config['spotmarket']['apitype'] == "tibber":
        payload = '{ "query": "{ viewer { homes { currentSubscription { status priceInfo (resolution: QUARTER_HOURLY) { today { energy } tomorrow { energy } } } } } }" }'
        headers = { "Content-Type": "application/json", "User-Agent": "REST", "Authorization": config['spotmarket']['apikey'] }
        r = requests.post('https://api.tibber.com/v1-beta/gql', headers=headers, data=payload)
        data = json.loads(r.text)
        data = data['data']['viewer']['homes'][0]['currentSubscription']['priceInfo']
        data = data['today'] + data['tomorrow']
        midnight=datetime.combine(date.today(), datetime.min.time())
        priceList['data'] = [ {
            'start_timestamp': int((midnight + timedelta(minutes=i*15)).timestamp() * 1000), 
            'end_timestamp': int((midnight + timedelta(minutes=(i+1)*15)).timestamp() * 1000), 
            'marketprice': x['energy'] * 1000} for i, x in enumerate(data)]
    else: #awattar
        req = requests.get(config['spotmarket']['priceuri'])
        priceList = json.loads(req.text)

    client.publish("/spotmarket/pricelist", json.dumps(priceList), retain=True)
    priceListObtained = getUnixTime()
    print('Obtained pricelist')
    
def getCurrentPrice():
    global priceList

    timeNow = getUnixTime() * 1000
    for item in priceList['data']:
        if item['end_timestamp'] > timeNow:
            return float(item['marketprice'])

with open("config.json") as configFile:
    config = json.load(configFile)
    
client = mqtt.Client(client_id = "spotmarket")
client.connect(config['broker']['address'], 1883, 60)

priceList = { "data": [] }
priceListObtained = 0

while True:
    if (getUnixTime() - priceListObtained) >= 3600:
        updatePriceList()
        client.publish("/spotmarket/pricenow", getCurrentPrice(), retain=True)

    client.publish("/spotmarket/pricenow", getCurrentPrice(), retain=True)
    client.loop(timeout=0.1)
    time.sleep(10)
