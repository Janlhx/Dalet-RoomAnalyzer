# 🏛️ Dalet-RoomAnalyzer — Proyecto Final IoT & Arquitectura FIWARE

## 1. Información General y Alcance
* **Proyecto**: Dalet-RoomAnalyzer (Monitoreo Inteligente y Toma de Decisiones Ambientales para Salas).
* **Asignatura**: Proyecto Final de IoT (Sensórica + Pipeline ETL + Frontend de Toma de Decisiones + Asistente por Voz con IA).
* **Hito Inmediato (Próximo Jueves)**:
  1. Infraestructura base de FIWARE levantada con Docker Compose (en AWS EC2 o local).
  2. Aprovisionamiento y recepción de telemetría de sensores (físicos o simulados).
  3. Pipeline ETL recibiendo notificaciones de cambio de contexto y transformando datos en tiempo real.

---

## 2. Sensórica y Topología Espacial (4 Esquinas)
Para garantizar un análisis térmico y ambiental representativo de la sala y detectar estratificación de temperatura o corrientes de aire, se adopta una **distribución espacial en las 4 esquinas**:

| Nodo | ID Dispositivo | Entidad NGSI-v2 | Ubicación / Microclima |
| :--- | :--- | :--- | :--- |
| **Nodo NW** | `hdc1080_nw` | `Room:01:Corner:NW` | Esquina Noroeste (Ventana / Fachada solar) |
| **Nodo NE** | `hdc1080_ne` | `Room:01:Corner:NE` | Esquina Noreste (Puerta de acceso / Circulación) |
| **Nodo SW** | `hdc1080_sw` | `Room:01:Corner:SW` | Esquina Suroeste (Zona de Servidores / Carga térmica) |
| **Nodo SE** | `hdc1080_se` | `Room:01:Corner:SE` | Esquina Sureste (Zona Climatizada / Flujo de AC) |

* **Microcontrolador**: LilyGO (ESP32) o ESP8266 con conexión Wi-Fi en cada esquina.
* **Sensor Principal**: HDC1080 conectado por bus I2C (VCC, GND, SDA, SCL, dirección `0x40`) para medir:
  * Temperatura ambiente (°C).
  * Humedad relativa (%).
* **Variables Complementarias**:
  * Presencia (PIR / HC-SR501): Detección de ocupación humana en zonas específicas.
  * Coordenadas GPS de la sala: Latitud y Longitud para representación geográfica.

---

## 3. Arquitectura del Firmware en el Nodo (Dual: WebServer + FIWARE Client)
Cada microcontrolador implementa un diseño dual para satisfacer diagnósticos de borde (*Edge*) y el estándar europeo de nube (*Cloud*):

```text
       ┌─────────────────────────────────────────────────────────┐
       │         NODO SENSOR (LilyGO ESP32 / ESP8266)            │
       │                                                         │
       │  [ Sensor HDC1080 I2C ] ──► Lectura periódica (t, h)   │
       │                                                         │
       │  ROL 1: Servidor Web Local (Puerto 80 - Edge)           │
       │    • GET /      ──► Dashboard HTML en vivo con RSSI     │
       │    • GET /json  ──► Endpoint REST para diagnóstico      │
       │                                                         │
       │  ROL 2: Cliente HTTP Push (Hacia la Nube FIWARE)        │
       │    • POST :7896 ──► /iot/json?k=dalet_secret_key&i=...  │
       └─────────────────────────┬───────────────────────────────┘
                                 │ Wi-Fi (HTTP POST :7896)
                                 ▼
```

---

## 4. Arquitectura Global del Sistema (Estándar FIWARE)

