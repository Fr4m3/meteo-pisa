#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Confronto modelli meteo vs osservazioni reali per Pisa - v2 (fix allineamento).
I modelli vengono confrontati ORA PER ORA (stesso timestamp) con le osservazioni
dell'archivio Open-Meteo (stazioni + ERA5), sugli ultimi 30 giorni.
"""
import json
import math
import urllib.request
import urllib.parse
from datetime import datetime, timedelta

LAT, LON = 43.7228, 10.4017
MODELS = ["ecmwf_ifs025", "icon_seamless", "best_match"]
VARS = "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m"
PAST_DAYS = 35
N_DAYS = 30
WINDOW_MIN = (datetime.now() - timedelta(days=N_DAYS, hours=2)).strftime("%Y-%m-%d")
WINDOW_MAX = (datetime.now() - timedelta(hours=2)).strftime("%Y-%m-%d")

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "pisa-meteo-verif/2.0"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.load(r)

def to_map(times, values):
    """{timestamp: value} saltando None."""
    return {t: v for t, v in zip(times, values) if v is not None}

def metrics(pairs):
    """MAE/RMSE/bias da lista di coppie (obs, fc)."""
    if not pairs:
        return None
    n = len(pairs)
    mae = sum(abs(o - f) for o, f in pairs) / n
    rmse = math.sqrt(sum((o - f) ** 2 for o, f in pairs) / n)
    bias = sum(f - o for o, f in pairs) / n
    return {"n": n, "mae": mae, "rmse": rmse, "bias": bias}

def main():
    print(f"[1/2] Scarico previsioni archiviate dei modelli ({PAST_DAYS} g)...")
    q = urllib.parse.urlencode({"latitude": LAT, "longitude": LON, "past_days": PAST_DAYS,
                                "forecast_days": 0, "hourly": VARS,
                                "models": ",".join(MODELS), "timezone": "Europe/Rome"})
    f = get(f"https://api.open-meteo.com/v1/forecast?{q}")
    hf = f["hourly"]

    print("[2/2] Scarico osservazioni (archivio)...")
    start = (datetime.now() - timedelta(days=PAST_DAYS + 2)).strftime("%Y-%m-%d")
    end = datetime.now().strftime("%Y-%m-%d")
    q2 = urllib.parse.urlencode({"latitude": LAT, "longitude": LON,
                                 "start_date": start, "end_date": end,
                                 "hourly": VARS, "timezone": "Europe/Rome"})
    a = get(f"https://archive-api.open-meteo.com/v1/archive?{q2}")
    ha = a["hourly"]

    obs = {v: to_map(ha["time"], ha[v])
           for v in ["temperature_2m", "relative_humidity_2m", "precipitation", "wind_speed_10m"]}

    # --- verifica per modello ---
    results = {}
    for m in MODELS:
        fc = {v: to_map(hf["time"], hf.get(f"{v}_{m}"))
              for v in ["temperature_2m", "relative_humidity_2m", "precipitation", "wind_speed_10m"]}
        if not fc["temperature_2m"]:
            print(f"  {m}: nessun dato, salto")
            continue

        vs = {}
        for v in ["temperature_2m", "relative_humidity_2m", "wind_speed_10m"]:
            pairs = [(obs[v][t], fc[v][t]) for t in fc[v]
                     if WINDOW_MIN <= t[:10] <= WINDOW_MAX and t in obs[v]]
            mm = metrics(pairs)
            if mm:
                vs[v] = mm

        # contemporaneita': quante ore valide
        temp_n = vs.get("temperature_2m", {}).get("n", 0)

        # precipitazione giornaliera (somma)
        obs_day = {}
        fc_day = {}
        for t, v in obs["precipitation"].items():
            if WINDOW_MIN <= t[:10] <= WINDOW_MAX:
                obs_day[t[:10]] = obs_day.get(t[:10], 0) + v
        for t, v in fc["precipitation"].items():
            if WINDOW_MIN <= t[:10] <= WINDOW_MAX:
                fc_day[t[:10]] = fc_day.get(t[:10], 0) + v
        dpairs = [(obs_day[d], fc_day[d]) for d in sorted(set(obs_day) & set(fc_day))]
        mp = metrics(dpairs)
        if mp:
            vs["precip_daily"] = mp
            vs["precip_daily"]["tot_obs_mm"] = sum(x[0] for x in dpairs)
            vs["precip_daily"]["tot_fc_mm"] = sum(x[1] for x in dpairs)
            vs["precip_daily"]["giorni_pioggia"] = sum(1 for x in dpairs if x[0] > 0.1)

        # Tmax / Tmin giornalieri
        odt, fdt = {}, {}
        for t, v in obs["temperature_2m"].items():
            if WINDOW_MIN <= t[:10] <= WINDOW_MAX:
                odt.setdefault(t[:10], []).append(v)
        for t, v in fc["temperature_2m"].items():
            if WINDOW_MIN <= t[:10] <= WINDOW_MAX:
                fdt.setdefault(t[:10], []).append(v)
        for name, f in (("tmax", max), ("tmin", min)):
            errs = []
            for d in sorted(set(odt) & set(fdt)):
                if len(odt[d]) < 22 or len(fdt[d]) < 20:   # giornata quasi completa
                    continue
                errs.append(f(odt[d]) - f(fdt[d]))
            if errs:
                vs[f"{name}_err"] = {"mae": sum(abs(e) for e in errs) / len(errs),
                                     "n": len(errs)}

        # score composito (pesi: temp e pioggia piu' importanti)
        w = {"temperature_2m": 2.0, "precip_daily": 1.5,
             "wind_speed_10m": 1.0, "relative_humidity_2m": 1.0,
             "tmax_err": 0.5, "tmin_err": 0.5}
        num = den = 0.0
        for v, wt in w.items():
            if v in vs:
                num += vs[v]["mae"] * wt
                den += wt
        results[m] = {"var_stats": vs, "composite_mae": num / den, "temp_n": temp_n}

    # --- tabella ---
    print("\n" + "=" * 108)
    print(f"VERIFICA su {N_DAYS} giorni (finestra {WINDOW_MIN} … {WINDOW_MAX}) — Pisa (43.72N, 10.40E)")
    print("=" * 108)
    hdr = (f"{'MODELLO':<18}{'T MAE':>8}{'T RMSE':>8}{'BiasT':>8}{'PrecMAE':>9}"
           f"{'Ptot':>7}{'Tmax':>7}{'Tmin':>7}{'Vento':>8}{'Umid':>8}{'COMP':>9}")
    print(hdr)
    print("-" * 108)
    ranked = sorted(results.items(), key=lambda kv: kv[1]["composite_mae"])
    for m, r in ranked:
        s = r["var_stats"]
        t = s.get("temperature_2m", {})
        p = s.get("precip_daily", {})
        w_ = s.get("wind_speed_10m", {})
        hu = s.get("relative_humidity_2m", {})
        tx = s.get("tmax_err", {})
        tn = s.get("tmin_err", {})
        def f2(x): return f"{x:7.2f}" if x is not None else "    -- "
        print(f"{m:<18}{f2(t.get('mae'))}{f2(t.get('rmse'))}{f2(t.get('bias'))}"
              f"{f2(p.get('mae'))}{f2(p.get('tot_obs_mm'))} {p.get('giorni_pioggia','-'):>3}"
              f"{f2(tx.get('mae'))}{f2(tn.get('mae'))}{f2(w_.get('mae'))}"
              f"{f2(hu.get('mae'))}  {r['composite_mae']:6.3f}")
        if p:
            print(f"    (pioggia: reale {p.get('tot_obs_mm'):.1f} mm, prevista {p.get('tot_fc_mm'):.1f} mm, "
                  f"giorni con pioggia osservata: {p.get('giorni_pioggia')})")
    print("-" * 108)

    winner = ranked[0][0]
    print(f"\n>>> VINCITORE: {winner}  (composite MAE = {ranked[0][1]['composite_mae']:.3f}, "
          f"ore confrontate = {ranked[0][1]['temp_n']})")
    with open("verifica_modelli.json", "w") as fh:
        json.dump({"window_days": N_DAYS, "window": [WINDOW_MIN, WINDOW_MAX],
                   "modelli": MODELS, "results": results, "winner": winner},
                  fh, indent=2, ensure_ascii=False)
    print("Salvato in verifica_modelli.json")

if __name__ == "__main__":
    main()