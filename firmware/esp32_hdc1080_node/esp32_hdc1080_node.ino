/*
 * ==============================================================================
 * 🏛️ Dalet-RoomAnalyzer — Firmware Nodo Sensor IoT (LilyGO ESP32 / ESP8266)
 * ==============================================================================
 * Sensor: HDC1080 (I2C: SDA=21, SCL=22 en ESP32 estándar, o pines LilyGO)
 *
 * ARQUITECTURA DUAL (Recomendación Académica):
 * 1. Servidor Web Embebido (Puerto 80 - Edge / Diagnóstico Local):
 *    - Ruta '/': Dashboard web local en HTML con estado en vivo, RSSI y diagnóstico.
 *    - Ruta '/json': API REST local con telemetría cruda en formato JSON.
 *
 * 2. Cliente HTTP Periódico (Hacia la Nube - Estándar FIWARE IoT Agent):
 *    - Realiza HTTP POST a http://<EC2_IP>:7896/iot/json?k=<API_KEY>&i=<DEVICE_ID>
 * ==============================================================================
 */

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

#include <Wire.h>
#include <ClosedCube_HDC1080.h> // Librería oficial recomendada para HDC1080

// ==============================================================================
// ⚙️ CONFIGURACIÓN DEL NODO Y DE LA ESQUINA
// (Cambiar estos valores para cada uno de los 4 nodos)
// ==============================================================================
#define NODE_ID         "hdc1080_nw"             // hdc1080_nw, hdc1080_ne, hdc1080_sw, hdc1080_se
#define CORNER_NAME     "Esquina Noroeste (Ventana)"
#define ROOM_NAME       "Room:01"

// Coordenadas aproximadas de la sala
const float ROOM_LAT = 6.2442;
const float ROOM_LON = -75.5812;

// ==============================================================================
// 🌐 CONFIGURACIÓN WI-FI Y FIWARE (AWS EC2)
// ==============================================================================
const char* WIFI_SSID     = "TU_SSID_WIFI";
const char* WIFI_PASSWORD = "TU_PASSWORD_WIFI";

// Dirección IP o DNS de tu instancia EC2 en AWS Academy
const char* FIWARE_HOST   = "EC2_PUBLIC_IP";     // Reemplazar con la IP pública de tu EC2
const int   FIWARE_PORT   = 7896;                // Puerto Southbound de IoT Agent JSON
const char* API_KEY       = "dalet_secret_key";  // API Key aprovisionada en el servicio

// Intervalo de transmisión a FIWARE (en milisegundos)
const unsigned long TX_INTERVAL_MS = 5000;       // Cada 5 segundos

// ==============================================================================
// 📦 OBJETOS GLOBALES
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

    // Verificación de integridad básica
    if (!isnan(t) && !isnan(h) && t > -40.0 && t < 125.0) {
        currentTemp = t;
        currentHum  = h;
    } else {
        Serial.println("⚠️ Error al leer HDC1080, conservando último valor válido.");
    }
}

