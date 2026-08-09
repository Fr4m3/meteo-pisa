# Meteo Pisa — pagina GitHub Pages

Pagina previsioni per Pisa basata sul modello **ECMWF IFS 0.25°** (scelto dopo
verifica oggettiva di 30 giorni contro le osservazioni Open-Meteo).

- `index.html` — pagina statica (si aggiorna dal vivo nel browser via API Open-Meteo)
- `forecast.json` — istantanea dei dati (aggiornata ogni giorno da cron sul telefono)
- La verifica completa dei modelli: `~/pisa_meteo/` (script + dati)
