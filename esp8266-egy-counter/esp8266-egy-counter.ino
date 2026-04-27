/* 
  FSWebServer - Example WebServer with SPIFFS backend for esp8266
  Copyright (c) 2015 Hristo Gochkov. All rights reserved.
  This file is part of the ESP8266WebServer library for Arduino environment.
 
  This library is free software; you can redistribute it and/or
  modify it under the terms of the GNU Lesser General Public
  License as published by the Free Software Foundation; either
  version 2.1 of the License, or (at your option) any later version.
  This library is distributed in the hope that it will be useful,
  but WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
  Lesser General Public License for more details.
  You should have received a copy of the GNU Lesser General Public
  License along with this library; if not, write to the Free Software
  Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
  
  upload the contents of the data folder with MkSPIFFS Tool ("ESP8266 Sketch Data Upload" in Tools menu in Arduino IDE)
  or you can upload the contents of a folder if you CD in that folder and run the following command:
  for file in `ls -A1`; do curl -F "file=@$PWD/$file" esp8266fs.local/edit; done
  
  access the sample web page at http://esp8266fs.local
  edit the page by going to http://esp8266fs.local/edit
*/
/*
 * This file is part of the esp8266 web interface
 *
 * Copyright (C) 2018 Johannes Huebner <dev@johanneshuebner.com>
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 *
 */
#include <ESP8266WiFi.h>
#include <WiFiClient.h>
#include <ESP8266WebServer.h>
#include <ESP8266HTTPUpdateServer.h>
#include <ESP8266mDNS.h>
#include <ArduinoOTA.h>
#include <FS.h>
#include <Ticker.h>
#include <PubSubClient.h>
#include "sml_decoder.h"
#include "obis_decoder.h"

#define DBG_OUTPUT_PORT Serial
/* Minimum milliseconds between reconnection attempts */
#define MQTT_RECONNECT_INTERVAL_MS 5000UL
#define CONFIG_FILE      "/config.json"

/* ---- Decoder mode -------------------------------------------------------- */
#define DECODER_SML  0
#define DECODER_OBIS 1

/* ---- Serial baud-rate table (index matches serialBaud config value) ------ */
static const long BAUD_RATES[]    = { 1200, 2400, 4800, 9600, 19200, 38400, 57600 };
static const int  BAUD_RATE_COUNT = 7;

/* ---- Serial frame-format table (index matches serialConfig value) -------- */
static const SerialConfig SERIAL_CONFIGS[] = {
  SERIAL_8N1, SERIAL_7E1, SERIAL_8E1, SERIAL_8N2
};
static const int SERIAL_CONFIG_COUNT = 4;

/* ---- Runtime configuration ---------------------------------------------- */
struct Config {
  int  decoder;            /* DECODER_SML or DECODER_OBIS                   */
  char mqttHost[64];       /* MQTT broker hostname or IP                     */
  int  mqttPort;           /* MQTT broker port                               */
  char mqttUser[32];       /* MQTT username (empty = no auth)                */
  char mqttPass[32];       /* MQTT password (empty = no auth)                */
  char mqttClientId[32];   /* MQTT client identifier                         */
  char mqttTopicJson[64];  /* MQTT topic for JSON readings                   */
  char mqttTopicRaw[64];   /* MQTT topic for raw binary payload              */
  int  serialBaud;         /* index into BAUD_RATES[]  (default 3 = 9600)   */
  int  serialConfig;       /* index into SERIAL_CONFIGS[] (default 0 = 8N1) */
};

static Config config = {
  DECODER_SML,
  "192.168.188.23",
  1883,
  "",
  "",
  "ebzclient",
  "/ebz/readings",
  "/ebz/raw",
  3,  /* 9600 baud */
  0   /* 8N1 */
};

ESP8266WebServer server(80);
ESP8266HTTPUpdateServer updater;
//holds the current upload
File fsUploadFile;
Ticker sta_tick;
WiFiClient wifiClient;
PubSubClient mqtt(wifiClient);
CounterValues values;
static unsigned long lastMqttAttempt = 0;

/* ======================================================================== */
/*  Config helpers                                                           */
/* ======================================================================== */

