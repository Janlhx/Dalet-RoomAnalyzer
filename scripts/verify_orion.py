#!/usr/bin/env python3
"""
scripts/verify_orion.py
Consulta el estado de las entidades en FIWARE Orion Context Broker.
Permite inspeccionar las 4 esquinas de la sala, calcular el promedio espacial
y evaluar el gradiente térmico (ΔT) entre las esquinas en tiempo real.
"""

import sys
import json
import argparse
import requests

DEFAULT_ORION_URL = "http://localhost:1026"
DEFAULT_SERVICE = "openiot"
DEFAULT_SERVICE_PATH = "/"

CORNER_ENTITIES = [
    ("Room:01:Corner:NW", "Noroeste (Ventana)"),
    ("Room:01:Corner:NE", "Noreste (Puerta)"),
    ("Room:01:Corner:SW", "Suroeste (Servidores)"),
    ("Room:01:Corner:SE", "Sureste (Climatizador)")
]

def check_all_corners(orion_url: str, service: str, service_path: str):
    headers = {
        "fiware-service": service,
        "fiware-servicepath": service_path
    }

    print("=" * 75)
    print(f"🏛️  DALET-ROOMANALYZER — ESTADO ESPACIAL DE LA SALA EN ORION CONTEXT BROKER")
    print(f"📡 Broker: {orion_url} | Service: {service} | Path: {service_path}")
    print("=" * 75)

    temps = []
    hums = []
    presence_sum = 0
    results = []

    for entity_id, label in CORNER_ENTITIES:
        url = f"{orion_url}/v2/entities/{entity_id}"
        try:
            resp = requests.get(url, headers=headers, timeout=3)
            if resp.status_code == 200:
                data = resp.json()
                t = data.get("temperature", {}).get("value")
                h = data.get("relativeHumidity", {}).get("value")
                p = data.get("presence", {}).get("value", 0)
                
                if t is not None:
                    temps.append(float(t))
                if h is not None:
                    hums.append(float(h))
                if p:
                    presence_sum += int(p)

                results.append({
                    "id": entity_id,
                    "label": label,
                    "t": t,
                    "h": h,
                    "p": p,
                    "status": "OK"
                })
            elif resp.status_code == 404:
                results.append({"id": entity_id, "label": label, "status": "NO DATOS (404)"})
            else:
                results.append({"id": entity_id, "label": label, "status": f"HTTP {resp.status_code}"})
        except requests.exceptions.RequestException as e:
            print(f"❌ Error conectando a Orion: {e}")
            return False

    # Imprimir tabla por esquinas
    print(f"\n{'ESQUINA':<26} | {'ENTIDAD':<20} | {'TEMP (°C)':<9} | {'HUM (%)':<8} | {'PRES':<4} | ESTADO")
    print("-" * 75)
    for r in results:
        if r.get("status") == "OK":
            t_str = f"{r['t']:.2f}" if r['t'] is not None else "--"
            h_str = f"{r['h']:.2f}" if r['h'] is not None else "--"
            p_str = str(r['p'])
            print(f"{r['label']:<26} | {r['id']:<20} | {t_str:>9} | {h_str:>8} | {p_str:>4} | ✅ Conectado")
        else:
            print(f"{r['label']:<26} | {r['id']:<20} | {'--':>9} | {'--':>8} | {'--':>4} | ⚠️ {r['status']}")

    # Resumen y Gradiente Espacial
    if temps:
        avg_t = sum(temps) / len(temps)
        min_t = min(temps)
        max_t = max(temps)
        delta_t = max_t - min_t
        avg_h = sum(hums) / len(hums) if hums else 0.0

        print("\n" + "=" * 75)
        print("📊 ANÁLISIS ESPACIAL CONSOLIDADO DE LA SALA:")
        print(f"  • Temperatura Promedio:     {avg_t:.2f} °C")
        print(f"  • Humedad Promedio:         {avg_h:.2f} %")
        print(f"  • Gradiente Térmico (ΔT):   {delta_t:.2f} °C (Min: {min_t:.2f}°C, Max: {max_t:.2f}°C)")
        print(f"  • Ocupación Detectada:      {'Detectada (' + str(presence_sum) + ' nodos)' if presence_sum > 0 else 'Sala Vacía'}")
        
        if delta_t > 3.0:
            print(f"  ⚠️ ALERTA ESPACIAL: Gradiente térmico excesivo (ΔT > 3.0°C). Posible desbalance en climatización o foco de calor.")
        else:
            print(f"  ✅ Distribución térmica homogénea en la sala.")
        print("=" * 75)
    else:
        print("\nℹ️  Aún no se han recibido datos en Orion. Envía telemetría con 'python scripts/simulator.py'.")

    return True

def main():
    parser = argparse.ArgumentParser(description="Verificar estado espacial de la sala en Orion Context Broker")
    parser.add_argument("--host", default="localhost", help="Host de Orion Context Broker (default: localhost)")
    parser.add_argument("--port", type=int, default=1026, help="Puerto de Orion Context Broker (default: 1026)")
    parser.add_argument("--url", default=None, help="URL completa de Orion Context Broker (opcional)")
    parser.add_argument("--service", default=DEFAULT_SERVICE, help="FIWARE Service Header (default: openiot)")
    parser.add_argument("--service-path", default=DEFAULT_SERVICE_PATH, help="FIWARE Service Path Header (default: /)")
    
    args = parser.parse_args()
    orion_url = args.url if args.url else f"http://{args.host}:{args.port}"
    check_all_corners(orion_url, args.service, args.service_path)

if __name__ == "__main__":
    main()
