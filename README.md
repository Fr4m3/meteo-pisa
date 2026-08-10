# Meteo Pisa — pagina GitHub Pages

Pagina previsioni per Pisa basata sul modello **ECMWF IFS 0.25°** (scelto dopo
verifica oggettiva di 30 giorni contro le osservazioni Open-Meteo).

- `index.html` — pagina statica (si aggiorna dal vivo nel browser via API Open-Meteo)
- `forecast.json` — istantanea dei dati (aggiornata ogni giorno da cron sul telefono)
- La verifica completa dei modelli: `~/pisa_meteo/` (script + dati)

## Aggiornamento automatico

Il progetto è collegato a GitHub Actions:
- **Previsioni giornaliere**: ogni giorno alle 05:30 e 17:30 UTC (07:30/19:30 IT) il workflow `aggiorna-previsioni.yml` scarica le previsioni dal modello vincente e rigenera la pagina.
- **Verifica settimanale**: ogni lunedì alle 04:15 UTC il workflow `verifica-settimanale.yml` ricalcola la classifica dei modelli su 30 giorni, aggiorna storico/calibrazione e regenera previsioni + pagina.
- Entrambi eseguibili anche manualmente dal tab Actions.
