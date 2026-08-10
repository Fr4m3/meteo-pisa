#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Genera le previsioni per Pisa con il modello attualmente vincente (dalla
verifica) e scrive forecast.json (istanza attuale + 7 giorni + dettagli orari).

Ottimizzazioni dalle prove:
  - modello dinamico: si usa il vincitore di verifica_modelli.json (fallback ECMWF);
  - bias-correzione: se esiste calibrazione.json si applicano gli offset misurati
    (temperatura additiva, pioggia moltiplicativa, vento/umidità additivi) in modo
    prudente (frazioni di sicurezza), così le previsioni mostrate risultano più
    vicine alle osservazioni reali rispetto al modello grezzo.
"""
import json
import urllib.request
import urllib.parse
from datetime import datetime, timedelta

LAT, LON = 43.7228, 10.4017
DEFAULT_MODEL = "ecmwf_ifs025"          # fallback se non c'è una verifica
FORECAST_DAYS = 7

WMO = {
    0: ("Sereno", "☀️"), 1: ("Prevalentemente sereno", "🌤️"), 2: ("Parzialmente nuvoloso", "⛅"),
    3: ("Coperto", "☁️"), 45: ("Nebbia", "🌫️"), 48: ("Nebbia con ghiaccio", "🌫️"),
    51: ("Pioviggine leggera", "🌦️"), 53: ("Pioviggine", "🌦️"), 55: ("Pioviggine intensa", "🌧️"),
    56: ("Pioviggine gelata", "🌧️"), 57: ("Pioviggine gelata intensa", "🌧️"),
    61: ("Pioggia debole", "🌦️"), 63: ("Pioggia", "🌧️"), 65: ("Pioggia forte", "🌧️"),
    66: ("Pioggia gelata", "🌧️"), 67: ("Pioggia gelata forte", "🌧️"),
    71: ("Neve debole", "🌨️"), 73: ("Neve", "🌨️"), 75: ("Neve abbondante", "❄️"),
    77: ("Granelli di neve", "🌨️"), 80: ("Rovesci deboli", "🌦️"), 81: ("Rovesci", "🌧️"),
    82: ("Rovesci violenti", "⛈️"), 85: ("Rovesci di neve", "🌨️"), 86: ("Rovesci di neve forti", "❄️"),
    95: ("Temporale", "⛈️"), 96: ("Temporale con grandine", "⛈️"), 99: ("Temporale con grandine forte", "⛈️"),
}

MODEL_LABEL = {
    "ecmwf_ifs025": "ECMWF IFS 0.25° (HRES)",
    "icon_seamless": "DWD ICON (seamless)",
    "best_match": "Best-match composito (ICON)",
}

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "pisa-meteo/1.0"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.load(r)

def load_winner():
    """Vincitore dall'ultima verifica; None se assente."""
    try:
        vf = json.load(open("verifica_modelli.json"))
        return vf.get("winner") or DEFAULT_MODEL
    except (FileNotFoundError, json.JSONDecodeError):
        return DEFAULT_MODEL

