# 🏛️ Dalet-RoomAnalyzer

> Monitoreo Inteligente y Toma de Decisiones Ambientales para Salas basado en el estándar **FIWARE**, Sensórica IoT (LilyGO / ESP8266 + HDC1080), Pipeline ETL y Asistente por Voz con IA (**Dalet**).

---

## 🏗️ Arquitectura del Sistema

```text
[ LilyGO / ESP8266 + HDC1080 ]
       │
       │ 1. Telemetría cruda (HTTP JSON :7896)
       ▼
[ FIWARE IOT AGENT JSON (:4041 / :7896) ]
  • Aprovisionamiento de Device & Service
  • Mapea {"t", "h", "presence", "lat", "lon"} a NGSI-v2
       │
       │ 2. Actualiza contexto en tiempo real
       ▼
[ ORION CONTEXT BROKER (:1026) ]
  • Entidad viva de la Sala (id: Room:01, type: Room)
  • Persistencia inmediata en MongoDB (:27017)
       │
       │ 3. Notificación automática vía Suscripción (Webhook)
       ▼
[ PIPELINE ETL (Python) ]
  • EXTRACT: Recibe payload NGSI-v2 (/v1/notify)
  • TRANSFORM: Sensación Térmica (NOAA), Punto de Rocío, Tasa ΔT/Δt
  • LOAD: Guarda en DB analítica (SQLite WAL)
       │
       ├──► [ MOTOR DE TOMA DE DECISIONES ]
       └──► [ DALET AI (ASISTENTE POR VOZ) ]
```

---

## ☁️ Despliegue en AWS Academy (Recomendado para IoT Real)

Tener FIWARE en una instancia EC2 con IP pública permite que el hardware físico (LilyGO ESP32 / ESP8266) envíe telemetría por Wi-Fi sin lidiar con NAT, ngrok ni instalar Docker en Windows.

### 1. Configuración de la Instancia EC2 en AWS Academy
* **AMI**: Ubuntu Server 22.04 LTS (o 24.04 LTS).
* **Tipo de instancia**: `t3.small` o `t2.medium` (si usas `t2.micro`, el script creará 2GB de Swap para proteger a MongoDB).
* **Security Group (Reglas de Entrada / Inbound Rules)**:
  | Protocolo | Puerto | Origen (Source) | Descripción |
  | :--- | :--- | :--- | :--- |
  | SSH (TCP) | `22` | Tu IP o `0.0.0.0/0` | Conexión terminal |
  | Custom TCP | `7896` | `0.0.0.0/0` | IoT Agent Southbound (Sensores LilyGO / ESP32) |
  | Custom TCP | `1026` | `0.0.0.0/0` | FIWARE Orion Context Broker |
  | Custom TCP | `4041` | `0.0.0.0/0` | IoT Agent Northbound (Aprovisionamiento) |
  | Custom TCP | `8000` | `0.0.0.0/0` | Pipeline ETL Worker / API |
  | Custom TCP | `3000` | `0.0.0.0/0` | Frontend Web (Fase posterior) |

### 2. Puesta en Marcha Automatizada en EC2
Conéctate por SSH a tu instancia:
```bash
ssh -i "tu-llave.pem" ubuntu@<IP-PUBLICA-EC2>
```
Clona el repositorio y ejecuta el script automatizado:
```bash
git clone https://github.com/TU_USUARIO/Dalet-RoomAnalyzer.git
cd Dalet-RoomAnalyzer
chmod +x setup_ec2.sh
./setup_ec2.sh
```
El script instala Docker, configura 2GB de memoria Swap para evitar caídas de MongoDB y levanta la pila FIWARE.

---

## 🚀 Inicio Rápido y Pruebas (Local o Remoto)

### 1. Requisitos Previos (En tu máquina local)
* Python 3.10+ con dependencias instaladas:
  ```bash
  pip install -r requirements.txt
  ```

### 2. Levantar la Infraestructura FIWARE
En la raíz del proyecto, ejecuta:
```bash
docker compose up -d
```
Esto levantará los cinco contenedores del ecosistema FIWARE:
* `dalet-mongo` (`:27017`): MongoDB para persistencia de Orion e IoT Agent.
* `dalet-orion` (`:1026`): FIWARE Orion Context Broker.
* `dalet-iot-agent-json` (`:4041` gestión, `:7896` telemetría).
* `dalet-crate-db` (`:4200` Web Admin UI, `:5432` PostgreSQL protocol): Persistencia de series temporales.
* `dalet-quantumleap` (`:8668`): Traductor NGSI-v2 a CrateDB.

Verifica que estén saludables:
```bash
docker compose ps
```

### 3. Aprovisionar los 4 Nodos de Esquina
Aprovisiona en FIWARE IoT Agent los 4 nodos correspondientes a las esquinas de la sala:
```bash
# Si lo ejecutas desde tu máquina local hacia AWS EC2:
python scripts/provision.py --host <IP-PUBLICA-EC2>

# Si lo ejecutas dentro de la instancia EC2:
python scripts/provision.py
```
> Registra los 4 dispositivos: `hdc1080_nw`, `hdc1080_ne`, `hdc1080_sw`, `hdc1080_se` vinculados a sus respectivas entidades NGSI-v2 en Orion.