// ==============================================================================
// 🚀 TRANSMISIÓN HTTP POST A FIWARE IOT AGENT
// ==============================================================================
void sendToFiware() {
    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("❌ Wi-Fi desconectado, reintentando...");
        return;
    }

    WiFiClient client;
    HTTPClient http;

    String url = "http://" + String(FIWARE_HOST) + ":" + String(FIWARE_PORT) +
                 "/iot/json?k=" + String(API_KEY) + "&i=" + String(NODE_ID);

    http.begin(client, url);
    http.addHeader("Content-Type", "application/json");

    // Payload según especificación de ARCHITECTURE.md
    String payload = "{\"t\":" + String(currentTemp, 2) +
                     ",\"h\":" + String(currentHum, 2) +
                     ",\"presence\":1" +
                     ",\"lat\":" + String(ROOM_LAT, 6) +
                     ",\"lon\":" + String(ROOM_LON, 6) + "}";

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
// 🖥️ CONTROLADORES DEL SERVIDOR WEB EMBEBIDO (EDGE DIAGNOSTICS)
// ==============================================================================
void handleRoot() {
    String html = "<!DOCTYPE html><html lang='es'><head><meta charset='UTF-8'>";
    html += "<meta name='viewport' content='width=device-width, initial-scale=1.0'>";
    html += "<meta http-equiv='refresh' content='3'>"; // Auto-recarga cada 3 segundos
    html += "<title>Nodo " + String(NODE_ID) + " - Dalet RoomAnalyzer</title>";
    html += "<style>";
    html += "body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #f8fafc; padding: 20px; text-align: center; }";
    html += ".card { background: #1e293b; max-width: 450px; margin: 0 auto; padding: 24px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); border: 1px solid #334155; }";
    html += ".metric { font-size: 2.2rem; font-weight: bold; color: #38bdf8; margin: 8px 0; }";
    html += ".metric-sub { font-size: 1.8rem; font-weight: bold; color: #34d399; margin: 8px 0; }";
    html += ".badge { display: inline-block; padding: 4px 10px; border-radius: 9999px; font-size: 0.8rem; background: #0284c7; color: white; margin-bottom: 12px; }";
    html += ".status { font-size: 0.9rem; color: #94a3b8; margin-top: 16px; border-top: 1px solid #334155; padding-top: 12px; text-align: left; }";
    html += "a { color: #38bdf8; text-decoration: none; }";
    html += "</style></head><body>";
    html += "<div class='card'>";
    html += "<span class='badge'>" + String(CORNER_NAME) + "</span>";
    html += "<h2>🏛️ Nodo " + String(NODE_ID) + "</h2>";
    html += "<p style='color:#94a3b8;'>Sensor HDC1080 • Sala: " + String(ROOM_NAME) + "</p>";
    
    html += "<div class='metric'>" + String(currentTemp, 1) + " °C</div>";
    html += "<div style='color:#94a3b8; font-size: 0.85rem;'>Temperatura Ambiente</div>";
    
    html += "<div class='metric-sub'>" + String(currentHum, 1) + " %</div>";
    html += "<div style='color:#94a3b8; font-size: 0.85rem;'>Humedad Relativa</div>";
    
    html += "<div class='status'>";
    html += "<b>📡 Wi-Fi IP:</b> " + WiFi.localIP().toString() + "<br>";
    html += "<b>📶 Señal RSSI:</b> " + String(WiFi.RSSI()) + " dBm<br>";
    html += "<b>☁️ Destino FIWARE:</b> " + String(FIWARE_HOST) + ":" + String(FIWARE_PORT) + "<br>";
    html += "<b>🔄 Último Envío:</b> HTTP " + String(lastHttpStatus) + " (Envíos: " + String(txCount) + ")<br>";
    html += "<b>⏱️ Uptime:</b> " + String(millis() / 1000) + " s<br>";
    html += "<p style='text-align:center; margin-top:14px;'><a href='/json'>[Ver Datos Crudos en /json]</a></p>";
    html += "</div></div></body></html>";

    server.send(200, "text/html", html);
}

void handleJson() {
    String json = "{\"node_id\":\"" + String(NODE_ID) + "\"" +
                  ",\"corner\":\"" + String(CORNER_NAME) + "\"" +
                  ",\"room\":\"" + String(ROOM_NAME) + "\"" +
                  ",\"temperature\":" + String(currentTemp, 2) +
                  ",\"humidity\":" + String(currentHum, 2) +
                  ",\"rssi\":" + String(WiFi.RSSI()) +
                  ",\"last_http_code\":" + String(lastHttpStatus) +
                  ",\"tx_count\":" + String(txCount) +
                  ",\"uptime_seconds\":" + String(millis() / 1000) + "}";
    server.send(200, "application/json", json);
}

// ==============================================================================
// 🚀 INICIALIZACIÓN (SETUP)
// ==============================================================================
void setup() {
    Serial.begin(115200);
    delay(500);

    Serial.println("\n==================================================");
    Serial.printf("🏛️ Iniciando Nodo %s (%s)\n", NODE_ID, CORNER_NAME);
    Serial.println("==================================================");

    // Inicializar bus I2C y sensor HDC1080 (Dirección I2C estándar: 0x40)
    Wire.begin();
    hdc1080.begin(0x40);

    // Conexión Wi-Fi
    Serial.printf("Conectando a Wi-Fi: %s ", WIFI_SSID);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }
    Serial.println("\n✅ Wi-Fi conectado exitosamente!");
    Serial.print("🌐 IP Local del Nodo: http://");
    Serial.println(WiFi.localIP());

    // Iniciar servidor web embebido (Edge Diagnostics)
    server.on("/", handleRoot);
    server.on("/json", handleJson);
    server.begin();
    Serial.println("🖥️ Servidor Web local iniciado en puerto 80.");

    // Primera lectura
    readSensor();
}

// ==============================================================================
// 🔄 BUCLE PRINCIPAL (LOOP)
// ==============================================================================
void loop() {
    // 1. Atender peticiones del Servidor Web local embebido
    server.handleClient();

    // 2. Disparar transmisión periódica hacia FIWARE IoT Agent
    unsigned long now = millis();
    if (now - lastTxTime >= TX_INTERVAL_MS) {
        lastTxTime = now;
        readSensor();
        sendToFiware();
    }
}
