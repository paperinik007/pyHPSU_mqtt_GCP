# Guida alla Migrazione - Google Cloud Pub/Sub

## Panoramica

**IMPORTANTE**: Google Cloud IoT Core è stato deprecato e dismesso il 16 agosto 2023.

Questo progetto è stato aggiornato per utilizzare **Google Cloud Pub/Sub** invece di Google Cloud IoT Core.

## Vantaggi della Nuova Implementazione

- ✅ Usa API attive e supportate (Pub/Sub)
- ✅ Autenticazione moderna con Service Account
- ✅ Più semplice da configurare
- ✅ Migliori performance e scalabilità
- ✅ Supporto per MQTT locale opzionale
- ✅ Gestione errori migliorata

## Prerequisiti

### 1. Installazione Librerie Python

```bash
# Installa google-cloud-pubsub
pip install google-cloud-pubsub

# Opzionale: per MQTT locale
pip install paho-mqtt
```

### 2. Configurazione Google Cloud Platform

#### A. Crea un Progetto GCP (se non esiste)

```bash
# Installa gcloud CLI se non presente
# https://cloud.google.com/sdk/docs/install

# Crea un nuovo progetto
gcloud projects create your-project-id --name="HPSU IoT"

# Imposta il progetto come default
gcloud config set project your-project-id
```

#### B. Abilita le API necessarie

```bash
# Abilita Pub/Sub API
gcloud services enable pubsub.googleapis.com
```

#### C. Crea un Topic Pub/Sub

```bash
# Crea il topic
gcloud pubsub topics create hpsu-telemetry

# Verifica la creazione
gcloud pubsub topics list
```

#### D. Crea una Subscription (opzionale, per testare)

```bash
# Crea una subscription per visualizzare i messaggi
gcloud pubsub subscriptions create hpsu-telemetry-sub \
    --topic=hpsu-telemetry
```

#### E. Crea un Service Account

```bash
# Crea il service account
gcloud iam service-accounts create hpsu-publisher \
    --display-name="HPSU Pub/Sub Publisher"

# Assegna il ruolo Pub/Sub Publisher
gcloud projects add-iam-policy-binding your-project-id \
    --member="serviceAccount:hpsu-publisher@your-project-id.iam.gserviceaccount.com" \
    --role="roles/pubsub.publisher"

# Scarica la chiave JSON
gcloud iam service-accounts keys create /etc/pyHPSU/keys/service-account.json \
    --iam-account=hpsu-publisher@your-project-id.iam.gserviceaccount.com
```

## Configurazione

### 1. Aggiorna il file di configurazione

Modifica `/etc/pyHPSU/pyhpsu.conf`:

```ini
[PYHPSU]
OUTPUT_TYPE = MQTT

[GCP_PUBSUB]
ENABLED = true
PROJECT_ID = your-project-id
TOPIC_ID = hpsu-telemetry
DEVICE_ID = hpsu-001
CREDENTIALS_FILE = /etc/pyHPSU/keys/service-account.json
```

### 2. File di esempio

È disponibile un file di configurazione di esempio completo:

```bash
cp /etc/pyHPSU/pyhpsu_gcp.conf.example /etc/pyHPSU/pyhpsu.conf
# Modifica il file con i tuoi parametri
nano /etc/pyHPSU/pyhpsu.conf
```

## Test della Configurazione

### Test 1: Verifica del Plugin

```bash
# Test diretto del plugin
python3 /usr/lib/python3/dist-packages/HPSU/plugins/mqtt.py /etc/pyHPSU/pyhpsu.conf
```

### Test 2: Verifica Messaggi su Pub/Sub

In un altro terminale, monitora i messaggi:

```bash
# Ricevi i messaggi dalla subscription
gcloud pubsub subscriptions pull hpsu-telemetry-sub --auto-ack --limit=10
```

### Test 3: Esegui pyHPSU

```bash
# Esegui in auto mode
pyHPSU.py -a
```

## Formato dei Messaggi

