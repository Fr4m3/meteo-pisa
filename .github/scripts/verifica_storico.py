#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Aggiorna lo storico delle verifiche (verifica_storico.json):
legge l'ultima verifica (verifica_modelli.json) e la aggiunge/aggiorna
nello storico, con etichetta umana per ogni modello.
Idempotente: se esiste gia' una corsa con la stessa finestra, la sostituisce.
"""
import json
from datetime import datetime

NAME = {
    "ecmwf_ifs025": "ECMWF IFS 0.25° (HRES)",
    "icon_seamless": "DWD ICON (seamless)",
    "best_match": "Best-match (ICON)",
    "metno_seamless": "Yr/MET Norway (escluso)",
    "gfs025": "GFS 0.25° (NOAA)",
    "ecmwf_aifs025": "ECMWF AIFS",
}

def main():
    vf = json.load(open("verifica_modelli.json"))
    storico_path = "verifica_storico.json"
    try:
        storico = json.load(open(storico_path))
    except FileNotFoundError:
        storico = {"ultimo_aggiornamento": None, "runs": []}

    run = {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "window": vf["window"],
        "window_days": vf["window_days"],
        "winner": vf["winner"],
        "models": [],
    }
    for key, r in vf["results"].items():
        s = r["var_stats"]
        p = s.get("precip_daily", {})
        run["models"].append({
            "key": key,
            "label": NAME.get(key, key),
            "temp_mae": s.get("temperature_2m", {}).get("mae"),
            "temp_rmse": s.get("temperature_2m", {}).get("rmse"),
            "temp_bias": s.get("temperature_2m", {}).get("bias"),
            "tmax_err": s.get("tmax_err", {}).get("mae"),
            "tmin_err": s.get("tmin_err", {}).get("mae"),
            "wind_mae": s.get("wind_speed_10m", {}).get("mae"),
            "hum_mae": s.get("relative_humidity_2m", {}).get("mae"),
            "precip_mae": p.get("mae"),
            "precip_tot_fc": p.get("tot_fc_mm"),
            "precip_tot_obs": p.get("tot_obs_mm"),
            "giorni_pioggia": p.get("giorni_pioggia"),
            "composite": r["composite_mae"],
            "ore": r["temp_n"],
        })
    run["models"].sort(key=lambda m: m["composite"] or 9e9)

    # sostituzione idempotente per finestra [window[0]]
    w0 = run["window"][0]
    runs = [r for r in storico["runs"] if r["window"][0] != w0]
    runs.append(run)
    runs.sort(key=lambda r: r["window"][0])
    storico["runs"] = runs
    storico["ultimo_aggiornamento"] = datetime.now().strftime("%Y-%m-%d %H:%M")

    with open(storico_path, "w") as fh:
        json.dump(storico, fh, ensure_ascii=False, indent=1)
    print(f"Storico aggiornato: {len(runs)} corse di verifica (finestre) salvate.")
    print(f"  - ultima: {run['window'][0]} -> {run['window'][1]}  vincitore: {NAME.get(vf['winner'], vf['winner'])}")

if __name__ == "__main__":
    main()