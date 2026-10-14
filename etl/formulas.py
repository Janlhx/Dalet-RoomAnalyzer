"""
etl/formulas.py
Funciones matemáticas y físicas del Pipeline ETL:
1. Sensación Térmica (Heat Index) con la fórmula oficial de Rothfusz (NOAA/NWS).
2. Punto de Rocío (Dew Point) con la aproximación de Magnus-Tetens.
3. Evaluación de Riesgo de Condensación.
4. Clasificación de Confort Ambiental.
"""

import math

def calculate_dew_point(temperature_c: float, humidity_pct: float) -> float:
    """
    Calcula el punto de rocío en °C usando la fórmula de Magnus-Tetens.
    Válido para temperaturas entre -40°C y 60°C.
    """
    if humidity_pct <= 0:
        return temperature_c
    
    # Constantes de Magnus para vapor de agua
    a = 17.27
    b = 237.7
    
    alpha = ((a * temperature_c) / (b + temperature_c)) + math.log(humidity_pct / 100.0)
    dew_point = (b * alpha) / (a - alpha)
    return round(dew_point, 2)

def calculate_heat_index(temperature_c: float, humidity_pct: float) -> float:
    """
    Calcula la sensación térmica (Heat Index) en °C usando la ecuación de regresión
    de Rothfusz del National Weather Service / NOAA de Estados Unidos.
    """
    # Si la temperatura es menor a 20°C, la sensación térmica coincide con la temperatura ambiente
    if temperature_c < 20.0:
        return round(temperature_c, 2)
        
    # Convertir a Fahrenheit para aplicar la fórmula estándar de la NOAA
    t_f = temperature_c * 1.8 + 32.0
    rh = max(0.0, min(100.0, humidity_pct))

    # Ecuación simple preliminar de Steadman
    hi_simple = 0.5 * (t_f + 61.0 + ((t_f - 68.0) * 1.2) + (rh * 0.094))
    
    if hi_simple < 80.0:
        hi_f = hi_simple
    else:
        # Polinomio completo de regresión de Rothfusz
        hi_f = (
            -42.379
            + (2.04901523 * t_f)
            + (10.14333127 * rh)
            - (0.22475541 * t_f * rh)
            - (0.00683783 * (t_f ** 2))
            - (0.05481717 * (rh ** 2))
            + (0.00122874 * (t_f ** 2) * rh)
            + (0.00085282 * t_f * (rh ** 2))
            - (0.00000199 * (t_f ** 2) * (rh ** 2))
        )
        
        # Ajustes de la NOAA para humedades extremas
        if rh < 13.0 and 80.0 <= t_f <= 112.0:
            adj = ((13.0 - rh) / 4.0) * math.sqrt((17.0 - abs(t_f - 95.0)) / 17.0)
            hi_f -= adj
        elif rh > 85.0 and 80.0 <= t_f <= 87.0:
            adj = ((rh - 85.0) / 10.0) * ((87.0 - t_f) / 5.0)
            hi_f += adj

    # Convertir de vuelta a Celsius
    hi_c = (hi_f - 32.0) / 1.8
    return round(hi_c, 2)

def assess_condensation_risk(temperature_c: float, dew_point_c: float) -> dict:
    """
    Evalúa el margen de seguridad para evitar condensación de agua en hardware/electrónica.
    Margen = Temperatura - Punto de Rocío.
    """
    margin = round(temperature_c - dew_point_c, 2)
    if margin <= 2.0:
        return {
            "level": "CRITICAL",
            "margin_c": margin,
            "message": "¡PELIGRO DE CONDENSACIÓN! La temperatura está a menos de 2°C del punto de rocío."
        }
    elif margin <= 4.0:
        return {
            "level": "WARNING",
            "margin_c": margin,
            "message": "Margen de condensación bajo (humedad muy alta en sala)."
        }
    else:
        return {
            "level": "SAFE",
            "margin_c": margin,
            "message": "Seguro: sin riesgo de condensación."
        }

def classify_comfort(temp_c: float, hum_pct: float, delta_t_spatial: float = 0.0) -> dict:
    """
    Clasifica el confort ambiental de la sala en:
    - OPTIMAL (Verde): 20°C - 25°C, 40% - 60% humedad, balance térmico homogéneo.
    - WARNING (Amarillo): Temperatura o humedad moderadamente desviada, o gradiente térmico > 2.5°C.
    - CRITICAL (Rojo): Temperatura extrema (>29°C o <17°C) o gradiente térmico severo (>4.0°C).
    """
    reasons = []

    if delta_t_spatial > 4.0:
        return {
            "status": "CRITICAL",
            "color": "red",
            "reason": f"Desbalance térmico severo entre esquinas (ΔT = {delta_t_spatial:.1f}°C)."
        }

    if temp_c > 29.0:
        reasons.append("Temperatura excesivamente alta.")
    elif temp_c < 17.0:
        reasons.append("Temperatura excesivamente baja.")

    if hum_pct > 75.0:
        reasons.append("Humedad sofocante (>75%).")
    elif hum_pct < 30.0:
        reasons.append("Aire excesivamente seco (<30%).")

    if reasons:
        return {
            "status": "CRITICAL",
            "color": "red",
            "reason": " • ".join(reasons)
        }

    # Evaluación de advertencias (Warning)
    warning_reasons = []
    if delta_t_spatial >= 2.5:
        warning_reasons.append(f"Gradiente térmico notable (ΔT = {delta_t_spatial:.1f}°C)")
    if 25.0 < temp_c <= 29.0:
        warning_reasons.append("Sensación ligeramente cálida")
    elif 17.0 <= temp_c < 20.0:
        warning_reasons.append("Sensación ligeramente fresca")
    if 65.0 < hum_pct <= 75.0:
        warning_reasons.append("Humedad elevada")

    if warning_reasons:
        return {
            "status": "WARNING",
            "color": "yellow",
            "reason": " • ".join(warning_reasons)
        }

    return {
        "status": "OPTIMAL",
        "color": "green",
        "reason": "Condiciones ambientales óptimas para personas y equipos."
    }
