#!/usr/bin/env python3
"""
scripts/subscribe_alerts.py
Registra en FIWARE Orion Context Broker la Suscripción Condicional para Alertas Reactivas (Escenario #2).
Filtra mediante expresión NGSI-v2: 'temperature > UMBRAL' hacia el servidor Flask en :5000/alerta.
"""

import socket
import argparse
import requests

DEFAULT_ORION_URL = "http://localhost:1026"
DEFAULT_THRESHOLD = 26.0
FIWARE_SERVICE = "openiot"
FIWARE_SERVICE_PATH = "/"

HEADERS = {
    "fiware-service": FIWARE_SERVICE,
    "fiware-servicepath": FIWARE_SERVICE_PATH,
    "Content-Type": "application/json"
}

def detect_host_ip() -> str:
    """Detecta la IP privada/local de la máquina (ej. 172.31.19.146 en AWS EC2)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "172.17.0.1"

def subscribe_conditional_alerts(orion_url: str, alert_url: str, threshold: float):
    print(f"\n🚨 Creando Suscripción Condicional en Orion (Escenario #2: t > {threshold} °C)...")
    
    payload = {
        "description": "Alerta Reactiva Escenario 2 Umbral Termico",
        "subject": {
            "entities": [
                {
                    "idPattern": ".*",
                    "type": "Room"
                }
            ],
            "condition": {
                "attrs": ["temperature"],
                "expression": {
                    "q": f"temperature>{threshold}"
                }
            }
        },
        "notification": {
            "http": {
                "url": alert_url
            },
            "attrs": [
                "temperature",
                "relativeHumidity",
                "presence",
                "cornerLabel",
                "cornerCode"
            ]
        }
    }

    url = f"{orion_url}/v2/subscriptions"
    try:
        resp = requests.post(url, headers=HEADERS, json=payload, timeout=4)
        if resp.status_code in [201, 200]:
            sub_id = resp.headers.get("Location", "").split("/")[-1]
            print(f"  ✅ Suscripción condicional creada exitosamente (ID: {sub_id})")
            print(f"     • Regla en Orion: temperature > {threshold} °C")
            print(f"     • Destino Webhook: {alert_url}")
            return True
        else:
            print(f"  ❌ Error al crear suscripción ({resp.status_code}): {resp.text}")
            return False
    except Exception as e:
        print(f"  ❌ Error de conexión con Orion: {e}")
        return False

def list_subscriptions(orion_url: str):
    url = f"{orion_url}/v2/subscriptions"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=3)
        if resp.status_code == 200:
            subs = resp.json()
            print(f"\n📋 Suscripciones activas en Orion ({len(subs)}):")
            for s in subs:
                cond = s.get("subject", {}).get("condition", {})
                q_expr = cond.get("expression", {}).get("q", "Sin condición (todas las lecturas)")
                dest = s.get("notification", {}).get("http", {}).get("url")
                print(f"  - ID: {s.get('id')}")
                print(f"    • Desc: {s.get('description')}")
                print(f"    • Condición: {q_expr}")
                print(f"    • Destino: {dest}\n")
    except Exception as e:
        print(f"⚠️ Error al listar suscripciones: {e}")

def main():
    detected_ip = detect_host_ip()
    default_alert_webhook = f"http://{detected_ip}:5000/alerta"

    parser = argparse.ArgumentParser(description="Registrar Suscripción Condicional en Orion (Escenario #2: t > X)")
    parser.add_argument("--host", default="localhost", help="Host de Orion Context Broker (default: localhost)")
    parser.add_argument("--orion-port", type=int, default=1026, help="Puerto de Orion (default: 1026)")
    parser.add_argument("--alert-url", default=default_alert_webhook, help=f"URL del Webhook de alertas Flask (default: {default_alert_webhook})")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD, help=f"Umbral térmico para disparar alerta en °C (default: {DEFAULT_THRESHOLD})")

    args = parser.parse_args()
    orion_url = f"http://{args.host}:{args.orion_port}"

    print("=" * 70)
    print("🏛️  DALET-ROOMANALYZER — REGISTRO DE ALERTAS REACTIVAS (ESCENARIO #2)")
    print(f"📡 Orion: {orion_url}")
    print(f"🎯 Condición: temperature > {args.threshold} °C")
    print(f"📬 Webhook: {args.alert_url}")
    print("=" * 70)

    subscribe_conditional_alerts(orion_url, args.alert_url, args.threshold)
    list_subscriptions(orion_url)

if __name__ == "__main__":
    main()