/* Minimal JSON integer extractor – finds "key": <integer> */
static int parseJsonInt(const String& json, const char* key, int defaultVal)
{
  String search = "\"";
  search += key;
  search += "\":";
  int idx = json.indexOf(search);
  if (idx < 0) return defaultVal;
  idx += search.length();
  while (idx < (int)json.length() && json[idx] == ' ') idx++;
  return json.substring(idx).toInt();
}

/* Minimal JSON string extractor – finds "key": "value" */
static void parseJsonString(const String& json, const char* key,
                            char* dest, size_t destLen, const char* defaultVal)
{
  String search = "\"";
  search += key;
  search += "\":\"";
  int idx = json.indexOf(search);
  if (idx < 0) {
    strncpy(dest, defaultVal, destLen - 1);
    dest[destLen - 1] = '\0';
    return;
  }
  idx += search.length();
  int end = json.indexOf('"', idx);
  if (end < 0) end = json.length();
  String val = json.substring(idx, end);
  val.toCharArray(dest, destLen);
}

static void loadConfig()
{
  if (!SPIFFS.exists(CONFIG_FILE)) return;
  File f = SPIFFS.open(CONFIG_FILE, "r");
  if (!f) return;
  String json = f.readString();
  f.close();

  config.decoder      = parseJsonInt(json, "decoder",      DECODER_SML);
  config.mqttPort     = parseJsonInt(json, "mqttPort",     1883);
  config.serialBaud   = parseJsonInt(json, "serialBaud",   3);
  config.serialConfig = parseJsonInt(json, "serialConfig", 0);

  parseJsonString(json, "mqttHost",      config.mqttHost,      sizeof(config.mqttHost),      "192.168.188.23");
  parseJsonString(json, "mqttUser",      config.mqttUser,      sizeof(config.mqttUser),      "");
  parseJsonString(json, "mqttPass",      config.mqttPass,      sizeof(config.mqttPass),      "");
  parseJsonString(json, "mqttClientId",  config.mqttClientId,  sizeof(config.mqttClientId),  "ebzclient");
  parseJsonString(json, "mqttTopicJson", config.mqttTopicJson, sizeof(config.mqttTopicJson), "/ebz/readings");
  parseJsonString(json, "mqttTopicRaw",  config.mqttTopicRaw,  sizeof(config.mqttTopicRaw),  "/ebz/raw");

  /* Clamp indices to valid range */
  if (config.serialBaud   < 0 || config.serialBaud   >= BAUD_RATE_COUNT)    config.serialBaud   = 3;
  if (config.serialConfig < 0 || config.serialConfig >= SERIAL_CONFIG_COUNT) config.serialConfig = 0;
}

static void saveConfig()
{
  File f = SPIFFS.open(CONFIG_FILE, "w");
  if (!f) return;
  f.print("{\n");
  f.print("  \"decoder\": ");        f.print(config.decoder);        f.print(",\n");
  f.print("  \"mqttHost\": \"");     f.print(config.mqttHost);       f.print("\",\n");
  f.print("  \"mqttPort\": ");       f.print(config.mqttPort);       f.print(",\n");
  f.print("  \"mqttUser\": \"");     f.print(config.mqttUser);       f.print("\",\n");
  f.print("  \"mqttPass\": \"");     f.print(config.mqttPass);       f.print("\",\n");
  f.print("  \"mqttClientId\": \""); f.print(config.mqttClientId);   f.print("\",\n");
  f.print("  \"mqttTopicJson\": \"");f.print(config.mqttTopicJson);  f.print("\",\n");
  f.print("  \"mqttTopicRaw\": \""); f.print(config.mqttTopicRaw);   f.print("\",\n");
  f.print("  \"serialBaud\": ");     f.print(config.serialBaud);     f.print(",\n");
  f.print("  \"serialConfig\": ");   f.print(config.serialConfig);   f.print("\n");
  f.print("}\n");
  f.close();
}

/* Ensure baud/config indices are in valid range before array access */
static void clampSerialConfig()
{
  if (config.serialBaud   < 0 || config.serialBaud   >= BAUD_RATE_COUNT)    config.serialBaud   = 3;
  if (config.serialConfig < 0 || config.serialConfig >= SERIAL_CONFIG_COUNT) config.serialConfig = 0;
}

