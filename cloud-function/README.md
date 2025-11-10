# Cloud Function HPSU → BigQuery

Questa Cloud Function riceve i dati della pompa di calore HPSU da Pub/Sub e li inserisce automaticamente in BigQuery.

## 🎯 Caratteristiche

- ✅ **Completamente gratuita** per un singolo dispositivo HPSU
- ✅ **Serverless**: nessun server da gestire
- ✅ **Auto-scaling**: scala automaticamente con il carico
- ✅ **Affidabile**: retry automatici in caso di errore
- ✅ **Efficiente**: ottimizzata per minimizzare memoria e tempo di esecuzione

## 💰 Costi (Tier Gratuito)

Con configurazione standard (1 messaggio ogni 30 secondi):

| Servizio | Utilizzo mensile | Tier Gratuito | Costo |
|----------|------------------|---------------|-------|
| Cloud Functions | ~86,400 invocazioni | 2M invocazioni | $0.00 |
| BigQuery Storage | ~2-3 MB | 10 GB | $0.00 |
| BigQuery Query | Dipende dalle query | 1 TB processati | $0.00 |
| Pub/Sub | ~0.5 GB | 10 GB | $0.00 |

**Totale stimato: $0.00/mese** 🎉

## 📋 Prerequisiti

1. Progetto GCP configurato
2. Topic Pub/Sub creato (`hpsu-telemetry`)
3. gcloud CLI installato e autenticato
4. Permessi necessari:
   - `cloudfunctions.developer`
   - `bigquery.admin`
   - `iam.serviceAccountUser`

## 🚀 Quick Start

### 1. Crea il Dataset BigQuery

```bash
cd bigquery
./create_dataset.sh YOUR_PROJECT_ID
```

Questo script:
- Crea il dataset `hpsu_data`
- Crea la tabella `telemetry` con schema ottimizzato
- Configura partitioning per query veloci
- Opzionalmente configura data retention

### 2. Deploy della Cloud Function

```bash
cd cloud-function
./deploy.sh YOUR_PROJECT_ID europe-west1
```

Parametri:
- `YOUR_PROJECT_ID`: Il tuo GCP project ID
- `europe-west1`: Region (scegli la più vicina)

Regions disponibili nel tier gratuito:
- `europe-west1` (Belgio)
- `us-central1` (Iowa)
- `us-east1` (South Carolina)
- `asia-northeast1` (Tokyo)

### 3. Testa la Function

```bash
# Pubblica un messaggio di test
gcloud pubsub topics publish hpsu-telemetry \
  --message='{"timestamp":"2025-11-10T10:30:00+00:00","device_id":"hpsu-test","measurements":{"t_hs":"32.5","t_dhw":"45.0"}}'

# Controlla i log
gcloud functions logs read hpsu-to-bigquery \
  --region=europe-west1 \
  --limit=50
```

### 4. Verifica i Dati in BigQuery

```bash
# Query di test
bq query --use_legacy_sql=false \
  'SELECT * FROM `YOUR_PROJECT_ID.hpsu_data.telemetry` ORDER BY timestamp DESC LIMIT 10'
```

## 📊 Schema BigQuery

La tabella `telemetry` contiene:

| Campo | Tipo | Descrizione |
|-------|------|-------------|
| `timestamp` | TIMESTAMP | Timestamp della misurazione (partitioning key) |
| `device_id` | STRING | ID del dispositivo (clustering key) |
| `t_hs` | FLOAT64 | Temperatura mandata riscaldamento |
| `t_hs_set` | FLOAT64 | Setpoint mandata riscaldamento |
| `t_dhw` | FLOAT64 | Temperatura acqua calda sanitaria |
| `t_dhw_set` | FLOAT64 | Setpoint acqua calda sanitaria |
| `t_ext` | FLOAT64 | Temperatura esterna |
| `t_return` | FLOAT64 | Temperatura ritorno |
| `t_hc` | FLOAT64 | Temperatura circuito riscaldamento |
| `t_hc_set` | FLOAT64 | Setpoint circuito riscaldamento |
| `water_pressure` | FLOAT64 | Pressione acqua impianto |
| `flow_rate` | FLOAT64 | Portata |
| `mode` | STRING | Modalità operativa |
| `error_code` | STRING | Codice errore |
| `additional_data` | STRING | Dati aggiuntivi (JSON) |

### Ottimizzazioni

- **Partitioning per giorno**: Query su periodi specifici sono molto veloci
- **Clustering**: Query filtrate per device_id sono ottimizzate
- **Compression**: Dati compressi automaticamente
- **Time-travel**: Accesso ai dati storici fino a 7 giorni fa

## 📈 Query di Esempio

### Temperature medie ultime 24 ore

