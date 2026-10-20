#!/usr/bin/env python3
"""
alerts/app.py
Servidor Ligero en Flask para Toma de Decisiones y Gestión de Alertas Reactivas (Escenario #2).
Recibe notificaciones webhook de Orion Context Broker filtradas por condiciones (ej. t > x °C).
"""

import os
import json
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)

# Memoria volátil de eventos y estado del recinto
ALERTS_HISTORY = []
MAX_HISTORY = 100
CURRENT_THRESHOLD = float(os.getenv("ALERT_TEMP_THRESHOLD", "26.0"))

# Recomendaciones de toma de decisiones según la esquina afectada
DECISION_ACTIONS = {
    "Room:01:Corner:NW": "Ventana / Fachada: Abrir celosías o activar extractor para reducir radiación solar incidente.",
    "Room:01:Corner:NE": "Puerta de Acceso: Verificar cierre hermético para evitar ingreso de aire cálido exterior.",
    "Room:01:Corner:SW": "Zona de Servidores: ¡CRÍTICO! Aumentar velocidad de ventiladores de rack o redistribuir carga de cómputo.",
    "Room:01:Corner:SE": "Zona Climatizada: Reducir consigna de termostato del sistema de aire acondicionado (HVAC)."
}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Dalet Room Analyzer — Monitor de Alertas Reactivas</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <meta http-equiv="refresh" content="5">
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen p-6 font-sans">
  <div class="max-w-5xl mx-auto space-y-6">
    
    <!-- Encabezado -->
    <header class="flex justify-between items-center border-b border-slate-800 pb-4">
      <div>
        <h1 class="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
          🏛️ Dalet-RoomAnalyzer <span class="text-xs bg-amber-500/20 text-amber-300 border border-amber-500/30 px-2 py-0.5 rounded-full font-mono">Escenario #2: Orion Alertas</span>
        </h1>
        <p class="text-sm text-slate-400 mt-1">
          Motor de Alertas Reactivas y Toma de Decisiones activado por Suscripción Condicional en Orion
        </p>
      </div>
      <div class="text-right">
        <span class="text-xs font-mono px-3 py-1 bg-emerald-950 text-emerald-400 border border-emerald-800 rounded-full animate-pulse">
          ● Servicio Flask Activo (:5000)
        </span>
      </div>
    </header>

    <!-- Tarjetas de Métricas -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
      <div class="bg-slate-900 border border-slate-800 rounded-xl p-4">
        <div class="text-xs font-medium text-slate-400 uppercase tracking-wider">Regla de Disparo en Orion</div>
        <div class="text-2xl font-bold text-amber-400 mt-2 font-mono">t > {{ threshold }} °C</div>
        <div class="text-xs text-slate-500 mt-1">Expresión NGSI-v2: q="temperature>{{ threshold }}"</div>
      </div>

      <div class="bg-slate-900 border border-slate-800 rounded-xl p-4">
        <div class="text-xs font-medium text-slate-400 uppercase tracking-wider">Total Alertas Recibidas</div>
        <div class="text-2xl font-bold text-rose-400 mt-2 font-mono">{{ alerts|length }}</div>
        <div class="text-xs text-slate-500 mt-1">Eventos donde Orion decidió notificar</div>
      </div>

      <div class="bg-slate-900 border border-slate-800 rounded-xl p-4">
        <div class="text-xs font-medium text-slate-400 uppercase tracking-wider">Último Estado</div>
        {% if alerts %}
          <div class="text-lg font-bold text-rose-300 mt-2 truncate">{{ alerts[0].corner }}</div>
          <div class="text-xs text-rose-400 mt-1 font-mono">{{ alerts[0].temp }} °C ({{ alerts[0].timestamp }})</div>
        {% else %}
          <div class="text-lg font-bold text-emerald-400 mt-2">Sin Alertas Activas</div>
          <div class="text-xs text-slate-500 mt-1">Temperatura bajo control (&le; {{ threshold }} °C)</div>
        {% endif %}
      </div>
    </div>

    <!-- Tabla de Alertas y Decisiones -->
    <div class="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-lg">
      <div class="px-6 py-4 border-b border-slate-800 flex justify-between items-center">
        <h2 class="text-lg font-semibold text-white">Registro de Eventos y Decisiones Automáticas</h2>
        <span class="text-xs text-slate-400">Auto-refresco cada 5s</span>
      </div>
      
      {% if alerts %}
      <div class="overflow-x-auto">
        <table class="w-full text-left text-sm">
          <thead class="bg-slate-950 text-slate-400 text-xs uppercase tracking-wider font-mono">
            <tr>
              <th class="px-6 py-3">Hora</th>
              <th class="px-6 py-3">Esquina / Nodo</th>
              <th class="px-6 py-3">Temperatura</th>
              <th class="px-6 py-3">Humedad</th>
              <th class="px-6 py-3">Severidad</th>
              <th class="px-6 py-3">Toma de Decisión (Acción Recomendada)</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-800 font-mono text-xs">
            {% for a in alerts %}
            <tr class="hover:bg-slate-800/50 transition">
              <td class="px-6 py-3 text-slate-400 whitespace-nowrap">{{ a.timestamp }}</td>
              <td class="px-6 py-3 font-semibold text-white">{{ a.corner }}</td>
              <td class="px-6 py-3 text-amber-300 font-bold">{{ a.temp }} °C</td>
              <td class="px-6 py-3 text-cyan-300">{{ a.hum }} %</td>
              <td class="px-6 py-3">
                {% if a.temp >= 28.0 %}
                  <span class="px-2 py-0.5 rounded bg-rose-950 text-rose-300 border border-rose-800 font-sans font-medium text-[11px]">CRÍTICA</span>
                {% else %}
                  <span class="px-2 py-0.5 rounded bg-amber-950 text-amber-300 border border-amber-800 font-sans font-medium text-[11px]">ADVERTENCIA</span>
                {% endif %}
              </td>
              <td class="px-6 py-3 font-sans text-xs text-slate-200">{{ a.decision }}</td>
            </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
      {% else %}
      <div class="p-12 text-center text-slate-500 font-sans">
        <div class="text-4xl mb-2">🌿</div>
        <p class="font-medium text-slate-400">No hay alertas reactivas en este momento.</p>
        <p class="text-xs text-slate-600 mt-1">Orion evalúa cada lectura. Solo notificará a este servidor si alguna esquina supera los {{ threshold }} °C.</p>
      </div>
      {% endif %}
    </div>

    <!-- Pie técnico -->
    <footer class="text-xs text-slate-600 flex justify-between items-center font-mono">
      <span>FIWARE Orion Context Broker ➔ Flask Notification Webhook</span>
      <span>Dalet-RoomAnalyzer IoT</span>
    </footer>

  </div>