I messaggi pubblicati su Pub/Sub hanno il seguente formato JSON:

```json
{
  "timestamp": "2025-11-10T10:30:00.123456+00:00",
  "device_id": "hpsu-001",
  "measurements": {
    "t_hs": "32.5",
    "t_dhw": "45.0",
    "water_pressure": "1.8",
    "t_ext": "15.2"
  }
}
```

### Attributi del Messaggio

Ogni messaggio include anche attributi Pub/Sub:

- `device_id`: ID del dispositivo
- `timestamp`: Timestamp ISO 8601
- `source`: "pyHPSU"

Questi attributi possono essere usati per filtrare i messaggi nelle subscription.

## Integrazione con BigQuery

### Setup Completo (Gratuito!)

Il progetto include una **Cloud Function completa** già pronta che:
- Riceve automaticamente i dati da Pub/Sub
- Li inserisce in BigQuery con schema ottimizzato
- È configurata per rimanere **completamente nel tier gratuito**

#### Costi Stimati

Con 1 dispositivo HPSU (messaggio ogni 30 secondi):

| Servizio | Utilizzo/mese | Tier Gratuito | Costo |
|----------|---------------|---------------|-------|
| Cloud Functions | ~86,400 invocazioni | 2M invocazioni | **$0.00** |
| BigQuery Storage | ~2-3 MB | 10 GB | **$0.00** |
| BigQuery Query | Dipende | 1 TB processati | **$0.00** |
| Pub/Sub | ~0.5 GB | 10 GB | **$0.00** |

**Totale: $0.00/mese** 🎉

### Quick Start BigQuery

#### 1. Crea Dataset e Tabella

```bash
cd bigquery
./create_dataset.sh your-project-id
```

Questo script crea:
- Dataset `hpsu_data`
- Tabella `telemetry` con schema completo
- Partitioning per query veloci
- Opzionalmente, data retention policy

#### 2. Deploy Cloud Function

```bash
cd cloud-function
./deploy.sh your-project-id europe-west1
```

Parametri:
- `your-project-id`: Il tuo GCP project ID
- `europe-west1`: Region più vicina (o `us-central1`, `asia-northeast1`)

#### 3. Testa

```bash
# Pubblica un messaggio di test
gcloud pubsub topics publish hpsu-telemetry \
  --message='{"timestamp":"2025-11-10T10:30:00+00:00","device_id":"test","measurements":{"t_hs":"32.5"}}'

# Controlla i log
gcloud functions logs read hpsu-to-bigquery --region=europe-west1 --limit=50

# Query i dati
bq query --use_legacy_sql=false \
  'SELECT * FROM `your-project-id.hpsu_data.telemetry` ORDER BY timestamp DESC LIMIT 10'
```

### Schema BigQuery

La tabella include tutti i campi HPSU comuni:

```sql
CREATE TABLE `your-project-id.hpsu_data.telemetry` (
  timestamp TIMESTAMP NOT NULL,          -- Chiave di partitioning
  device_id STRING NOT NULL,             -- Chiave di clustering
  t_hs FLOAT64,                          -- Temperatura mandata riscaldamento
  t_hs_set FLOAT64,                      -- Setpoint mandata
  t_dhw FLOAT64,                         -- Temperatura ACS
  t_dhw_set FLOAT64,                     -- Setpoint ACS
  t_ext FLOAT64,                         -- Temperatura esterna
  t_return FLOAT64,                      -- Temperatura ritorno
  t_hc FLOAT64,                          -- Temperatura circuito
  t_hc_set FLOAT64,                      -- Setpoint circuito
  water_pressure FLOAT64,                -- Pressione acqua
  flow_rate FLOAT64,                     -- Portata
  mode STRING,                           -- Modalità operativa
  error_code STRING,                     -- Codice errore
  additional_data STRING                 -- Altri dati (JSON)
)
PARTITION BY DATE(timestamp)
CLUSTER BY device_id, timestamp;
```

### Query di Esempio

#### Temperature medie ultime 24 ore

