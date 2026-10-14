#!/usr/bin/env python3
"""
scripts/simulator.py
Simulador de Nodos LilyGO (ESP32) / ESP8266 con Sensor HDC1080.
Soporta simular un solo nodo o la sala completa con los 4 nodos de esquina
(Noroeste, Noreste, Suroeste, Sureste) reflejando microclimas y gradientes térmicos.
"""

import sys
import time
import random
import argparse
import requests

DEFAULT_IOTA_SOUTH_URL = "http://localhost:7896/iot/json"
DEFAULT_API_KEY = "dalet_secret_key"

# Coordenadas base
DEFAULT_LAT = 6.2442
DEFAULT_LON = -75.5812

# Perfiles de microclima por esquina para simulación realista
CORNER_PROFILES = [
    {
        "id": "hdc1080_nw",
        "name": "Noroeste (Ventana / Fachada)",
        "temp_offset": 1.2,    # Recibe radiación solar
        "hum_offset": -2.0,
        "presence_prob": 0.4
    },
    {
        "id": "hdc1080_ne",
        "name": "Noreste (Puerta de Acceso)",
        "temp_offset": -0.3,   # Corriente de aire por circulación
        "hum_offset": 1.0,
        "presence_prob": 0.7
    },
    {
        "id": "hdc1080_sw",
        "name": "Suroeste (Zona de Servidores)",
        "temp_offset": 2.1,    # Disipación térmica de equipos
        "hum_offset": -3.5,
        "presence_prob": 0.2
    },
    {
        "id": "hdc1080_se",
        "name": "Sureste (Zona Climatizada AC)",
        "temp_offset": -1.8,   # Directamente bajo flujo de aire acondicionado
        "hum_offset": 3.0,
        "presence_prob": 0.3
    }
]

def send_telemetry(url: str, api_key: str, device_id: str, payload: dict):
    target_url = f"{url}?k={api_key}&i={device_id}"
    headers = {"Content-Type": "application/json"}
    
    try:
        resp = requests.post(target_url, headers=headers, json=payload, timeout=3)
        return resp.status_code, resp.text
    except requests.exceptions.RequestException as e:
        return None, str(e)

def run_simulation(args):
    target_url = args.url if args.url else f"http://{args.host}:{args.port}/iot/json"
    
    print("=" * 70)
    print("🚀 DALET-ROOMANALYZER — SIMULADOR HARDWARE LILYGO / HDC1080")
    print(f"📡 Destino IoT Agent: {target_url} (API Key: {args.api_key})")
    if args.all_corners:
        print("🗺️  Modo: 4 ESQUINAS DE LA SALA (NW, NE, SW, SE) con gradiente térmico")
    else:
        print(f"📍 Modo: NODO ÚNICO ({args.device_id})")
    print("=" * 70)

    nodes_to_simulate = CORNER_PROFILES if args.all_corners else [
        {
            "id": args.device_id,
            "name": "Nodo Específico",
            "temp_offset": 0.0,
            "hum_offset": 0.0,
            "presence_prob": 0.5
        }
    ]

    base_temp = args.temp
    base_hum = args.hum
    step = 0

    while True:
        step += 1
        timestamp_str = time.strftime("%H:%M:%S")
        print(f"\n⏱️  [{timestamp_str}] [Ciclo #{step:03d}] ---------------------------------")

        for node in nodes_to_simulate:
            nid = node["id"]
            nname = node["name"]
            
            # Cálculo térmico con microclima
            t = base_temp + node["temp_offset"] + random.uniform(-0.25, 0.25)
            h = max(15.0, min(90.0, base_hum + node["hum_offset"] + random.uniform(-0.8, 0.8)))

            # Inyección de anomalía si se solicitó en el 3er ciclo (ej. recalentamiento en servidores SW)
            if args.spike and step >= 3 and nid == "hdc1080_sw":
                t += 4.5
                print(f"  🔥 [ANOMALÍA INYECTADA en {nid}]: Sobrecalentamiento crítico de +4.5°C!")

            presence = 1 if random.random() < node["presence_prob"] else 0

            payload = {
                "t": round(t, 2),
                "h": round(h, 2),
                "presence": presence,
                "lat": args.lat,
                "lon": args.lon
            }

            status, body = send_telemetry(target_url, args.api_key, nid, payload)
            if status == 200:
                print(f"  ✅ {nid:<12} ({nname:<28}): {payload['t']:>5.2f}°C | {payload['h']:>5.2f}% | Pres: {presence}")
            else:
                print(f"  ❌ {nid:<12} Error ({status}): {body}")

        if args.once:
            break

        if args.count and step >= args.count:
            print(f"\n✅ Finalizados {args.count} ciclos de transmisión.")
            break

        try:
            time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\n🛑 Simulación detenida por el usuario.")
            break

def main():
    parser = argparse.ArgumentParser(description="Simulador de Sensores HDC1080 para FIWARE IoT Agent")
    parser.add_argument("--host", default="localhost", help="Host del IoT Agent (default: localhost)")
    parser.add_argument("--port", type=int, default=7896, help="Puerto Southbound del IoT Agent (default: 7896)")
    parser.add_argument("--url", default=None, help="URL Southbound completa (opcional)")
    parser.add_argument("--api-key", default=DEFAULT_API_KEY, help="API Key de servicio (default: dalet_secret_key)")
    parser.add_argument("--device-id", default="hdc1080_nw", help="ID del dispositivo individual (default: hdc1080_nw)")
    parser.add_argument("--all-corners", action="store_true", default=True, help="Simular simultáneamente las 4 esquinas de la sala (default: True)")
    parser.add_argument("--single-node", dest="all_corners", action="store_false", help="Simular solo el nodo especificado en --device-id")
    parser.add_argument("--temp", type=float, default=24.5, help="Temperatura base (°C)")
    parser.add_argument("--hum", type=float, default=60.0, help="Humedad base (%)")
    parser.add_argument("--lat", type=float, default=DEFAULT_LAT, help="Latitud GPS")
    parser.add_argument("--lon", type=float, default=DEFAULT_LON, help="Longitud GPS")
    parser.add_argument("--interval", type=float, default=4.0, help="Intervalo en segundos entre ciclos (default: 4.0)")
    parser.add_argument("--once", action="store_true", help="Enviar un único ciclo y salir")
    parser.add_argument("--count", type=int, default=None, help="Número específico de ciclos a enviar")
    parser.add_argument("--spike", action="store_true", help="Inyectar pico térmico en esquina de servidores (SW) en ciclo 3")

    args = parser.parse_args()
    run_simulation(args)

if __name__ == "__main__":
    main()
