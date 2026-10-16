#!/usr/bin/env python3
"""
scripts/subscribe_orion.py
Crea y verifica las Suscripciones Webhook en FIWARE Orion Context Broker:
1. Suscripción a QuantumLeap: Persiste series temporales en CrateDB.
2. Suscripción al Pipeline ETL: Calcula Sensación Térmica (NOAA), Punto de Rocío y ΔT.
"""

import sys
import json
import socket
import argparse
import requests

DEFAULT_ORION_URL = "http://localhost:1026"
DEFAULT_QL_URL = "http://quantumleap:8668/v2/notify"
FIWARE_SERVICE = "openiot"
FIWARE_SERVICE_PATH = "/"

HEADERS = {
    "fiware-service": FIWARE_SERVICE,
    "fiware-servicepath": FIWARE_SERVICE_PATH,
    "Content-Type": "application/json"
}

def detect_host_ip() -> str:
    """Detecta la IP local de la máquina (ej. 172.31.19.184 en AWS EC2)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "172.17.0.1"

def clean_old_subscriptions(orion_url: str):
    """Elimina suscripciones anteriores para evitar duplicados."""
    try:
        r = requests.get(f"{orion_url}/v2/subscriptions", headers=HEADERS, timeout=3)
        if r.status_code == 200:
            subs = r.json()
            for s in subs:
                sid = s.get("id")
                requests.delete(f"{orion_url}/v2/subscriptions/{sid}", headers=HEADERS, timeout=2)
                print(f"  🗑️ Suscripción anterior eliminada: {sid}")
    except Exception:
        pass

def subscribe_quantumleap(orion_url: str, ql_url: str):
    print("\n📦 1. Creando suscripción hacia QuantumLeap (Persistencia CrateDB)...")
    payload = {
        "description": "Notificar a QuantumLeap para persistencia historica en CrateDB",
        "subject": {
            "entities": [
                {
                    "idPattern": ".*",
                    "type": "Room"
                }
            ],
            "condition": {
                "attrs": ["temperature", "relativeHumidity"]
            }
        },
        "notification": {
            "http": {
                "url": ql_url
            },
            "attrs": [
                "temperature",
                "relativeHumidity",
                "presence"
            ],
            "metadata": ["dateCreated", "dateModified"]
        },
        "throttling": 1
    }

    url = f"{orion_url}/v2/subscriptions"
    try:
        resp = requests.post(url, headers=HEADERS, json=payload, timeout=4)
        if resp.status_code in [201, 200]:
            sub_id = resp.headers.get("Location", "").split("/")[-1]
            print(f"  ✅ QuantumLeap suscrito exitosamente (ID: {sub_id})")
            print(f"     • Destino: {ql_url} ➔ CrateDB :4200")
            return True
        else:
            print(f"  ❌ Error al suscribir QuantumLeap ({resp.status_code}): {resp.text}")
            return False
    except Exception as e:
        print(f"  ❌ Error de conexión al suscribir QuantumLeap: {e}")
        return False

def subscribe_etl(orion_url: str, etl_webhook_url: str):
    print("\n⚙️  2. Creando suscripción hacia Pipeline ETL Worker (FastAPI)...")
    payload = {
        "description": "Dalet ETL Webhook - Notificar ante cambios en esquinas de salas",
        "subject": {
            "entities": [
                {
                    "idPattern": ".*",
                    "type": "Room"
                }
            ],
            "condition": {
                "attrs": ["temperature", "relativeHumidity"]
            }
        },
        "notification": {
            "http": {
                "url": etl_webhook_url
            },
            "attrs": [
                "temperature",
                "relativeHumidity",
                "presence",
                "cornerLabel",
                "cornerCode"
            ]
        },
        "throttling": 1
    }

    url = f"{orion_url}/v2/subscriptions"
    try:
        resp = requests.post(url, headers=HEADERS, json=payload, timeout=4)
        if resp.status_code in [201, 200]:
            sub_id = resp.headers.get("Location", "").split("/")[-1]
            print(f"  ✅ ETL Worker suscrito exitosamente (ID: {sub_id})")
            print(f"     • Destino: {etl_webhook_url}")
            return True
        else:
            print(f"  ❌ Error al suscribir ETL ({resp.status_code}): {resp.text}")
            return False
    except Exception as e:
        print(f"  ❌ Error de conexión al suscribir ETL: {e}")
        return False

def list_subscriptions(orion_url: str):
    url = f"{orion_url}/v2/subscriptions"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=3)
        if resp.status_code == 200:
            subs = resp.json()
            print(f"\n📋 Suscripciones activas en Orion ({len(subs)}):")
            for s in subs:
                dest = s.get("notification", {}).get("http", {}).get("url")
                print(f"  - ID: {s.get('id')} | Desc: {s.get('description')[:40]}... | Destino: {dest}")
    except Exception as e:
        print(f"⚠️ Error al listar suscripciones: {e}")

def main():
    detected_ip = detect_host_ip()
    default_webhook = f"http://{detected_ip}:8000/v1/notify"

    parser = argparse.ArgumentParser(description="Registrar suscripciones de Orion (QuantumLeap + ETL Worker)")
    parser.add_argument("--host", default="localhost", help="Host de Orion Context Broker (default: localhost)")
    parser.add_argument("--orion-port", type=int, default=1026, help="Puerto de Orion (default: 1026)")
    parser.add_argument("--etl-url", default=default_webhook, help=f"URL del Webhook receptor ETL (default: {default_webhook})")
    parser.add_argument("--ql-url", default=DEFAULT_QL_URL, help=f"URL de QuantumLeap (default: {DEFAULT_QL_URL})")
    
    args = parser.parse_args()
    orion_url = f"http://{args.host}:{args.orion_port}"

    print("=" * 70)
    print("🏛️  DALET-ROOMANALYZER — REGISTRO DE SUSCRIPCIONES (ORION ➔ QUANTUMLEAP + ETL)")
    print(f"📡 Orion Context Broker: {orion_url}")
    print("=" * 70)

    clean_old_subscriptions(orion_url)
    subscribe_quantumleap(orion_url, args.ql_url)
    subscribe_etl(orion_url, args.etl_url)
    list_subscriptions(orion_url)

    print("\n🎉 Listo: Orion ahora notifica tanto a QuantumLeap (CrateDB) como a tu Pipeline ETL.")

if __name__ == "__main__":
    main()
