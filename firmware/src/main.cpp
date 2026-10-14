/*
 * ==============================================================================
 * 🏛️ Dalet-RoomAnalyzer — Firmware Multi-Nodo Sensor (PlatformIO)
 * ==============================================================================
 * Microcontrolador: LilyGO (ESP32) / ESP8266
 * Sensor: HDC1080 (I2C: SDA=21, SCL=22 en ESP32 estándar)
 *
 * ARQUITECTURA:
 * 1. Edge WebServer (:80): Dashboard HTML local y API REST /json.
 * 2. Cloud HTTP Client: Envío periódico a FIWARE IoT Agent (:7896).
 * ==============================================================================
 */

#include <Arduino.h>
#include <Wire.h>
#include <ClosedCube_HDC1080.h>
#include <ArduinoJson.h>

#if defined(ESP32)
  #include <WiFi.h>
  #include <WebServer.h>
  #include <HTTPClient.h>
#elif defined(ESP8266)
  #include <ESP8266WiFi.h>
  #include <ESP8266WebServer.h>
  #include <ESP8266HTTPClient.h>
  #define WebServer ESP8266WebServer
#endif

#include "config.h"

// Si no fueron definidos mediante PlatformIO build_flags, asignamos valores por defecto:
#ifndef NODE_ID
  #define NODE_ID "hdc1080_nw"
#endif

#ifndef CORNER_NAME
  #define CORNER_NAME "Esquina Noroeste (Ventana)"
#endif

#ifndef ROOM_NAME
  #define ROOM_NAME "Room:01"
#endif

// ==============================================================================
// 📦 VARIABLES Y OBJETOS GLOBALES
// ==============================================================================
WebServer server(80);
ClosedCube_HDC1080 hdc1080;

float currentTemp = 0.0;
float currentHum  = 0.0;
int lastHttpStatus = 0;
unsigned long lastTxTime = 0;
unsigned long txCount = 0;

// ==============================================================================
// 🌡️ LECTURA DEL SENSOR HDC1080
// ==============================================================================
void readSensor() {
    float t = hdc1080.readTemperature();
    float h = hdc1080.readHumidity();

    if (!isnan(t) && !isnan(h) && t > -40.0 && t < 125.0) {
        currentTemp = t;
        currentHum  = h;
    } else {
        Serial.println("⚠️ [HDC1080] Error de lectura, manteniendo valor anterior.");
    }
}

// ==============================================================================
// 🚀 TRANSMISIÓN HTTP POST A FIWARE IOT AGENT
// ==============================================================================
void sendToFiware() {
    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("❌ [Wi-Fi] Desconectado, omitiendo transmisión...");
        return;
    }

    WiFiClient client;
    HTTPClient http;

    String url = "http://" + String(FIWARE_HOST) + ":" + String(FIWARE_PORT) +
                 "/iot/json?k=" + String(API_KEY) + "&i=" + String(NODE_ID);

    http.begin(client, url);
    http.addHeader("Content-Type", "application/json");

    // Construcción del JSON con ArduinoJson
    StaticJsonDocument<200> doc;
    doc["t"] = serialized(String(currentTemp, 2));
    doc["h"] = serialized(String(currentHum, 2));
    doc["presence"] = 1;
    doc["lat"] = serialized(String(ROOM_LAT, 6));
    doc["lon"] = serialized(String(ROOM_LON, 6));

    String payload;
    serializeJson(doc, payload);

    int httpCode = http.POST(payload);
    lastHttpStatus = httpCode;
    txCount++;

    if (httpCode == HTTP_CODE_OK) {
        Serial.printf("[FIWARE OK #%lu] %s -> %s (HTTP 200)\n", txCount, NODE_ID, payload.c_str());
    } else {
        Serial.printf("[FIWARE ERR #%lu] HTTP %d: %s\n", txCount, httpCode, http.errorToString(httpCode).c_str());
    }

    http.end();
}