def load_calibration():
    """Coefficienti di bias-correzione; None se assenti."""
    try:
        return json.load(open("calibrazione.json"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None

def apply_cal(data, cal):
    """
    Applica la bias-correzione sui dati scaricati (in-place su liste hourly/daily
    e sul current). Le voci mancanti restano None.
    """
    if not cal:
        return
    t_off = cal.get("temp_offset") or 0.0
    w_off = cal.get("wind_offset") or 0.0
    h_off = cal.get("humidity_offset") or 0.0
    r_p = cal.get("precip_ratio") or 1.0

    def adj(arr, dx, lo=None, hi=None):
        out = []
        for v in arr:
            if v is None:
                out.append(None)
                continue
            v2 = v + dx
            if lo is not None:
                v2 = max(lo, v2)
            if hi is not None:
                v2 = min(hi, v2)
            out.append(round(v2, 2))
        return out

    def mul(arr, f):
        out = []
        for v in arr:
            if v is None:
                out.append(None)
                continue
            v2 = v * f
            # evita mm "sporchi" tipo 0.004
            out.append(round(v2, 3) if v2 >= 0.05 else 0.0)
        return out

    hourly = data.get("hourly") or {}
    daily = data.get("daily") or {}
    cur = data.get("current") or {}

    for k in ("temperature_2m", "apparent_temperature", "dew_point_2m"):
        if k in hourly:
            hourly[k] = adj(hourly[k], t_off)
        if k in daily:
            daily[k] = adj(daily[k], t_off)
    for k in ("temperature_2m_max", "temperature_2m_min",
              "apparent_temperature_max", "apparent_temperature_min"):
        if k in daily:
            daily[k] = adj(daily[k], t_off)
    if "wind_speed_10m" in hourly:
        hourly["wind_speed_10m"] = adj(hourly["wind_speed_10m"], w_off, lo=0)
    if "wind_gusts_10m" in hourly:
        hourly["wind_gusts_10m"] = adj(hourly["wind_gusts_10m"], w_off * 1.2, lo=0)
    if "wind_speed_10m_max" in daily:
        daily["wind_speed_10m_max"] = adj(daily["wind_speed_10m_max"], w_off, lo=0)
    if "wind_gusts_10m_max" in daily:
        daily["wind_gusts_10m_max"] = adj(daily["wind_gusts_10m_max"], w_off * 1.2, lo=0)
    if "relative_humidity_2m" in hourly:
        hourly["relative_humidity_2m"] = adj(hourly["relative_humidity_2m"], h_off, lo=0, hi=100)
    if "precipitation" in hourly:
        hourly["precipitation"] = mul(hourly["precipitation"], r_p)
    if "precipitation_sum" in daily:
        daily["precipitation_sum"] = mul(daily["precipitation_sum"], r_p)

    # current
    if "temperature_2m" in cur:
        cur["temperature_2m"] = round(cur["temperature_2m"] + t_off, 1)
    if "apparent_temperature" in cur:
        cur["apparent_temperature"] = round(cur["apparent_temperature"] + t_off, 1)
    if "dew_point_2m" in cur:
        cur["dew_point_2m"] = round(cur["dew_point_2m"] + t_off, 1)
    if "wind_speed_10m" in cur:
        cur["wind_speed_10m"] = round(max(0, cur["wind_speed_10m"] + w_off), 1)
    if "wind_gusts_10m" in cur:
        cur["wind_gusts_10m"] = round(max(0, cur["wind_gusts_10m"] + w_off * 1.2), 1)
    if "relative_humidity_2m" in cur:
        cur["relative_humidity_2m"] = round(min(100, max(0, cur["relative_humidity_2m"] + h_off)), 0)

def main():
    model = load_winner()
    cal = load_calibration()

    q = urllib.parse.urlencode({
        "latitude": LAT, "longitude": LON,
        "forecast_days": FORECAST_DAYS,
        "current": "temperature_2m,apparent_temperature,relative_humidity_2m,is_day,"
                   "precipitation,weather_code,wind_speed_10m,wind_direction_10m,"
                   "surface_pressure,cloud_cover,uv_index,dew_point_2m,wind_gusts_10m,"
                   "visibility,cloud_cover_low,cloud_cover_mid,cloud_cover_high",
        "hourly": "temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,"
                  "precipitation_probability,weather_code,wind_speed_10m,wind_gusts_10m,"
                  "wind_direction_10m,surface_pressure,cloud_cover,visibility,uv_index,"
                  "dew_point_2m,cloud_cover_low,cloud_cover_mid,cloud_cover_high",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,"
                 "precipitation_probability_max,wind_speed_10m_max,wind_gusts_10m_max,"
                 "sunrise,sunset,uv_index_max,daylight_duration,sunshine_duration,"
                 "precipitation_hours,moonrise,moonset,moon_phase,"
                 "apparent_temperature_max,apparent_temperature_min",
        "models": model,
        "timezone": "Europe/Rome",
    })
    url = f"https://api.open-meteo.com/v1/forecast?{q}"
    print(f"Scarico previsioni ({model}) ...")
    d = get(url)

    if cal:
        print("Applico bias-correzione da calibrazione.json ...")
        apply_cal(d, cal)

    now = datetime.now()
    out = {
        "generated_at": now.strftime("%Y-%m-%d %H:%M"),
        "model": model,
        "model_label": MODEL_LABEL.get(model, model),
        "bias_corr": {
            "applicato": bool(cal),
            "dettagli": cal,
        } if cal else {"applicato": False},
        "location": {"name": "Pisa", "lat": d.get("latitude"), "lon": d.get("longitude"),
                     "elevation": d.get("elevation")},
        "current": d.get("current"),
        "hourly": d.get("hourly"),
        "daily": d.get("daily"),
        "wmo": WMO,
    }
    with open("forecast.json", "w") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print("Scritto forecast.json")
    print(f"  Ora: {out['current']['time']}  T={out['current']['temperature_2m']}°C  "
          f"codice={out['current']['weather_code']}")
    print(f"  Giorni: {len(out['daily']['time'])}")
    print(f"  Modello: {out['model_label']}  ·  bias-corr={'SÌ' if cal else 'no'}")

if __name__ == "__main__":
    main()