"""
etl/main.py
Servicio Worker ETL y API REST para Dalet-RoomAnalyzer (FastAPI).
1. EXTRACT: Recibe notificaciones NGSI-v2 de Orion en /v1/notify.
2. TRANSFORM: Calcula Sensación Térmica (NOAA), Punto de Rocío (Magnus),
   gradiente espacial (ΔT) y tasa de variación térmica temporal.
3. LOAD: Persiste métricas en SQLite WAL.
4. API: Expone endpoints para el Frontend y el Asistente Dalet AI.
"""

import sys
import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

class OrionNotification(BaseModel):
    subscriptionId: Optional[str] = "sub_orion_room_01"
    data: List[Dict[str, Any]] = Field(
        default=[
            {
                "id": "Room:01:Corner:NW",
                "type": "Room",
                "temperature": {"type": "Number", "value": 26.5},
                "relativeHumidity": {"type": "Number", "value": 55.0},
                "presence": {"type": "Integer", "value": 1},
                "cornerLabel": {"type": "Text", "value": "Noroeste - Ventana"},
                "cornerCode": {"type": "Text", "value": "NW"}
            }
        ],
        description="Lista de entidades enviadas por la suscripción NGSI-v2 de Orion"
    )

from etl.formulas import calculate_dew_point, calculate_heat_index, assess_condensation_risk, classify_comfort
from etl.database import (
    init_db, insert_reading, insert_spatial_snapshot, insert_alert,
    get_latest_readings_by_entity, get_recent_history, get_recent_alerts,
    get_recent_readings_for_rate_of_change
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("dalet-etl")

app = FastAPI(
    title="Dalet-RoomAnalyzer ETL & Analytics Worker",
    version="1.0.0",
    description="Pipeline ETL y Motor de Diagnóstico Ambiental para Salas IoT con FIWARE"
)

# Permitir CORS para desarrollo de frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    init_db()
    logger.info("🚀 Base de datos analítica SQLite (WAL) inicializada correctamente.")

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "dalet-etl-worker"}

# ==============================================================================
# 📥 1. EXTRACT & TRANSFORM: Webhook Receptor de Orion Context Broker
# ==============================================================================
@app.post("/v1/notify", status_code=status.HTTP_200_OK)
async def orion_notify_webhook(payload: OrionNotification):
    """
    Endpoint que recibe el webhook NGSI-v2 desde Orion Context Broker
    cada vez que un sensor actualiza sus valores de temperatura o humedad.
    """
    data_list = payload.data if payload and payload.data else []
    if not data_list:
        return {"status": "ignored", "reason": "No data in notification"}

    processed_count = 0

    for entity in data_list:
        entity_id = entity.get("id")
        if not entity_id:
            continue

        # Extraer atributos dinámicos
        t_attr = entity.get("temperature", {})
        h_attr = entity.get("relativeHumidity", {})
        p_attr = entity.get("presence", {})
        
        # Atributos estáticos
        cl_attr = entity.get("cornerLabel", {})
        cc_attr = entity.get("cornerCode", {})

        raw_temp = t_attr.get("value") if isinstance(t_attr, dict) else None
        raw_hum = h_attr.get("value") if isinstance(h_attr, dict) else None
        presence = p_attr.get("value", 0) if isinstance(p_attr, dict) else 0

        corner_label = cl_attr.get("value", "Esquina") if isinstance(cl_attr, dict) else "Esquina"
        corner_code = cc_attr.get("value", "CORNER") if isinstance(cc_attr, dict) else "CORNER"

        # Validación / Limpieza de anomalías (filtrado de nulos o valores imposibles)
        if raw_temp is None or raw_hum is None:
            continue
        try:
            temp = float(raw_temp)
            hum = float(raw_hum)
        except (ValueError, TypeError):
            continue

        if temp < -40.0 or temp > 85.0 or hum <= 0.0 or hum > 100.0:
            logger.warning(f"⚠️ Lectura descartada por anomalía extrema: T={temp}, H={hum} en {entity_id}")
            continue

        # ======================================================================
        # ⚙️ TRANSFORM: Cálculos Físicos y de Confort
        # ======================================================================
        dew_point = calculate_dew_point(temp, hum)
        heat_index = calculate_heat_index(temp, hum)
        condensation = assess_condensation_risk(temp, dew_point)

        # 1. Evaluación de tasa de cambio rápido (ΔT / Δt > 2.0°C en 5 minutos)
        past_temps = get_recent_readings_for_rate_of_change(entity_id, minutes=5)
        if past_temps and len(past_temps) >= 2:
            delta_temporal = temp - past_temps[0]
            if delta_temporal >= 2.0:
                msg = f"Tasa de aumento térmico acelerada en {corner_label}: +{delta_temporal:.2f}°C en 5 min."
                insert_alert(entity_id, "RAPID_THERMAL_INCREASE", "CRITICAL", msg)
                logger.warning(f"🔥 ALERTA: {msg}")

        # 2. Evaluación de riesgo de condensación
        if condensation["level"] == "CRITICAL":
            msg = f"Riesgo inminente de condensación en {corner_label} (T={temp}°C, Rocío={dew_point}°C)."
            insert_alert(entity_id, "CONDENSATION_RISK", "CRITICAL", msg)
            logger.warning(f"💧 ALERTA: {msg}")

        # ======================================================================
        # 💾 LOAD: Inserción en SQLite WAL
        # ======================================================================
        insert_reading(
            entity_id=entity_id,
            corner_code=corner_code,
            corner_label=corner_label,
            temp=temp,
            hum=hum,
            heat_index=heat_index,
            dew_point=dew_point,
            presence=int(presence)
        )
        processed_count += 1

        logger.info(f"📊 [ETL Processed] {entity_id:<20} -> T: {temp:>5.2f}°C | Hum: {hum:>5.2f}% | "
                    f"Sensación: {heat_index:>5.2f}°C | Rocío: {dew_point:>5.2f}°C")

    # ==========================================================================
    # 🗺️ EVALUACIÓN ESPACIAL CONSOLIDADA DE LA SALA (4 ESQUINAS)
    # ==========================================================================
    latest_readings = get_latest_readings_by_entity()
    if latest_readings and len(latest_readings) >= 2:
        temps = [r["temperature"] for r in latest_readings]
        hums = [r["humidity"] for r in latest_readings]
        his = [r["heat_index"] for r in latest_readings]

        avg_temp = round(sum(temps) / len(temps), 2)
        avg_hum = round(sum(hums) / len(hums), 2)
        avg_hi = round(sum(his) / len(his), 2)

        min_temp = min(temps)
        max_temp = max(temps)
        delta_t_spatial = round(max_temp - min_temp, 2)

        # Identificar Hotspot y Coldspot
        hotspot = next(r["corner_label"] for r in latest_readings if r["temperature"] == max_temp)
        coldspot = next(r["corner_label"] for r in latest_readings if r["temperature"] == min_temp)

        comfort = classify_comfort(avg_temp, avg_hum, delta_t_spatial)

        insert_spatial_snapshot(
            room_id="Room:01",
            avg_temp=avg_temp,
            avg_hum=avg_hum,
            avg_hi=avg_hi,
            delta_t=delta_t_spatial,
            hotspot=hotspot,
            coldspot=coldspot,
            comfort_status=comfort["status"],
            comfort_reason=comfort["reason"]
        )

        if delta_t_spatial >= 3.0:
            msg = f"Desbalance térmico espacial severo (ΔT = {delta_t_spatial}°C). Hotspot: {hotspot} ({max_temp}°C) vs Coldspot: {coldspot} ({min_temp}°C)."
            insert_alert("Room:01", "SPATIAL_IMBALANCE", "WARNING", msg)

    return {"status": "success", "processed_entities": processed_count}

