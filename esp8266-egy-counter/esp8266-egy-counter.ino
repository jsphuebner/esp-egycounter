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
#include "Adafruit_MQTT.h"
#include "Adafruit_MQTT_Client.h"

#define DBG_OUTPUT_PORT Serial

struct CounterValues
{
  String id;
  float etotal;
  float ptotal;
  float pphase[3];
};

ESP8266WebServer server(80);
ESP8266HTTPUpdateServer updater;
//holds the current upload
File fsUploadFile;
Ticker sta_tick;
WiFiClient client;
Adafruit_MQTT_Client mqtt(&client, "192.168.178.37", 1883);
Adafruit_MQTT_Publish ebz = Adafruit_MQTT_Publish(&mqtt, "/ebz/readings");
CounterValues values;

void GetCounterValues(CounterValues& v)
{
  Serial.readStringUntil('/');
  Serial.readStringUntil('\n');
  Serial.readStringUntil('\n');
  Serial.readStringUntil('(');
  v.id = Serial.readStringUntil(')');
  Serial.readStringUntil('\n');
  yield();
  Serial.readStringUntil('\n');
  Serial.readStringUntil('(');
  v.etotal = Serial.parseFloat();
  Serial.readStringUntil('\n');
  yield();
  Serial.readStringUntil('(');
  v.ptotal = Serial.parseFloat();
  Serial.readStringUntil('\n');
  yield();
  Serial.readStringUntil('(');
  v.pphase[0] = Serial.parseFloat();
  Serial.readStringUntil('\n');
  yield();
  Serial.readStringUntil('(');
  v.pphase[1] = Serial.parseFloat();
  Serial.readStringUntil('\n');
  yield();
  Serial.readStringUntil('(');
  v.pphase[2] = Serial.parseFloat();
  yield();
  Serial.readStringUntil('!');
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
  String output, line;

  if(server.hasArg("cmd"))
  {
    if (server.arg("cmd") == "json")
    {
      output = "{ \"etotal\": {\"value\":" + String(values.etotal, 8) + ",\"isparam\":false,\"unit\":\"kWh\" },"
             + "\"ptotal\": {\"value\":" + String(values.ptotal) + ",\"isparam\":false,\"unit\":\"W\" },"
             + "\"pL1\": {\"value\":" + String(values.pphase[0]) + ",\"isparam\":false,\"unit\":\"W\" },"
             + "\"pL2\": {\"value\":" + String(values.pphase[1]) + ",\"isparam\":false,\"unit\":\"W\" },"
             + "\"pL3\": {\"value\":" + String(values.pphase[2]) + ",\"isparam\":false,\"unit\":\"W\" }}";
    }
    else if (server.arg("cmd") == "get ptotal")
    {
      output = String(values.ptotal);
    }
    else if (server.arg("cmd") == "get pL1,pL2,pL3")
    {
      output = String(values.pphase[0]) + "," + String(values.pphase[1]) + "," + String(values.pphase[2]);
    }
  }
  else
  {
    Serial.readStringUntil('/');
    output = Serial.readStringUntil('!');
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
  Serial.begin(9600, SERIAL_7E1);
  Serial.setTimeout(300);
  SPIFFS.begin();

  //WIFI INIT
  #ifdef WIFI_IS_OFF_AT_BOOT
    enableWiFiAtBootTime();
  #endif  WiFi.mode(WIFI_AP_STA);
  WiFi.begin();
  WiFi.setAutoReconnect(true);
  WiFi.persistent(true);
  sta_tick.attach(10, staCheck);
  
  MDNS.begin("ebzclient");

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
  int8_t ret;

  // Stop if already connected.
  if (mqtt.connected()) {
    return;
  }

  uint8_t retries = 3;
  while ((ret = mqtt.connect()) != 0) { // connect will return 0 for connected
       mqtt.disconnect();
       delay(1000);  // wait 5 seconds
       retries--;
       if (retries == 0) {
         // basically die and wait for WDT to reset me
         return;
       }
  }
}
 
void loop(void){
  ArduinoOTA.handle();

  String output;
  yield();
  GetCounterValues(values);
  ValuesJson(output);

  server.handleClient();

  MQTT_connect();
  char buffer[256];
  output.toCharArray(buffer, sizeof(buffer));
  ebz.publish(buffer);
}
