#!/usr/bin/env python3
"""
scripts/provision.py
Aprovisionamiento de Servicio y Nodos Sensores de las 4 Esquinas en FIWARE IoT Agent JSON.
Permite ejecutar localmente o de forma remota contra una instancia EC2 de AWS.
"""

import os
import sys
import json
import time
import argparse
import requests

DEFAULT_HOST = os.getenv("FIWARE_HOST", "localhost")
FIWARE_SERVICE = os.getenv("FIWARE_SERVICE", "openiot")
FIWARE_SERVICE_PATH = os.getenv("FIWARE_SERVICE_PATH", "/")
API_KEY = os.getenv("FIWARE_API_KEY", "dalet_secret_key")
ENTITY_TYPE = os.getenv("FIWARE_ENTITY_TYPE", "Room")

HEADERS = {
    "fiware-service": FIWARE_SERVICE,
    "fiware-servicepath": FIWARE_SERVICE_PATH,
    "Content-Type": "application/json"
}

# Definición de los 4 nodos de esquina recomendados para la sala
CORNER_DEVICES = [
    {
        "device_id": "hdc1080_nw",
        "entity_name": "Room:01:Corner:NW",
        "corner_label": "Noroeste - Ventana",
        "corner_code": "NW"
    },
    {
        "device_id": "hdc1080_ne",
        "entity_name": "Room:01:Corner:NE",
        "corner_label": "Noreste - Puerta",
        "corner_code": "NE"
    },
    {
        "device_id": "hdc1080_sw",
        "entity_name": "Room:01:Corner:SW",
        "corner_label": "Suroeste - Servidores",
        "corner_code": "SW"
    },
    {
        "device_id": "hdc1080_se",
        "entity_name": "Room:01:Corner:SE",
        "corner_label": "Sureste - Climatizador",
        "corner_code": "SE"
    },
    # Dispositivo base para retrocompatibilidad
    {
        "device_id": "hdc1080_01",
        "entity_name": "Room:01",
        "corner_label": "Sensor Central Consolidado",
        "corner_code": "CENTER"
    }
]

def wait_for_services(orion_url, iota_url, timeout=30):
    print(f"⏳ Verificando conectividad con Orion ({orion_url}) e IoT Agent ({iota_url})...")
    start_time = time.time()
    
    orion_ok = False
    iota_ok = False
    
    while time.time() - start_time < timeout:
        if not orion_ok:
            try:
                r = requests.get(f"{orion_url}/version", timeout=2)
                if r.status_code == 200:
                    orion_ok = True
                    print(f"  ✅ Orion Context Broker disponible en {orion_url}")
            except Exception:
                pass

        if not iota_ok:
            try:
                r = requests.get(f"{iota_url}/iot/about", timeout=2)
                if r.status_code == 200:
                    iota_ok = True
                    print(f"  ✅ IoT Agent JSON disponible en {iota_url}")
            except Exception:
                pass

        if orion_ok and iota_ok:
            return True
        time.sleep(2)
        
    print("❌ Tiempo de espera agotado. Verifica que los servicios estén activos y que los puertos estén abiertos en el Security Group de AWS.")
    return False

def provision_service(iota_url):
    print("\n📦 1. Aprovisionando Grupo de Servicios en IoT Agent...")
    url = f"{iota_url}/iot/services"
    payload = {
        "services": [
            {
                "apikey": API_KEY,
                "cbroker": "http://fiware-orion:1026",
                "entity_type": ENTITY_TYPE,
                "resource": "/iot/json"
            }
        ]
    }

    resp = requests.post(url, headers=HEADERS, json=payload)
    if resp.status_code == 201:
        print("  ✅ Servicio aprovisionado exitosamente (HTTP 201).")
    elif resp.status_code in [409, 422]:
        print("  ℹ️  El servicio o API Key ya se encuentra registrado.")
    else:
        print(f"  ⚠️ Respuesta inesperada ({resp.status_code}): {resp.text}")