### 4. Simular Telemetría de las 4 Esquinas
Envía telemetría simulada con microclimas y gradientes térmicos diferenciados por esquina:
* **Envío continuo de las 4 esquinas (cada 4 segundos):**
  ```bash
  python scripts/simulator.py --host <IP-PUBLICA-EC2> --all-corners
  ```
* **Envío único de prueba:**
  ```bash
  python scripts/simulator.py --host <IP-PUBLICA-EC2> --once
  ```
* **Envío con inyección de sobrecalentamiento en esquina de servidores (SW):**
  ```bash
  python scripts/simulator.py --host <IP-PUBLICA-EC2> --count 5 --spike
  ```

### 5. Verificar Estado Espacial en Orion
Comprueba las 4 esquinas, el promedio global y el gradiente térmico ($\Delta T$) calculado en vivo:
```bash
python scripts/verify_orion.py --host <IP-PUBLICA-EC2>
```

### 6. Ejecutar el Pipeline ETL y Activar Suscripción
El Pipeline ETL recibe notificaciones automáticas de Orion ante cambios de contexto, calcula la Sensación Térmica (NOAA), Punto de Rocío (Magnus-Tetens) y persiste en SQLite WAL:

1. **Iniciar el Worker ETL (en la EC2):**
   ```bash
   python3 -m uvicorn etl.main:app --host 0.0.0.0 --port 8000
   ```
2. **Registrar la Suscripción Webhook en Orion (en otra terminal):**
   ```bash
   python3 scripts/subscribe_orion.py
   ```
3. **Consultar la API de Estado y Diagnóstico:**
   * En tu navegador: `http://<IP-PUBLICA-EC2>:8000/docs` (Swagger UI interactivo)
   * Estado consolidado de la sala: `http://<IP-PUBLICA-EC2>:8000/api/status`

---

## 🔌 Firmware del Hardware con PlatformIO

El código para los sensores LilyGO ESP32 / ESP8266 está organizado como proyecto estándar en [`firmware/`](file:///c:/Users/juans/Documents/Dalet-RoomAnalyzer/firmware/):
* [firmware/platformio.ini](file:///c:/Users/juans/Documents/Dalet-RoomAnalyzer/firmware/platformio.ini): Gestión automática de librerías (`ClosedCube HDC1080`, `ArduinoJson`) y entornos de compilación para cada esquina.
* [firmware/include/config.h](file:///c:/Users/juans/Documents/Dalet-RoomAnalyzer/firmware/include/config.h): Configuración centralizada de Wi-Fi y host FIWARE (AWS EC2).
* [firmware/src/main.cpp](file:///c:/Users/juans/Documents/Dalet-RoomAnalyzer/firmware/src/main.cpp): Lógica dual (WebServer local en puerto 80 + Cliente HTTP hacia FIWARE :7896).

### 🚀 Cómo Flashear cada Esquina con PlatformIO
Abre la carpeta `firmware/` en VS Code (con la extensión **PlatformIO IDE** instalada) o usa la CLI:

```bash
# 1. Flashear Esquina Noroeste (Ventana):
pio run -e node_nw -t upload

# 2. Flashear Esquina Noreste (Puerta):
pio run -e node_ne -t upload

# 3. Flashear Esquina Suroeste (Servidores):
pio run -e node_sw -t upload

# 4. Flashear Esquina Sureste (Climatizador AC):
pio run -e node_se -t upload
```
> [!TIP]
> ¡No necesitas modificar el código C++ para cada sensor! PlatformIO inyecta automáticamente los nombres, esquinas y variables mediante los `build_flags` de cada entorno.

---

## 📁 Estructura del Repositorio

* [ARCHITECTURE.md](file:///c:/Users/juans/Documents/Dalet-RoomAnalyzer/ARCHITECTURE.md): Documento de especificación arquitectónica detallada (Topología 4 esquinas + FIWARE).
* [docker-compose.yml](file:///c:/Users/juans/Documents/Dalet-RoomAnalyzer/docker-compose.yml): Orquestación de MongoDB, Orion Context Broker y IoT Agent JSON.
* [setup_ec2.sh](file:///c:/Users/juans/Documents/Dalet-RoomAnalyzer/setup_ec2.sh): Script de despliegue automático en instancias Ubuntu EC2 (Swap + Docker + Compose).
* [firmware/](file:///c:/Users/juans/Documents/Dalet-RoomAnalyzer/firmware/): Proyecto PlatformIO para sensores ESP32/ESP8266 con WebServer y cliente FIWARE.
* [scripts/provision.py](file:///c:/Users/juans/Documents/Dalet-RoomAnalyzer/scripts/provision.py): Aprovisionamiento de los 4 sensores en IoT Agent.
* [scripts/simulator.py](file:///c:/Users/juans/Documents/Dalet-RoomAnalyzer/scripts/simulator.py): Simulador multi-nodo con gradiente térmico espacial.
* [scripts/verify_orion.py](file:///c:/Users/juans/Documents/Dalet-RoomAnalyzer/scripts/verify_orion.py): Inspector espacial de las 4 esquinas y gradiente $\Delta T$ en Orion.