/* Apply serial and MQTT settings from config (called after load or save) */
static void applySerialConfig()
{
  clampSerialConfig();
  Serial.flush();
  Serial.begin(BAUD_RATES[config.serialBaud], SERIAL_CONFIGS[config.serialConfig]);
  Serial.setTimeout(500);
}

static void applyMqttConfig()
{
  mqtt.disconnect();
  mqtt.setServer(config.mqttHost, (uint16_t)config.mqttPort);
  lastMqttAttempt = 0; /* trigger immediate reconnect attempt */
}

/* Handle "set <name> <value>" command */
static void handleSet(const String& name, const String& value)
{
  bool serialChanged = false;
  bool mqttChanged   = false;

  if (name == "decoder") {
    int v = value.toInt();
    if (v == DECODER_SML || v == DECODER_OBIS) config.decoder = v;
  } else if (name == "mqttHost") {
    value.toCharArray(config.mqttHost, sizeof(config.mqttHost));
    mqttChanged = true;
  } else if (name == "mqttPort") {
    int v = value.toInt();
    if (v > 0 && v <= 65535) { config.mqttPort = v; mqttChanged = true; }
  } else if (name == "mqttUser") {
    value.toCharArray(config.mqttUser, sizeof(config.mqttUser));
    mqttChanged = true;
  } else if (name == "mqttPass") {
    value.toCharArray(config.mqttPass, sizeof(config.mqttPass));
    mqttChanged = true;
  } else if (name == "mqttClientId") {
    value.toCharArray(config.mqttClientId, sizeof(config.mqttClientId));
    mqttChanged = true;
  } else if (name == "mqttTopicJson") {
    value.toCharArray(config.mqttTopicJson, sizeof(config.mqttTopicJson));
  } else if (name == "mqttTopicRaw") {
    value.toCharArray(config.mqttTopicRaw, sizeof(config.mqttTopicRaw));
  } else if (name == "serialBaud") {
    int v = value.toInt();
    if (v >= 0 && v < BAUD_RATE_COUNT) { config.serialBaud = v; serialChanged = true; }
  } else if (name == "serialConfig") {
    int v = value.toInt();
    if (v >= 0 && v < SERIAL_CONFIG_COUNT) { config.serialConfig = v; serialChanged = true; }
  }

  if (serialChanged) applySerialConfig();
  if (mqttChanged)   applyMqttConfig();
}

//format bytes
String formatBytes(size_t bytes){
  if (bytes < 1024){
    return String(bytes)+"B";
  } else if(bytes < (1024 * 1024)){
    return String(bytes/1024.0)+"KB";
  } else if(bytes < (1024 * 1024 * 1024)){
    return String(bytes/1024.0/1024.0)+"MB";
  } else {
    return String(bytes/1024.0/1024.0/1024.0)+"GB";
  }
}

String getContentType(String filename){
  if(server.hasArg("download")) return "application/octet-stream";
  else if(filename.endsWith(".htm")) return "text/html";
  else if(filename.endsWith(".html")) return "text/html";
  else if(filename.endsWith(".css")) return "text/css";
  else if(filename.endsWith(".js")) return "application/javascript";
  else if(filename.endsWith(".png")) return "image/png";
  else if(filename.endsWith(".gif")) return "image/gif";
  else if(filename.endsWith(".jpg")) return "image/jpeg";
  else if(filename.endsWith(".ico")) return "image/x-icon";
  else if(filename.endsWith(".xml")) return "text/xml";
  else if(filename.endsWith(".pdf")) return "application/x-pdf";
  else if(filename.endsWith(".zip")) return "application/x-zip";
  else if(filename.endsWith(".gz")) return "application/x-gzip";
  return "text/plain";
}

bool handleFileRead(String path){
  //DBG_OUTPUT_PORT.println("handleFileRead: " + path);
  if(path.endsWith("/")) path += "index.html";
  String contentType = getContentType(path);
  String pathWithGz = path + ".gz";
  if(SPIFFS.exists(pathWithGz) || SPIFFS.exists(path)){
    if(SPIFFS.exists(pathWithGz))
      path += ".gz";
    File file = SPIFFS.open(path, "r");
    size_t sent = server.streamFile(file, contentType);
    file.close();
    return true;
  }
  return false;
}