</body>
</html>
"""

@app.route("/", methods=["GET"])
def index():
    """Panel visual en HTML con auto-refresco."""
    return render_template_string(HTML_TEMPLATE, alerts=ALERTS_HISTORY, threshold=CURRENT_THRESHOLD)

@app.route("/alerta", methods=["POST"])
def recibir_alerta():
    """
    Webhook receptor de la Suscripción Reactiva de Orion.
    Orion dispara este endpoint cuando se cumple la condición: t > X °C.
    """
    payload = request.get_json(silent=True) or {}
    data = payload.get("data", [])

    if not data:
        return jsonify({"status": "ignored", "reason": "payload sin entidades"}), 200

    new_events = []
    now_str = datetime.now().strftime("%H:%M:%S")

    for entity in data:
        entity_id = entity.get("id", "Desconocido")
        
        # Extracción segura de atributos NGSI-v2
        t_obj = entity.get("temperature", {})
        temp = t_obj.get("value") if isinstance(t_obj, dict) else t_obj

        h_obj = entity.get("relativeHumidity", {})
        hum = h_obj.get("value") if isinstance(h_obj, dict) else h_obj

        try:
            temp_val = float(temp)
        except (ValueError, TypeError):
            temp_val = 0.0

        try:
            hum_val = float(hum)
        except (ValueError, TypeError):
            hum_val = 0.0

        # Toma de decisión basada en la esquina y severidad
        decision_text = DECISION_ACTIONS.get(
            entity_id, 
            "Evaluar flujo de aire y activar ventilación general de la sala."
        )

        event = {
            "timestamp": now_str,
            "corner": entity_id,
            "temp": temp_val,
            "hum": hum_val,
            "decision": decision_text
        }

        ALERTS_HISTORY.insert(0, event)
        if len(ALERTS_HISTORY) > MAX_HISTORY:
            ALERTS_HISTORY.pop()

        new_events.append(event)
        print(f"🚨 [ALERTA ORION t > {CURRENT_THRESHOLD}°C] Esquina: {entity_id} | T: {temp_val}°C | Acción: {decision_text}")

    return jsonify({
        "status": "success",
        "processed_events": len(new_events),
        "message": "Alerta reactiva procesada exitosamente"
    }), 200

@app.route("/api/alertas", methods=["GET"])
def get_alertas():
    """API REST JSON con las alertas registradas."""
    return jsonify({
        "threshold": CURRENT_THRESHOLD,
        "total": len(ALERTS_HISTORY),
        "alerts": ALERTS_HISTORY
    })

@app.route("/api/limpiar", methods=["POST"])
def limpiar():
    """Limpia el historial de alertas."""
    global ALERTS_HISTORY
    ALERTS_HISTORY = []
    return jsonify({"status": "cleared"}), 200

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print(f"🚀 Servidor de Alertas Reactivas Flask corriendo en http://0.0.0.0:{port}")
    print(f"🎯 Umbral reactivo de disparo: t > {CURRENT_THRESHOLD} °C")
    app.run(host="0.0.0.0", port=port, debug=False)