```text
[ 4 Nodos de Esquina (NW, NE, SW, SE) ]
       │
       │ 1. Telemetría cruda (HTTP JSON :7896)
       ▼
[ FIWARE IOT AGENT JSON (:4041 / :7896) ]
  • Aprovisionamiento de Device & Service
  • Mapea {"t", "h", "presence", "lat", "lon"} a entidades NGSI-v2
       │
       │ 2. Actualiza contexto en tiempo real
       ▼
[ ORION CONTEXT BROKER (:1026) ]
  • Entidades vivas de cada esquina (Room:01:Corner:NW/NE/SW/SE)
  • Persistencia inmediata en MongoDB (:27017)
       │
       ├──► 3a. Suscripción a QUANTUMLEAP (:8668) ──► CRATEDB (:4200)
       │          • Persistencia canónica de Series Temporales (Time-Series)
       │          • Consola Web SQL en CrateDB (:4200)
       │
       └──► 3b. Suscripción a PIPELINE ETL (FastAPI :8000)
                  • EXTRACT: Recibe payload NGSI-v2 de Orion (/v1/notify)
                  • TRANSFORM:
                    - Sensación térmica / Heat Index (Fórmula Rothfusz/NOAA)
                    - Punto de Rocío (Dew Point - Magnus-Tetens)
                    - Gradiente térmico espacial (ΔT = Tmax - Tmin)
                    - Tasa de variación temporal (ΔT / Δt > 2°C en 5 min)
                    - Clasificación de confort y balance térmico
                  • LOAD: Guarda en DB analítica (SQLite WAL) y alimenta a Dalet AI
       │
       ├──► [ MOTOR TOMA DECISIONES ]
       │      • Reglas de balance térmico (alertas de ventana abierta, AC insuficiente)
       │      • Generación de alertas / actuadores
       │
       └──► [ DALET AI (VOZ & LLM) ]
              • STT (Voz a texto)
              • Consulta a Orion (tiempo real) y DB analítica (histórico/esquinas)
              • TTS (Edge-TTS Audio)
              │
              ▼
    [ DOBLE FRONTEND ]
    1. Frontend de Gestión (CRUD sensores, suscripciones, monitoreo de nodos)
    2. Frontend de Usuario (Mapa de calor 4 esquinas, semáforo de confort, widget de voz Dalet)
```

---

## 5. Pipeline ETL: Análisis Espacial y Temporal
* **Extract**: Endpoint `/v1/notify` en el worker Python que recibe notificaciones de cambio de estado desde Orion.
* **Transform**:
  * **Análisis Espacial**:
    - $\Delta T_{spatial} = T_{max} - T_{min}$ entre las 4 esquinas. Si $\Delta T > 3.0^\circ\text{C}$, alerta de desbalance térmico.
    - Identificación del *Hotspot* (esquina más caliente) y *Coldspot* (esquina más fría).
    - Temperatura y humedad promedio ponderada de la sala: $\overline{T}_{room}, \overline{H}_{room}$.
  * **Métricas Físicas**:
    - Sensación Térmica (Heat Index) con la fórmula de Rothfusz / NOAA.
    - Punto de Rocío (Dew Point) para prevención de condensación en equipos.
  * **Análisis Temporal**:
    - Tasa de cambio $\Delta T / \Delta t$ para detectar anomalías repentinas.
* **Load**: Inserción asíncrona en base de datos SQLite en modo WAL para acceso concurrente de frontends y Dalet.

---

## 6. Plan de Trabajo Inmediato (Sprint para el Jueves)
1. **Infraestructura FIWARE (AWS EC2 / Local)**:
   * Mongo 5.0 + Orion 3.11.0 + IoT Agent JSON 3.3.0 en Docker Compose.
2. **Aprovisionamiento Multi-Nodo**:
   * Script `scripts/provision.py` con registro de los 4 nodos de esquina.
3. **Simulador y Firmware de Hardware**:
   * Firmware ESP32 dual (WebServer + FIWARE) en `firmware/esp32_hdc1080_node/`.
   * Simulador multi-nodo en `scripts/simulator.py` con gradientes térmicos.
4. **Worker ETL**:
   * Servicio FastAPI con suscripción en Orion, cálculos de Rothfusz/Tetens y cálculo de gradientes espaciales.