void handleFileUpload(){
  if(server.uri() != "/edit") return;
  HTTPUpload& upload = server.upload();
  if(upload.status == UPLOAD_FILE_START){
    String filename = upload.filename;
    if(!filename.startsWith("/")) filename = "/"+filename;
    //DBG_OUTPUT_PORT.print("handleFileUpload Name: "); DBG_OUTPUT_PORT.println(filename);
    fsUploadFile = SPIFFS.open(filename, "w");
    filename = String();
  } else if(upload.status == UPLOAD_FILE_WRITE){
    //DBG_OUTPUT_PORT.print("handleFileUpload Data: "); DBG_OUTPUT_PORT.println(upload.currentSize);
    if(fsUploadFile)
      fsUploadFile.write(upload.buf, upload.currentSize);
  } else if(upload.status == UPLOAD_FILE_END){
    if(fsUploadFile)
      fsUploadFile.close();
    //DBG_OUTPUT_PORT.print("handleFileUpload Size: "); DBG_OUTPUT_PORT.println(upload.totalSize);
  }
}

void handleFileDelete(){
  if(server.args() == 0) return server.send(500, "text/plain", "BAD ARGS");
  String path = server.arg(0);
  //DBG_OUTPUT_PORT.println("handleFileDelete: " + path);
  if(path == "/")
    return server.send(500, "text/plain", "BAD PATH");
  if(!SPIFFS.exists(path))
    return server.send(404, "text/plain", "FileNotFound");
  SPIFFS.remove(path);
  server.send(200, "text/plain", "");
  path = String();
}

void handleFileCreate(){
  if(server.args() == 0)
    return server.send(500, "text/plain", "BAD ARGS");
  String path = server.arg(0);
  DBG_OUTPUT_PORT.println("handleFileCreate: " + path);
  if(path == "/")
    return server.send(500, "text/plain", "BAD PATH");
  if(SPIFFS.exists(path))
    return server.send(500, "text/plain", "FILE EXISTS");
  File file = SPIFFS.open(path, "w");
  if(file)
    file.close();
  else
    return server.send(500, "text/plain", "CREATE FAILED");
  server.send(200, "text/plain", "");
  path = String();
}

void handleFileList() {
  String path = "/";
  if(server.hasArg("dir")) 
    String path = server.arg("dir");
  //DBG_OUTPUT_PORT.println("handleFileList: " + path);
  Dir dir = SPIFFS.openDir(path);
  path = String();

  String output = "[";
  while(dir.next()){
    File entry = dir.openFile("r");
    if (output != "[") output += ',';
    bool isDir = false;
    output += "{\"type\":\"";
    output += (isDir)?"dir":"file";
    output += "\",\"name\":\"";
    output += String(entry.name()).substring(1);
    output += "\"}";
    entry.close();
  }
  
  output += "]";
  server.send(200, "text/json", output);
}

