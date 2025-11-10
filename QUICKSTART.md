# 🚀 Quick Start - HPSU to BigQuery in 5 minuti

Questa guida ti porta da zero a dati HPSU in BigQuery in meno di 5 minuti.

## 📋 Prerequisiti

- [ ] Account Google Cloud (gratuito)
- [ ] gcloud CLI installato ([istruzioni](https://cloud.google.com/sdk/docs/install))
- [ ] Python 3.7+ con pip
- [ ] Dispositivo HPSU connesso

## ⚡ Setup Rapido

### 1. Setup GCP (2 minuti)

```bash
# Imposta variabili
export PROJECT_ID="my-hpsu-project"  # Cambia con il tuo nome progetto
export REGION="europe-west1"         # o us-central1, asia-northeast1

# Crea progetto
gcloud projects create $PROJECT_ID --name="HPSU IoT"
gcloud config set project $PROJECT_ID

# Abilita billing (necessario ma rimani nel tier gratuito!)
# Vai a: https://console.cloud.google.com/billing
# Collega una carta di credito (non verrà addebitato nulla)

# Abilita API
gcloud services enable \
  pubsub.googleapis.com \
  bigquery.googleapis.com \
  cloudfunctions.googleapis.com \
  cloudbuild.googleapis.com

# Crea topic Pub/Sub
gcloud pubsub topics create hpsu-telemetry

# Crea service account
gcloud iam service-accounts create hpsu-publisher \
  --display-name="HPSU Publisher"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:hpsu-publisher@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/pubsub.publisher"

# Scarica chiave
mkdir -p ~/.config/hpsu/keys
gcloud iam service-accounts keys create ~/.config/hpsu/keys/service-account.json \
  --iam-account=hpsu-publisher@${PROJECT_ID}.iam.gserviceaccount.com
```

### 2. Setup BigQuery (1 minuto)

```bash
cd bigquery
./create_dataset.sh $PROJECT_ID
```

Premi INVIO quando chiede la retention (default = mantieni tutto).

### 3. Deploy Cloud Function (1 minuto)

```bash
cd ../cloud-function
./deploy.sh $PROJECT_ID $REGION
```

Attendi che il deploy completi (~1-2 minuti).

### 4. Setup pyHPSU (1 minuto)

```bash
# Installa dipendenze
pip install -r requirements_gcp.txt

# Copia config di esempio
sudo cp etc/pyHPSU/pyhpsu_gcp.conf.example /etc/pyHPSU/pyhpsu.conf

# Modifica config
sudo nano /etc/pyHPSU/pyhpsu.conf
```

Modifica queste righe:

```ini
[GCP_PUBSUB]
ENABLED = true
PROJECT_ID = my-hpsu-project              # ← Il tuo project ID
TOPIC_ID = hpsu-telemetry
DEVICE_ID = hpsu-001                      # ← Identificatore del tuo device
CREDENTIALS_FILE = /home/yourusername/.config/hpsu/keys/service-account.json  # ← Percorso alla chiave

[PYHPSU]
OUTPUT_TYPE = MQTT                        # ← Importante!
```

Salva con `Ctrl+O`, esci con `Ctrl+X`.

### 5. Avvia pyHPSU

```bash
# Test singolo
pyHPSU.py -c t_hs

# Auto mode (continuo)
pyHPSU.py -a
```

## ✅ Verifica che Funzioni

### Test 1: Verifica Pub/Sub

```bash
# Pubblica messaggio di test
gcloud pubsub topics publish hpsu-telemetry \
  --message='{"timestamp":"'$(date -u +%Y-%m-%dT%H:%M:%S+00:00)'","device_id":"test","measurements":{"t_hs":"32.5"}}'

# Output atteso: messageIds: ['123456789']
```

### Test 2: Verifica Cloud Function

```bash
# Controlla log
gcloud functions logs read hpsu-to-bigquery \
  --region=$REGION \
  --limit=10

# Cerca righe tipo:
# D  hpsu-to-bigquery Function triggered by messageId...
# I  hpsu-to-bigquery Inserite 1 righe in BigQuery con successo
```

### Test 3: Verifica BigQuery

```bash
# Query ultimi 10 record
bq query --use_legacy_sql=false \
  "SELECT * FROM \`${PROJECT_ID}.hpsu_data.telemetry\` ORDER BY timestamp DESC LIMIT 10"

# Dovresti vedere i tuoi dati!
```

## 🎉 Fatto!

Se vedi dati in BigQuery, tutto funziona!

I dati ora arrivano automaticamente:
- pyHPSU legge dalla pompa di calore ogni X secondi
- Invia a Pub/Sub
- Cloud Function li inserisce in BigQuery
- Tutto gratis! 🎉

## 📊 Visualizza i Dati

### Opzione 1: BigQuery Console

Vai a: https://console.cloud.google.com/bigquery

Esegui query come:

```sql
-- Temperature ultime 24 ore
SELECT
  timestamp,
  t_hs as temp_mandata,
  t_dhw as temp_acs,
  t_ext as temp_esterna
FROM `my-hpsu-project.hpsu_data.telemetry`
WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
ORDER BY timestamp DESC
```

### Opzione 2: Google Data Studio (Grafici)

1. Vai a: https://datastudio.google.com/
2. Create → Report
3. Add Data → BigQuery
4. Seleziona: `my-hpsu-project > hpsu_data > telemetry`
5. Crea grafici con i tuoi dati!

### Opzione 3: Grafana (Self-hosted)

```bash
# Installa plugin BigQuery per Grafana
grafana-cli plugins install doitintl-bigquery-datasource

# Aggiungi data source con service account
```

## 🔧 Configurazione Avanzata

### Cambia Frequenza Invio

Modifica `/etc/pyHPSU/pyhpsu.conf`:

```ini
[JOBS]
T_HS = 30          # Ogni 30 secondi
T_HS_SET = 60      # Ogni 60 secondi
t_ext = 120        # Ogni 2 minuti
```

### Avvio Automatico (systemd)

```bash
# Crea service
sudo nano /etc/systemd/system/pyhpsu.service
```

```ini
[Unit]
Description=pyHPSU Auto Mode
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi
ExecStart=/usr/bin/python3 /usr/bin/pyHPSU.py -a
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Abilita e avvia
sudo systemctl enable pyhpsu.service
sudo systemctl start pyhpsu.service

# Controlla status
sudo systemctl status pyhpsu.service
```

## 🐛 Troubleshooting Rapido

### Errore: "Permission denied"

```bash
# Verifica permessi service account
gcloud projects get-iam-policy $PROJECT_ID \
  --flatten="bindings[].members" \
  --filter="bindings.members:serviceAccount:hpsu-publisher*"
```

### Errore: "Topic not found"

```bash
# Verifica topic
gcloud pubsub topics list

# Se mancante, ricrea
gcloud pubsub topics create hpsu-telemetry
```

### Dati non arrivano in BigQuery

```bash
# 1. Verifica pyHPSU invia
# Vedi output del comando pyHPSU.py -a

# 2. Verifica messaggi Pub/Sub
gcloud pubsub topics publish hpsu-telemetry --message='test'

# 3. Verifica function logs
gcloud functions logs read hpsu-to-bigquery --region=$REGION --limit=50

# 4. Verifica tabella BigQuery
bq show $PROJECT_ID:hpsu_data.telemetry
```

## 📚 Prossimi Passi

1. ✅ Sistema funzionante
2. 📖 Leggi [GCP_MIGRATION_GUIDE.md](GCP_MIGRATION_GUIDE.md) per dettagli
3. 💰 Leggi [COST_ANALYSIS.md](COST_ANALYSIS.md) per confermare costi = $0
4. 📊 Crea dashboard in Data Studio
5. 🔔 Configura alerting (opzionale)

## 💡 Tips

- **Backup config**: `cp /etc/pyHPSU/pyhpsu.conf ~/pyhpsu.conf.backup`
- **Monitor invocazioni**: `gcloud functions describe hpsu-to-bigquery --region=$REGION`
- **Test locale function**: `cd cloud-function && python3 main.py`
- **Retention dati**: Configura se vuoi limitare storage (vedi BigQuery docs)

## 🆘 Aiuto

- 📖 [Documentazione completa](GCP_MIGRATION_GUIDE.md)
- 🐛 [Troubleshooting dettagliato](GCP_MIGRATION_GUIDE.md#troubleshooting)
- 💬 [GitHub Issues](https://github.com/paperinik007/pyHPSU_mqtt_GCP/issues)

---

**🎉 Congratulazioni! Hai un sistema IoT professionale completamente gratuito!**