```sql
SELECT
  device_id,
  AVG(t_hs) as avg_t_hs,
  AVG(t_dhw) as avg_t_dhw,
  AVG(t_ext) as avg_t_ext,
  COUNT(*) as measurements
FROM `YOUR_PROJECT_ID.hpsu_data.telemetry`
WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
GROUP BY device_id
```

### Andamento temperatura giornaliero

```sql
SELECT
  DATE(timestamp) as day,
  ROUND(AVG(t_hs), 1) as avg_t_hs,
  ROUND(MIN(t_hs), 1) as min_t_hs,
  ROUND(MAX(t_hs), 1) as max_t_hs
FROM `YOUR_PROJECT_ID.hpsu_data.telemetry`
WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
GROUP BY day
ORDER BY day DESC
```

### Pressione acqua sotto soglia

```sql
SELECT
  timestamp,
  device_id,
  water_pressure
FROM `YOUR_PROJECT_ID.hpsu_data.telemetry`
WHERE water_pressure < 1.0
  AND timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
ORDER BY timestamp DESC
```

### Conteggio messaggi per ora

```sql
SELECT
  TIMESTAMP_TRUNC(timestamp, HOUR) as hour,
  COUNT(*) as message_count
FROM `YOUR_PROJECT_ID.hpsu_data.telemetry`
WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
GROUP BY hour
ORDER BY hour DESC
```

## 🔧 Configurazione Avanzata

### Modifica Memory/Timeout

Modifica `deploy.sh`:

```bash
MEMORY="512MB"    # Aumenta se necessario
TIMEOUT="120s"    # Aumenta per operazioni lente
```

⚠️ **Nota**: Aumentare questi valori può superare il tier gratuito.

### Retry Policy

La function NON rilancia eccezioni per evitare retry infiniti. I messaggi falliti vanno nella Dead Letter Queue se configurata.

Per configurare DLQ:

```bash
# Crea subscription con DLQ
gcloud pubsub subscriptions create hpsu-telemetry-dlq \
  --topic=hpsu-telemetry \
  --dead-letter-topic=hpsu-telemetry-failed
```

### Data Retention

Per limitare lo storage (e rimanere nel tier gratuito):

```bash
# 90 giorni retention
bq update \
  --time_partitioning_expiration=7776000000 \
  YOUR_PROJECT_ID:hpsu_data.telemetry
```

### Monitoring

```bash
# Vedi log in tempo reale
gcloud functions logs read hpsu-to-bigquery \
  --region=europe-west1 \
  --follow

# Metriche della function
gcloud functions describe hpsu-to-bigquery \
  --region=europe-west1 \
  --format="value(status)"
```

## 🐛 Troubleshooting

### "Permission denied" error

Verifica che il service account della Cloud Function abbia i permessi:

```bash
# Service account predefinito
SERVICE_ACCOUNT="YOUR_PROJECT_ID@appspot.gserviceaccount.com"

# Aggiungi ruolo BigQuery Data Editor
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:$SERVICE_ACCOUNT" \
  --role="roles/bigquery.dataEditor"
```

### Function timeout

Aumenta il timeout in `deploy.sh`:

```bash
TIMEOUT="120s"
```

### Messaggi non arrivano in BigQuery

1. Controlla i log della function:
   ```bash
   gcloud functions logs read hpsu-to-bigquery --region=europe-west1 --limit=100
   ```

2. Verifica che i messaggi arrivino a Pub/Sub:
   ```bash
   gcloud pubsub subscriptions pull hpsu-telemetry-sub --limit=1
   ```

3. Testa la function manualmente:
   ```bash
   cd cloud-function
   python3 main.py
   ```

## 📚 Documentazione

- [Cloud Functions Docs](https://cloud.google.com/functions/docs)
- [BigQuery Docs](https://cloud.google.com/bigquery/docs)
- [Pub/Sub Docs](https://cloud.google.com/pubsub/docs)

## 🔄 Aggiornamenti

Per aggiornare la function dopo modifiche al codice:

```bash
cd cloud-function
./deploy.sh YOUR_PROJECT_ID europe-west1
```

Il deploy sovrascrive la versione precedente mantenendo la configurazione.

## 🗑️ Cleanup

Per rimuovere tutto:

```bash
# Rimuovi Cloud Function
gcloud functions delete hpsu-to-bigquery --region=europe-west1

# Rimuovi tabella BigQuery (ATTENZIONE: cancella i dati!)
bq rm -f -t YOUR_PROJECT_ID:hpsu_data.telemetry

# Rimuovi dataset (se vuoto)
bq rm -f -d YOUR_PROJECT_ID:hpsu_data
```

## 🤝 Contributi

Suggerimenti e miglioramenti sono benvenuti!

## 📄 Licenza

Stesso del progetto pyHPSU principale.