static void handleCommand() {
  String output;

  if(server.hasArg("cmd"))
  {
    String cmd = server.arg("cmd");

    if (cmd == "json")
    {
      /* Spot values (isparam=false) */
      output = "{"
        "\"etotal\":{\"value\":" + String(values.etotal, 8) + ",\"isparam\":false,\"unit\":\"kWh\"},"
        "\"ptotal\":{\"value\":" + String(values.ptotal)    + ",\"isparam\":false,\"unit\":\"W\"},"
        "\"pL1\":{\"value\":"    + String(values.pphase[0]) + ",\"isparam\":false,\"unit\":\"W\"},"
        "\"pL2\":{\"value\":"    + String(values.pphase[1]) + ",\"isparam\":false,\"unit\":\"W\"},"
        "\"pL3\":{\"value\":"    + String(values.pphase[2]) + ",\"isparam\":false,\"unit\":\"W\"},"
        /* Configuration parameters (isparam=true) */
        "\"decoder\":{\"value\":"      + String(config.decoder)      + ",\"isparam\":true,\"unit\":\"0=SML,1=OBIS\",\"category\":\"Meter\",\"minimum\":0,\"maximum\":1,\"default\":0},"
        "\"mqttHost\":{\"value\":\""   + String(config.mqttHost)     + "\",\"isparam\":true,\"unit\":\"\",\"category\":\"MQTT\",\"type\":\"text\",\"default\":\"localhost\"},"
        "\"mqttPort\":{\"value\":"     + String(config.mqttPort)     + ",\"isparam\":true,\"unit\":\"\",\"category\":\"MQTT\",\"minimum\":1,\"maximum\":65535,\"default\":1883},"
        "\"mqttUser\":{\"value\":\""   + String(config.mqttUser)      + "\",\"isparam\":true,\"unit\":\"\",\"category\":\"MQTT\",\"type\":\"text\",\"default\":\"\"},"
        "\"mqttPass\":{\"value\":\""   + String(config.mqttPass)      + "\",\"isparam\":true,\"unit\":\"\",\"category\":\"MQTT\",\"type\":\"text\",\"default\":\"\"},"
        "\"mqttClientId\":{\"value\":\"" + String(config.mqttClientId)  + "\",\"isparam\":true,\"unit\":\"\",\"category\":\"MQTT\",\"type\":\"text\",\"default\":\"ebzclient\"},"
        "\"mqttTopicJson\":{\"value\":\"" + String(config.mqttTopicJson) + "\",\"isparam\":true,\"unit\":\"\",\"category\":\"MQTT\",\"type\":\"text\",\"default\":\"/ebz/readings\"},"
        "\"mqttTopicRaw\":{\"value\":\"" + String(config.mqttTopicRaw)  + "\",\"isparam\":true,\"unit\":\"\",\"category\":\"MQTT\",\"type\":\"text\",\"default\":\"/ebz/raw\"},"
        "\"serialBaud\":{\"value\":"   + String(config.serialBaud)   + ",\"isparam\":true,\"unit\":\"0=1200,1=2400,2=4800,3=9600,4=19200,5=38400,6=57600\",\"category\":\"Serial\",\"minimum\":0,\"maximum\":6,\"default\":3},"
        "\"serialConfig\":{\"value\":" + String(config.serialConfig) + ",\"isparam\":true,\"unit\":\"0=8N1,1=7E1,2=8E1,3=8N2\",\"category\":\"Serial\",\"minimum\":0,\"maximum\":3,\"default\":0}"
        "}";
    }
    else if (cmd == "get ptotal")
    {
      output = String(values.ptotal);
    }
    else if (cmd == "get pL1,pL2,pL3")
    {
      output = String(values.pphase[0]) + "," + String(values.pphase[1]) + "," + String(values.pphase[2]);
    }
    else if (cmd == "save")
    {
      saveConfig();
      output = "OK";
    }
    else if (cmd.startsWith("set "))
    {
      String rest = cmd.substring(4); /* "name value" */
      int sp = rest.indexOf(' ');
      if (sp > 0) {
        handleSet(rest.substring(0, sp), rest.substring(sp + 1));
        output = "OK";
      } else {
        output = "ERR: usage: set <param> <value>";
      }
    }
  }

  server.send(200, "text/json", output);
}

static void ValuesJson(String& output)
{
  output = "{\"id\":\"" + values.id
    + "\",\"etotal\":" + String(values.etotal, 8)
    + ",\"ptotal\":" + String(values.ptotal)
    + ",\"pphase\":[" + String(values.pphase[0]) + "," + String(values.pphase[1]) + "," + String(values.pphase[2]) + "]}";  
}

static void handleValues() {
  String output;

  ValuesJson(output);

  server.send(200, "text/json", output);
}

static void handleWifi()
{
  bool updated = true;
  if(server.hasArg("apSSID") && server.hasArg("apPW")) 
  {
    WiFi.softAP(server.arg("apSSID").c_str(), server.arg("apPW").c_str());
  }
  else if(server.hasArg("staSSID") && server.hasArg("staPW")) 
  {
    WiFi.mode(WIFI_AP_STA);
    WiFi.begin(server.arg("staSSID").c_str(), server.arg("staPW").c_str());
  }
  else
  {
    File file = SPIFFS.open("/wifi.html", "r");
    String html = file.readString();
    file.close();
    html.replace("%staSSID%", WiFi.SSID());
    html.replace("%apSSID%", WiFi.softAPSSID());
    html.replace("%staIP%", WiFi.localIP().toString());
    server.send(200, "text/html", html);
    updated = false;
  }

  if (updated)
  {
    File file = SPIFFS.open("/wifi-updated.html", "r");
    size_t sent = server.streamFile(file, getContentType("wifi-updated.html"));
    file.close();    
  }
}

