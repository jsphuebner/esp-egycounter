# Tibber Pulse data sender
The goal of this sub module is to make the Tibber Pulse IR hardware redundant. Tibber's hardware has some drawbacks:

- The Pulse IR is battery operated
- The Pulse IR is hard to install correctly to have uninterrupted data flow
- An additional Wifi bridge is needed

Since this project deploys an IR pickup head on your meter anyway and it also deploys a network attached Linux computer we actually have all the hardware installed to give Tibber what it wants: high resolution records of your energy consumption.

I have only tested the procedure with my eBZ meter which uses what I think is called the OBIS data format (text based)

# Extracting communication parameters
Despite us making the Pulse hardware redundant you still have to buy the hardware from them in order to obtain access to their servers.
There are a number of items that we need to extract from the Tibber bridge to be able to communicate with their server.

They use secure MQTT, so right off the bat we need 5 items:

- The MQTT server address
- The MQTT topic that we publish data to
- The CA certificate
- A public key
- A private key

See here: https://blog.wyraz.de/allgemein/a-brief-analysis-of-the-tibber-pulse-bridge/

Fortunately those items aren't hard to obtain. When you first plug in your bridge it opens an access point that you can access with any phone or PC. So once connected you browse the address http://10.133.70.1. You will be asked for user name and password. User name is admin, password is printed on the device. Then you will see the web interface. Then click on "PARAMS".
Now set "webserver_force_enable" to true. Then do the actual installation procedure through the Tibber app.

Now the bridge will be connected to your local router and you can access it via its assigned IP address as before. Click on "PARAMS" again

You will find the items mentioned above. Save them:

- ca_cert to ca.pem
- certificate to cert.pem
- private_key to private.pem
- mqtt_host to config.json (see below)
- the 32 digit id you find in mqtt_topic to config.json also

Now we need two more items:

- the ID of the tibber bridge
- the ID of the Pulse IR (eui)

Go to the "CONSOLE" tab and type "version". You will get some items, on of them is the 13 digit id of the bridge. Then go to the "NODES" tab, here you will find the eui of your Pulse IR.

With all that information collected the config section looks like this

```
{
  "tibber": {
    "broker": "a2zhmn2392zl2a.iot.eu-west-1.amazonaws.com",
    "uid": "209ad2f026855a9d895580f78d3519d6",
    "bridgeid": "1596765f34000",
    "eui": "ef8e95123eb82afe"
  },
  "meter": { "rawtopic": "/ebz/raw" }
}
```

You will also see there is a topic for the raw data read from your meters IR port.
Now also look through the 3 json files in the tibber/ directory. You will find things like IP addresses and "bssid" of your wifi. It may be required to make them reflect your local network. I found part of them on the overview page of the bridge.

# Testing
First I recommend running Tibber with the actual Pulse for a while so that you at least see its icon in the Tibber app. Maybe you even get it to display some meter data. With that sorted we check if our tibber sender yield the same result. Just start it by typing "./tibbersender.py". Also make sure that you get valid raw data on your meter topic.
Now you should see your power consumption in the tibber app. If you have negative consumption, e.g. because of solar, the Tibber app won't update.

With that sorted you can remove the batteries from your Pulse IR, put everything back in its box and store it for later use. Congratulations :)

# Technical Info
You don't need to read this if you just want to use it.
All communication to Tibber is done via MQTT under the topic tree

```$aws/rules/ingest_tibber_bridge_data/tibber-bridge/<uid>/publish/```

So underneath above topic we have

```TFD01/<eui>/metric``` various info about the Tibber IR reader on your meter - sent every 300 seconds

```TFD01/<eui>/obis_stream``` The actual meter data in ASCII OBIS format - send every 2 seconds (every 10s might be sufficient)

```TFD01/<eui>/SML``` Alternatively meter data in binary SML format (see issue #2) - same frequency as above

Then for the bridge we have

```TJH01/<bridge_id>/event``` A hello message read from TJH01_event.json - sent once at startup

```TJH01/<bridge_id>/metric``` various info about the Tibber Wifi bridge - sent every 120 seconds

The tibbersend.py scripts modifies the metrics to be somewhat plausible, like increasing uptime and some random variation in measured values such as temperature.
