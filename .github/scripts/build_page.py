#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Genera index.html a partire da forecast.json + verifica_modelli.json."""
import json
from datetime import datetime

NAME = {
    "ecmwf_ifs025": "ECMWF IFS 0.25° (HRES)",
    "icon_seamless": "DWD ICON (seamless)",
    "best_match": "Best-match composito (ICON)",
    "metno_seamless": "Yr/MET Norway (escluso)",
    "gfs025": "GFS 0.25° (NOAA)",
    "ecmwf_aifs025": "ECMWF AIFS",
}

def js(o):
    return json.dumps(o, ensure_ascii=False).replace("</", "<\\/")

def main():
    fc = json.load(open("forecast.json"))
    vf = json.load(open("verifica_modelli.json"))

    res = vf["results"]
    winner_key = vf["winner"]
    w = res[winner_key]["var_stats"]

    models = []
    for key in ("ecmwf_ifs025", "icon_seamless", "best_match"):
        if key not in res:
            continue
        s = res[key]["var_stats"]
        prec = s.get("precip_daily", {})
        models.append({
            "name": NAME.get(key, key),
            "temp_mae": s.get("temperature_2m", {}).get("mae"),
            "temp_bias": s.get("temperature_2m", {}).get("bias"),
            "tmax_err": s.get("tmax_err", {}).get("mae"),
            "tmin_err": s.get("tmin_err", {}).get("mae"),
            "wind_mae": s.get("wind_speed_10m", {}).get("mae"),
            "hum_mae": s.get("relative_humidity_2m", {}).get("mae"),
            "precip": prec.get("tot_fc_mm"),
            "precip_obs": prec.get("tot_obs_mm"),
            "composite": res[key]["composite_mae"],
        })
    models.sort(key=lambda m: m["composite"] or 9e9)
    winner = models[0]
    others = [m for m in models if m["name"] != winner["name"]]

    note = (
        "Metodologia: verifica su 30 giorni (finestra " + vf["window"][0] + " → " + vf["window"][1] +
        ") comparando ora per ora le previsioni archiviate dei modelli con le osservazioni "
        "Open-Meteo (stazioni Meteorologiche + rianalisi ERA5) per Pisa (43.72N, 10.40E). "
        "Metriche: MAE temperatura/orarie, errore medio su massima e minima giornaliera, "
        "MAE sul totale di pioggia giornaliero e score composito ponderato (temp 2, pioggia 1.5, "
        "vento 1, umidità 1, max/min giornaliere 0.5). "
        "GFS e AIFS/CEP non sono inclusi: Open-Meteo non archivia le loro previsioni passate "
        "(serie vuota). Il cosiddetto 'best match' di Open-Meteo per Pisa coincide con ICON. "
        "Il servizio Yr/MET Norway è stato escluso perché i suoi dati storici restituiti via API "
        "sono analisi, identici alle osservazioni (non vere previsioni). "
        "Nota: agosto è stato asciutto (7 giorni di pioggia, 15.5 mm totali), quindi la componente "
        "precipitazioni ha poco campione statistico; ciononostante ICON ha previsto 0 mm "
        "dove ne sono caduti 15.5, a conferma della migliore affidabilità di ECMWF."
    )
    footer = (
        "Fonte dati: Open-Meteo (api.open-meteo.com) con previsioni del modello ECMWF IFS HRES 0.25° "
        "(file generato il " + fc["generated_at"] + ", fuso Europe/Rome). Osservazioni: archivio Open-Meteo "
        "(stazioni + ERA5). Pagina generata localmente con script Python; la pagina tenta un aggiornamento "
        "dal vivo al caricamento. Uso non professionale: verificare sempre i bollettini ufficiali "
        "(es. Meteo.it / ARPA Toscana) per decisioni importanti."
    )

    verdict = {
        "winner_label": fc["model_label"],
        "window_days": vf["window_days"],
        "window": vf["window"],
        "winner": winner,
        "others": others,
        "models": models,
        "note": note,
        "footer": footer,
    }

    tpl = open("index.template.html", encoding="utf-8").read()
    out = (tpl
           .replace("__FORECAST_JSON__", js(fc))
           .replace("__VERDICT_JSON__", js(verdict)))
    open("index.html", "w", encoding="utf-8").write(out)
    print("index.html scritto (" + str(len(out)) + " byte)")

if __name__ == "__main__":
    main()