// ==============================================================================
// 🖥️ ENDPOINTS DEL SERVIDOR WEB EMBEBIDO (EDGE DIAGNOSTICS)
// ==============================================================================
void handleRoot() {
    String html = "<!DOCTYPE html><html lang='es'><head><meta charset='UTF-8'>";
    html += "<meta name='viewport' content='width=device-width, initial-scale=1.0'>";
    html += "<meta http-equiv='refresh' content='3'>";
    html += "<title>Nodo " + String(NODE_ID) + " - Dalet</title>";
    html += "<style>";
    html += "body { font-family: -apple-system, sans-serif; background: #0f172a; color: #f8fafc; padding: 20px; text-align: center; }";
    html += ".card { background: #1e293b; max-width: 440px; margin: 0 auto; padding: 24px; border-radius: 12px; border: 1px solid #334155; }";
    html += ".metric { font-size: 2.2rem; font-weight: bold; color: #38bdf8; margin: 6px 0; }";
    html += ".metric-sub { font-size: 1.8rem; font-weight: bold; color: #34d399; margin: 6px 0; }";
    html += ".badge { display: inline-block; padding: 4px 10px; border-radius: 9999px; font-size: 0.8rem; background: #0284c7; color: white; margin-bottom: 10px; }";
    html += ".status { font-size: 0.88rem; color: #94a3b8; margin-top: 16px; border-top: 1px solid #334155; padding-top: 12px; text-align: left; }";
    html += "a { color: #38bdf8; text-decoration: none; }";
    html += "</style></head><body>";
    html += "<div class='card'>";
    html += "<span class='badge'>" + String(CORNER_NAME) + "</span>";
    html += "<h2>🏛️ Nodo " + String(NODE_ID) + "</h2>";
    html += "<p style='color:#94a3b8;'>HDC1080 • Sala: " + String(ROOM_NAME) + "</p>";
    html += "<div class='metric'>" + String(currentTemp, 1) + " °C</div>";
    html += "<div style='color:#94a3b8; font-size: 0.85rem;'>Temperatura</div>";
    html += "<div class='metric-sub'>" + String(currentHum, 1) + " %</div>";
    html += "<div style='color:#94a3b8; font-size: 0.85rem;'>Humedad Relativa</div>";
    html += "<div class='status'>";
    html += "<b>📡 Wi-Fi IP:</b> " + WiFi.localIP().toString() + "<br>";
    html += "<b>📶 RSSI:</b> " + String(WiFi.RSSI()) + " dBm<br>";
    html += "<b>☁️ Destino FIWARE:</b> " + String(FIWARE_HOST) + ":" + String(FIWARE_PORT) + "<br>";
    html += "<b>🔄 Último Envío:</b> HTTP " + String(lastHttpStatus) + " (Envíos: " + String(txCount) + ")<br>";
    html += "<b>⏱️ Uptime:</b> " + String(millis() / 1000) + " s<br>";
    html += "<p style='text-align:center; margin-top:12px;'><a href='/json'>[Ver JSON Crudo]</a></p>";
    html += "</div></div></body></html>";

    server.send(200, "text/html", html);
}

void handleJson() {
    StaticJsonDocument<256> doc;
    doc["node_id"] = NODE_ID;
    doc["corner"] = CORNER_NAME;
    doc["room"] = ROOM_NAME;
    doc["temperature"] = currentTemp;
    doc["humidity"] = currentHum;
    doc["rssi"] = WiFi.RSSI();
    doc["last_http_code"] = lastHttpStatus;
    doc["tx_count"] = txCount;
    doc["uptime_sec"] = millis() / 1000;

    String jsonResponse;
    serializeJson(doc, jsonResponse);
    server.send(200, "application/json", jsonResponse);
}

// ==============================================================================
// 🚀 SETUP
// ==============================================================================
void setup() {
    Serial.begin(115200);
    delay(500);

    Serial.println("\n==================================================");
    Serial.printf("🏛️ DALET SENSOR NODE: %s (%s)\n", NODE_ID, CORNER_NAME);
    Serial.println("==================================================");

    // Inicializar I2C para sensor HDC1080 (Dirección 0x40)
    Wire.begin();
    hdc1080.begin(0x40);

    // Conexión Wi-Fi
    Serial.printf("Conectando a Wi-Fi: %s ", WIFI_SSID);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }
    Serial.println("\n✅ Wi-Fi Conectado!");
    Serial.print("🌐 Dashboard Local: http://");
    Serial.println(WiFi.localIP());

    // Iniciar servidor web local
    server.on("/", handleRoot);
    server.on("/json", handleJson);
    server.begin();
    Serial.println("🖥️ Servidor Web local iniciado en puerto 80.");

    readSensor();
}

// ==============================================================================
// 🔄 LOOP
// ==============================================================================
void loop() {
    server.handleClient();

    unsigned long now = millis();
    if (now - lastTxTime >= TX_INTERVAL_MS) {
        lastTxTime = now;
        readSensor();
        sendToFiware();
    }
}
