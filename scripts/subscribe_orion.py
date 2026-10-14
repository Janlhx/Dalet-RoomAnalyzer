#!/usr/bin/env python3
"""
scripts/subscribe_orion.py
Crea y verifica la Suscripción Webhook en FIWARE Orion Context Broker
para enviar notificaciones al Pipeline ETL cuando cambien temperatura o humedad.
"""

import sys
import json
import argparse
import requests

DEFAULT_ORION_URL = "http://localhost:1026"
DEFAULT_ETL_URL = "http://host.docker.internal:8000/v1/notify"
FIWARE_SERVICE = "openiot"
FIWARE_SERVICE_PATH = "/"

HEADERS = {
    "fiware-service": FIWARE_SERVICE,
    "fiware-servicepath": FIWARE_SERVICE_PATH,
    "Content-Type": "application/json"
}

def clean_old_subscriptions(orion_url: str):
    """Elimina suscripciones anteriores para evitar duplicados."""
    try:
        r = requests.get(f"{orion_url}/v2/subscriptions", headers=HEADERS, timeout=3)
        if r.status_code == 200:
            subs = r.json()
            for s in subs:
                sid = s.get("id")
                desc = s.get("description", "")
                if "ETL" in desc or "Dalet" in desc:
                    requests.delete(f"{orion_url}/v2/subscriptions/{sid}", headers=HEADERS, timeout=2)
                    print(f"  🗑️ Suscripción anterior eliminada: {sid}")
    except Exception:
        pass

def create_subscription(orion_url: str, etl_webhook_url: str):
    print("=" * 65)
    print("🏛️  DALET-ROOMANALYZER — REGISTRO DE SUSCRIPCIÓN EN ORION")
    print(f"📡 Orion:  {orion_url}")
    print(f"🎯 Destino Webhook ETL: {etl_webhook_url}")
    print("=" * 65)

    clean_old_subscriptions(orion_url)

    subscription_payload = {
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
        resp = requests.post(url, headers=HEADERS, json=subscription_payload, timeout=4)
        if resp.status_code == 201:
            sub_id = resp.headers.get("Location", "").split("/")[-1]
            print(f"\n✅ Suscripción creada exitosamente!")
            print(f"  • ID de Suscripción: {sub_id}")
            print(f"  • Entidades monitoreadas: type='Room' (todas las esquinas)")
            print(f"  • Atributos detonantes:  ['temperature', 'relativeHumidity']")
            print(f"  • URL de Notificación:   {etl_webhook_url}")
            return True
        else:
            print(f"\n❌ Error al crear suscripción ({resp.status_code}): {resp.text}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"\n❌ Error de conexión con Orion: {e}")
        return False

def list_subscriptions(orion_url: str):
    url = f"{orion_url}/v2/subscriptions"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=3)
        if resp.status_code == 200:
            subs = resp.json()
            print(f"\n📋 Suscripciones activas en Orion ({len(subs)}):")
            for s in subs:
                print(f"  - ID: {s.get('id')} | Estado: {s.get('status')} | Destino: {s.get('notification', {}).get('http', {}).get('url')}")
    except Exception as e:
        print(f"⚠️ Error al listar suscripciones: {e}")

def main():
    parser = argparse.ArgumentParser(description="Registrar suscripción de Orion hacia el ETL Worker")
    parser.add_argument("--host", default="localhost", help="Host de Orion Context Broker (default: localhost)")
    parser.add_argument("--orion-port", type=int, default=1026, help="Puerto de Orion (default: 1026)")
    parser.add_argument("--etl-url", default=DEFAULT_ETL_URL, help=f"URL del Webhook receptor (default: {DEFAULT_ETL_URL})")
    
    args = parser.parse_args()
    orion_url = f"http://{args.host}:{args.orion_port}"

    if create_subscription(orion_url, args.etl_url):
        list_subscriptions(orion_url)
        print("\n🎉 Listo: Cada vez que un sensor envíe datos, Orion notificará al Pipeline ETL.")

if __name__ == "__main__":
    main()