# ==============================================================================
# 📊 2. API REST DE CONSULTA PARA FRONTEND Y DALET AI
# ==============================================================================
@app.get("/api/status")
def get_room_status():
    """
    Retorna el estado consolidado de la sala, las lecturas actuales de las 4 esquinas,
    el gradiente térmico (ΔT), el semáforo de confort y las alertas activas.
    """
    corners = get_latest_readings_by_entity()
    if not corners:
        return {"status": "WAITING_DATA", "message": "Aún no se han recibido lecturas de sensores."}

    temps = [c["temperature"] for c in corners]
    hums = [c["humidity"] for c in corners]
    his = [c["heat_index"] for c in corners]

    avg_temp = round(sum(temps) / len(temps), 2)
    avg_hum = round(sum(hums) / len(hums), 2)
    avg_hi = round(sum(his) / len(his), 2)
    delta_t = round(max(temps) - min(temps), 2)

    hotspot = next(c["corner_label"] for c in corners if c["temperature"] == max(temps))
    coldspot = next(c["corner_label"] for c in corners if c["temperature"] == min(temps))

    comfort = classify_comfort(avg_temp, avg_hum, delta_t)
    recent_alerts = get_recent_alerts(limit=5)

    return {
        "room_id": "Room:01",
        "room_name": "Sala Principal Dalet",
        "spatial_summary": {
            "avg_temperature": avg_temp,
            "avg_humidity": avg_hum,
            "avg_heat_index": avg_hi,
            "delta_t_spatial": delta_t,
            "hotspot": hotspot,
            "coldspot": coldspot,
            "comfort_status": comfort["status"],
            "comfort_color": comfort["color"],
            "comfort_reason": comfort["reason"]
        },
        "corners": corners,
        "recent_alerts": recent_alerts
    }

@app.get("/api/history")
def get_history(entity_id: str = None, limit: int = 50):
    """Retorna historial de lecturas para gráficas temporales."""
    return {"history": get_recent_history(entity_id=entity_id, limit=limit)}

@app.get("/api/alerts")
def get_alerts(limit: int = 20):
    """Retorna el registro de alertas generadas."""
    return {"alerts": get_recent_alerts(limit=limit)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("etl.main:app", host="0.0.0.0", port=8000, reload=True)
