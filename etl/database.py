"""
etl/database.py
Capa de persistencia analítica con SQLite en modo WAL (Write-Ahead Logging).
Proporciona alta concurrencia (múltiples lectores simultáneos: Frontend, Dalet AI)
con un único escritor determinista (Worker ETL).
"""

import os
import sqlite3
from datetime import datetime
from typing import List, Dict, Any, Optional

DB_PATH = os.getenv("DALET_DB_PATH", "data/dalet_analytics.db")

def get_connection() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH) if os.path.dirname(DB_PATH) else ".", exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # Activar modo WAL y optimizaciones de rendimiento
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    return conn

def init_db():
    conn = get_connection()
    with conn:
        # 1. Tabla de lecturas crudas y transformadas por esquina
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sensor_readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_id TEXT NOT NULL,
                corner_code TEXT,
                corner_label TEXT,
                temperature REAL NOT NULL,
                humidity REAL NOT NULL,
                heat_index REAL NOT NULL,
                dew_point REAL NOT NULL,
                presence INTEGER DEFAULT 0,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_readings_entity_ts ON sensor_readings(entity_id, timestamp);")

        # 2. Tabla de fotos espaciales consolidadas de la sala
        conn.execute("""
            CREATE TABLE IF NOT EXISTS room_spatial_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_id TEXT NOT NULL,
                avg_temperature REAL NOT NULL,
                avg_humidity REAL NOT NULL,
                avg_heat_index REAL NOT NULL,
                delta_t_spatial REAL NOT NULL,
                hotspot_corner TEXT,
                coldspot_corner TEXT,
                comfort_status TEXT NOT NULL,
                comfort_reason TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_room_ts ON room_spatial_snapshots(room_id, timestamp);")

        # 3. Registro de alertas generadas
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alerts_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_id TEXT NOT NULL,
                alert_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                message TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_alerts_ts ON alerts_log(timestamp);")
    conn.close()

def insert_reading(entity_id: str, corner_code: str, corner_label: str,
                   temp: float, hum: float, heat_index: float, dew_point: float,
                   presence: int) -> int:
    conn = get_connection()
    with conn:
        cursor = conn.execute("""
            INSERT INTO sensor_readings 
            (entity_id, corner_code, corner_label, temperature, humidity, heat_index, dew_point, presence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (entity_id, corner_code, corner_label, temp, hum, heat_index, dew_point, presence))
        row_id = cursor.lastrowid
    conn.close()
    return row_id

def insert_spatial_snapshot(room_id: str, avg_temp: float, avg_hum: float,
                            avg_hi: float, delta_t: float, hotspot: str,
                            coldspot: str, comfort_status: str, comfort_reason: str) -> int:
    conn = get_connection()
    with conn:
        cursor = conn.execute("""
            INSERT INTO room_spatial_snapshots
            (room_id, avg_temperature, avg_humidity, avg_heat_index, delta_t_spatial,
             hotspot_corner, coldspot_corner, comfort_status, comfort_reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (room_id, avg_temp, avg_hum, avg_hi, delta_t, hotspot, coldspot, comfort_status, comfort_reason))
        row_id = cursor.lastrowid
    conn.close()
    return row_id

def insert_alert(entity_id: str, alert_type: str, severity: str, message: str) -> int:
    conn = get_connection()
    with conn:
        cursor = conn.execute("""
            INSERT INTO alerts_log (entity_id, alert_type, severity, message)
            VALUES (?, ?, ?, ?)
        """, (entity_id, alert_type, severity, message))
        row_id = cursor.lastrowid
    conn.close()
    return row_id

def get_latest_readings_by_entity() -> List[Dict[str, Any]]:
    """Devuelve la lectura más reciente de cada esquina registrada."""
    conn = get_connection()
    query = """
        SELECT r1.*
        FROM sensor_readings r1
        INNER JOIN (
            SELECT entity_id, MAX(id) as max_id
            FROM sensor_readings
            GROUP BY entity_id
        ) r2 ON r1.id = r2.max_id
        ORDER BY r1.entity_id ASC;
    """
    rows = conn.execute(query).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_recent_history(entity_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """Devuelve las últimas lecturas para gráficas y frontend."""
    conn = get_connection()
    if entity_id:
        query = "SELECT * FROM sensor_readings WHERE entity_id = ? ORDER BY timestamp DESC LIMIT ?;"
        rows = conn.execute(query, (entity_id, limit)).fetchall()
    else:
        query = "SELECT * FROM sensor_readings ORDER BY timestamp DESC LIMIT ?;"
        rows = conn.execute(query, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_recent_alerts(limit: int = 20) -> List[Dict[str, Any]]:
    conn = get_connection()
    query = "SELECT * FROM alerts_log ORDER BY timestamp DESC LIMIT ?;"
    rows = conn.execute(query, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_recent_readings_for_rate_of_change(entity_id: str, minutes: int = 5) -> List[float]:
    """Obtiene las lecturas de los últimos X minutos para evaluar tasa de cambio térmico."""
    conn = get_connection()
    query = """
        SELECT temperature FROM sensor_readings
        WHERE entity_id = ? AND timestamp >= datetime('now', ?)
        ORDER BY timestamp ASC;
    """
    rows = conn.execute(query, (entity_id, f"-{minutes} minutes")).fetchall()
    conn.close()
    return [r["temperature"] for r in rows]
