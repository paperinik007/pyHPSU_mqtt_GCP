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

### Esempio di Cloud Function per BigQuery

Crea una Cloud Function che inserisce automaticamente i dati in BigQuery:

```python
import json
from google.cloud import bigquery

def pubsub_to_bigquery(event, context):
    """Triggered from a message on a Cloud Pub/Sub topic."""

    # Decodifica il messaggio
    pubsub_message = json.loads(base64.b64decode(event['data']).decode('utf-8'))

    # Client BigQuery
    client = bigquery.Client()
    table_id = "your-project.hpsu_dataset.telemetry"

    # Prepara i dati per BigQuery
    rows_to_insert = [{
        "timestamp": pubsub_message["timestamp"],
        "device_id": pubsub_message["device_id"],
        **pubsub_message["measurements"]
    }]

    # Inserisci in BigQuery
    errors = client.insert_rows_json(table_id, rows_to_insert)

    if errors:
        print(f"Errors: {errors}")
    else:
        print("Data inserted successfully")
```

### Schema BigQuery Esempio

```sql
CREATE TABLE `your-project.hpsu_dataset.telemetry` (
  timestamp TIMESTAMP,
  device_id STRING,
  t_hs FLOAT64,
  t_dhw FLOAT64,
  water_pressure FLOAT64,
  t_ext FLOAT64,
  t_return FLOAT64,
  flow_rate FLOAT64,
  t_hc FLOAT64
);
```

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