```sql
SELECT
  AVG(t_hs) as avg_mandata,
  AVG(t_dhw) as avg_acs,
  AVG(t_ext) as avg_esterna
FROM `your-project-id.hpsu_data.telemetry`
WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
```

#### Andamento settimanale

```sql
SELECT
  DATE(timestamp) as giorno,
  ROUND(AVG(t_hs), 1) as temp_media,
  ROUND(MIN(t_hs), 1) as temp_min,
  ROUND(MAX(t_hs), 1) as temp_max
FROM `your-project-id.hpsu_data.telemetry`
WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
GROUP BY giorno
ORDER BY giorno DESC
```

#### Allarme pressione bassa

```sql
SELECT timestamp, water_pressure
FROM `your-project-id.hpsu_data.telemetry`
WHERE water_pressure < 1.0
  AND timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
ORDER BY timestamp DESC
```

### Documentazione Completa

Vedi **[cloud-function/README.md](cloud-function/README.md)** per:
- Istruzioni dettagliate di setup
- Configurazione avanzata
- Query di esempio avanzate
- Troubleshooting
- Monitoring e alerting

## Troubleshooting

### Errore: "Permission denied"

```bash
# Verifica i permessi del service account
gcloud projects get-iam-policy your-project-id \
    --flatten="bindings[].members" \
    --filter="bindings.members:serviceAccount:hpsu-publisher@*"
```

### Errore: "Topic not found"

```bash
# Verifica che il topic esista
gcloud pubsub topics describe hpsu-telemetry
```

### Errore: "Application Default Credentials not found"

Se non specifichi `CREDENTIALS_FILE`, assicurati che ADC sia configurato:

```bash
gcloud auth application-default login
```

### Debug logging

Modifica `/usr/lib/python3/dist-packages/HPSU/plugins/mqtt.py` riga 59:

```python
logging.basicConfig(level=logging.DEBUG)  # Cambia INFO in DEBUG
```

## Confronto: Vecchio vs Nuovo

| Caratteristica | IoT Core (Vecchio) | Pub/Sub (Nuovo) |
|----------------|-------------------|-----------------|
| Stato | ❌ Deprecato | ✅ Attivo |
| Complessità | Alta (JWT, MQTT bridge) | Bassa |
| Autenticazione | JWT con chiavi EC/RSA | Service Account |
| Protocollo | MQTT over TLS | gRPC/HTTP |
| Performance | Buone | Ottime |
| Costo | Più alto | Più basso |
| Manutenzione | Nessuna (deprecato) | Supporto completo |

## Migrazione da IoT Core

Se hai già dati su IoT Core:

1. **Non c'è migrazione automatica** - IoT Core è stato dismesso
2. Configura il nuovo sistema con Pub/Sub seguendo questa guida
3. I vecchi certificati EC/RSA non sono più necessari
4. Usa Service Account invece di JWT

## Supporto e Documentazione

- [Google Cloud Pub/Sub Documentation](https://cloud.google.com/pubsub/docs)
- [Python Client Library](https://cloud.google.com/pubsub/docs/reference/libraries#client-libraries-install-python)
- [Best Practices](https://cloud.google.com/pubsub/docs/publisher)

## Note di Sicurezza

1. **Proteggi il Service Account JSON**:
   ```bash
   chmod 600 /etc/pyHPSU/keys/service-account.json
   ```

2. **Principio del minimo privilegio**: Il service account ha solo il ruolo `pubsub.publisher`

3. **Rotazione chiavi**: Ruota periodicamente le chiavi del service account

4. **Non committare credenziali**: Aggiungi `*.json` al `.gitignore`

## Costi

Google Cloud Pub/Sub ha un tier gratuito:
- Primi 10 GB di dati al mese: gratuiti
- Primi 1 TB di egress al mese: gratuiti

Per un singolo dispositivo HPSU, i costi mensili sono praticamente nulli.

[Dettagli pricing](https://cloud.google.com/pubsub/pricing)
