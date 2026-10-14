#pragma once

// ==============================================================================
// 🌐 CONFIGURACIÓN WI-FI Y FIWARE (AWS EC2 / SERVIDOR)
// ==============================================================================
// 1. Credenciales de la red Wi-Fi (Modifica estos dos campos)
#define WIFI_SSID           "TU_SSID_WIFI"
#define WIFI_PASSWORD       "TU_PASSWORD_WIFI"

// 2. Destino FIWARE IoT Agent (AWS EC2 o IP Local)
// Coloca la IP pública de tu instancia EC2 de AWS Academy:
#define FIWARE_HOST         "EC2_PUBLIC_IP"
#define FIWARE_PORT         7896
#define API_KEY             "dalet_secret_key"

// 3. Ubicación geográfica y metadatos de la sala
#define ROOM_LAT            6.2442f
#define ROOM_LON            -75.5812f

// 4. Temporizador de envío (en milisegundos)
#define TX_INTERVAL_MS      4000  // Cada 4 segundos
