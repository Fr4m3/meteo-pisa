#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Calibrazione del modello vincitore dalle ultime prove (verifica_modelli.json).

Misura gli errori sistematici (bias) del modello che ha vinto l'ultima verifica
e li converte in coefficienti PRUDENTI applicabili alle previsioni future:

  - temp_offset  : correzione additiva T (°C) = fattore * (-bias)   [bias>0 → prevede caldo...]
                   Se il modello prevede in media T_fc = T_obs + bias, per cancellare
                   il bias va applicato -bias. Usiamo una frazione di sicurezza:
                   le condizioni stagionali cambiano, correggere il 100% rischia di
                   aggiungere rumore quando il bias si inverte.
  - precip_ratio : fattore moltiplicativo sulla pioggia oraria/giornaliera.
                   = ratio_osservato/previsto attenuato verso 1.0 (prudenza)
  - vento_offset / umid_offset: correzioni per vento e umidità (solo se consistenti).

Regola anti-rumore: si applica la correzione solo se il bias è statisticamente
rilevante (soglia minima) e il campione è sufficiente (>= 200 ore confrontate).

Output: calibrazione.json  (usato da fetch_forecast.py e mostrato in pagina)
"""
import json

NAME = {
    "ecmwf_ifs025": "ECMWF IFS 0.25° (HRES)",
    "icon_seamless": "DWD ICON (seamless)",
    "best_match": "Best-match (ICON)",
}

# frazioni di sicurezza: NON correggiamo mai il 100% del bias misurato
ALPHA_TEMP = 0.70     # 70% del bias di temperatura
ALPHA_PRECIP = 0.50   # 50% della sovra/sottostima di pioggia
ALPHA_OTHER = 0.50    # 50% per vento/umidità

MIN_BIAS_TEMP = 0.20      # °C: sotto questa soglia non si tocca T
MIN_BIAS_OTHER = 0.05     # unità (m/s, %)
MIN_HOURS = 200           # ore confrontate minime
MIN_PRECIP_TOT = 5.0      # mm totali osservati minimi per calibrare la pioggia
MIN_PRECIP_DAYS = 3       # giorni di pioggia minimi

def clip(x, lo, hi):
    return max(lo, min(hi, x))

def main():
    vf = json.load(open("verifica_modelli.json"))
    winner = vf["winner"]
    res = vf["results"].get(winner)
    if not res:
        print(f"Nessun risultato per il vincitore {winner}, niente da calibrare.")
        return

    s = res["var_stats"]
    hours = res.get("temp_n", 0)
    temp = s.get("temperature_2m", {})
    wind = s.get("wind_speed_10m", {})
    hum = s.get("relative_humidity_2m", {})
    prec = s.get("precip_daily", {})

    cal = {
        "generated_at": __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M"),
        "basato_su": {  # trasparenza: su quali prove si basa
            "window": vf["window"],
            "window_days": vf["window_days"],
            "ore_confrontate": hours,
            "giorni_pioggia_osservati": prec.get("giorni_pioggia"),
        },
        "vincitore": winner,
        "vincitore_label": NAME.get(winner, winner),
    }

    # --- temperatura (offset additivo) ---
    t_bias = temp.get("bias")   # media(fc - obs): positivo = prevede più caldo del reale
    t_off = 0.0
    if hours >= MIN_HOURS and t_bias is not None and abs(t_bias) >= MIN_BIAS_TEMP:
        t_off = round(-t_bias * ALPHA_TEMP, 2)
    cal["temp_offset"] = t_off
    cal["temp_bias_misurato"] = round(t_bias, 3) if t_bias is not None else None

    # --- pioggia (fattore moltiplicativo) ---
    tot_obs = prec.get("tot_obs_mm") or 0
    tot_fc = prec.get("tot_fc_mm") or 0
    days_rain = prec.get("giorni_pioggia") or 0
    ratio = 1.0
    if (hours >= MIN_HOURS and tot_obs >= MIN_PRECIP_TOT and days_rain >= MIN_PRECIP_DAYS
            and tot_fc > 0.5):
        raw = tot_obs / tot_fc
        # attenua verso 1.0 del 50% e limita tra 0.6 e 1.4
        ratio = round(1.0 + ALPHA_PRECIP * (raw - 1.0), 3)
        ratio = round(clip(ratio, 0.6, 1.4), 3)
    cal["precip_ratio"] = ratio
    cal["precip_osservato_mm"] = round(tot_obs, 1)
    cal["precip_previsto_mm"] = round(tot_fc, 1)

    # --- vento ---
    w_bias = wind.get("bias")
    w_off = 0.0
    if hours >= MIN_HOURS and w_bias is not None and abs(w_bias) >= MIN_BIAS_OTHER:
        w_off = round(-w_bias * ALPHA_OTHER, 2)
    cal["wind_offset"] = w_off
    cal["wind_bias_misurato"] = round(w_bias, 3) if w_bias is not None else None

    # --- umidità ---
    h_bias = hum.get("bias")
    h_off = 0.0
    if hours >= MIN_HOURS and h_bias is not None and abs(h_bias) >= MIN_BIAS_OTHER:
        h_off = round(-h_bias * ALPHA_OTHER, 1)
    cal["humidity_offset"] = h_off
    cal["humidity_bias_misurato"] = round(h_bias, 3) if h_bias is not None else None

    with open("calibrazione.json", "w") as fh:
        json.dump(cal, fh, ensure_ascii=False, indent=1)
    print(f"Calibrazione salvata ({winner}):")
    print(f"  temp  offset = {t_off:+.2f} °C  (bias misurato {t_bias:+.2f})")
    print(f"  pioggia ratio = {ratio:.3f}  (obs {tot_obs:.1f} / fc {tot_fc:.1f} mm, {days_rain} gg)")
    print(f"  vento offset  = {w_off:+.2f} m/s · umidità offset = {h_off:+.1f} %")

if __name__ == "__main__":
    main()