void staCheck(){
  sta_tick.detach();
  if(!(uint32_t)WiFi.localIP()){
    WiFi.mode(WIFI_AP); //disable station mode
  }
}

void setup(void){
  SPIFFS.begin();
  loadConfig();

  clampSerialConfig(); /* guard against corrupted config before array access */
  Serial.begin(BAUD_RATES[config.serialBaud], SERIAL_CONFIGS[config.serialConfig]);
  Serial.setTimeout(500);

  //WIFI INIT
  #ifdef WIFI_IS_OFF_AT_BOOT
    enableWiFiAtBootTime();
  #endif  
  WiFi.mode(WIFI_AP_STA);
  WiFi.begin();
  WiFi.setAutoReconnect(true);
  WiFi.persistent(true);
  sta_tick.attach(10, staCheck);
  
  MDNS.begin("ebzclient");

  mqtt.setServer(config.mqttHost, (uint16_t)config.mqttPort);
  /* Increase buffer for the raw binary payload (up to 512 bytes + overhead) */
  mqtt.setBufferSize(640);

  updater.setup(&server);
  
  //SERVER INIT
  ArduinoOTA.begin();
  //list directory
  server.on("/list", HTTP_GET, handleFileList);
  //load editor
  server.on("/edit", HTTP_GET, [](){
    if(!handleFileRead("/edit.htm")) server.send(404, "text/plain", "FileNotFound");
  });
  //create file
  server.on("/edit", HTTP_PUT, handleFileCreate);
  //delete file
  server.on("/edit", HTTP_DELETE, handleFileDelete);
  //first callback is called after the request has ended with all parsed arguments
  //second callback handles file uploads at that location
  server.on("/edit", HTTP_POST, [](){ server.send(200, "text/plain", ""); }, handleFileUpload);

  server.on("/wifi", handleWifi);
  server.on("/cmd", handleCommand);
  server.on("/values", handleValues);
  server.on("/version", [](){ server.send(200, "text/plain", "EBZ reader 1.0.B"); });
  //called when the url is not defined here
  //use it to load content from SPIFFS
  server.onNotFound([](){
    if(!handleFileRead(server.uri()))
      server.send(404, "text/plain", "FileNotFound");
  });

  server.begin();
  server.client().setNoDelay(1);
}

void MQTT_connect() {
  if (mqtt.connected()) {
    return;
  }

  /* Only attempt reconnection after the back-off interval has elapsed so that
     a broker outage does not block or spam the network. */
  unsigned long now = millis();
  if (now - lastMqttAttempt < MQTT_RECONNECT_INTERVAL_MS) {
    return;
  }
  lastMqttAttempt = now;

  if (config.mqttUser[0] != '\0') {
    /* NOTE: credentials are stored and transmitted in plaintext – use a
       private, firewalled network for deployments that require authentication. */
    mqtt.connect(config.mqttClientId, config.mqttUser, config.mqttPass);
  } else {
    mqtt.connect(config.mqttClientId);
  }
  /* Result is ignored here; mqtt.connected() will reflect the outcome on
     the next call and the interval prevents hammering the broker. */
}
 
void loop(void){
  ArduinoOTA.handle();

  uint8_t data[512];
  yield();
  uint16_t len = Serial.readBytes(data, 512);

  if (len > 0) {
    bool decoded = (config.decoder == DECODER_OBIS)
                   ? decodeObis(data, len, values)
                   : decodeSml(data, len, values);

    if (decoded && mqtt.connected()) {
      mqtt.publish(config.mqttTopicRaw, data, len, false);
      String msg;
      ValuesJson(msg);
      mqtt.publish(config.mqttTopicJson, msg.c_str());
    }
  }

  server.handleClient();
  mqtt.loop();
  MQTT_connect();
}