def provision_devices(iota_url):
    print(f"\n📡 2. Aprovisionando 4 Nodos de Esquina en IoT Agent...")
    url = f"{iota_url}/iot/devices"
    
    devices_payload = []
    for node in CORNER_DEVICES:
        dev_id = node["device_id"]
        ent_name = node["entity_name"]
        
        # Limpieza previa si existe
        try:
            requests.delete(f"{url}/{dev_id}", headers=HEADERS, timeout=2)
        except Exception:
            pass

        devices_payload.append({
            "device_id": dev_id,
            "entity_name": ent_name,
            "entity_type": ENTITY_TYPE,
            "timezone": "America/Bogota",
            "attributes": [
                { "object_id": "t", "name": "temperature", "type": "Number" },
                { "object_id": "h", "name": "relativeHumidity", "type": "Number" },
                { "object_id": "presence", "name": "presence", "type": "Integer" },
                { "object_id": "lat", "name": "latitude", "type": "Number" },
                { "object_id": "lon", "name": "longitude", "type": "Number" }
            ],
            "static_attributes": [
                { "name": "cornerLabel", "type": "Text", "value": node["corner_label"] },
                { "name": "cornerCode", "type": "Text", "value": node["corner_code"] },
                { "name": "refRoom", "type": "Text", "value": "Room:01" },
                { "name": "sensorModel", "type": "Text", "value": "LilyGO-ESP32-HDC1080" }
            ]
        })

    resp = requests.post(url, headers=HEADERS, json={"devices": devices_payload})
    if resp.status_code in [201, 204]:
        print(f"  ✅ {len(devices_payload)} dispositivos aprovisionados exitosamente.")
        return True
    elif resp.status_code == 409:
        print("  ℹ️  Dispositivos ya registrados.")
        return True
    else:
        print(f"  ❌ Error al aprovisionar dispositivos ({resp.status_code}): {resp.text}")
        return False

def verify_provisioning(iota_url):
    print(f"\n🔍 3. Verificando dispositivos en IoT Agent...")
    url = f"{iota_url}/iot/devices"
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code == 200:
        data = resp.json().get("devices", [])
        print(f"  ✅ {len(data)} dispositivos registrados en el servicio '{FIWARE_SERVICE}':")
        for dev in data:
            d_id = dev.get("device_id")
            e_name = dev.get("entity_name")
            print(f"     • Dispositivo: {d_id:<14} ➔ Entidad: {e_name}")
        return True
    else:
        print(f"  ❌ Error al consultar dispositivos ({resp.status_code}): {resp.text}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Aprovisionar 4 sensores de esquina en FIWARE IoT Agent JSON")
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"Host de FIWARE (default: {DEFAULT_HOST})")
    parser.add_argument("--iota-port", type=int, default=4041, help="Puerto de gestión del IoT Agent (default: 4041)")
    parser.add_argument("--orion-port", type=int, default=1026, help="Puerto de Orion Context Broker (default: 1026)")
    args = parser.parse_args()

    iota_url = f"http://{args.host}:{args.iota_port}"
    orion_url = f"http://{args.host}:{args.orion_port}"

    print("=" * 65)
    print("🏛️  DALET-ROOMANALYZER — APROVISIONAMIENTO TOPOLOGÍA 4 ESQUINAS")
    print(f"📍 Servidor destino: {args.host}")
    print("=" * 65)
    
    if not wait_for_services(orion_url, iota_url):
        sys.exit(1)
        
    provision_service(iota_url)
    if provision_devices(iota_url):
        verify_provisioning(iota_url)
        
    print("\n🎉 Aprovisionamiento de las 4 esquinas completado con éxito.")
    print(f"👉 Puedes simular la sala completa ejecutando: python scripts/simulator.py --host {args.host} --all-corners")

if __name__ == "__main__":
    main()
