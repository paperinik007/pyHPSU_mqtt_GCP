#!/bin/bash

# Script per creare dataset e tabella BigQuery per HPSU telemetry
# Ottimizzato per rimanere nel tier gratuito

set -e  # Exit on error

# Colori per output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configurazione (MODIFICA QUESTI VALORI)
PROJECT_ID="${1:-your-project-id}"
DATASET_ID="hpsu_data"
TABLE_ID="telemetry"
LOCATION="EU"  # Usa EU o US in base alla tua posizione (tier gratuito disponibile in entrambe)

echo -e "${GREEN}=== Setup BigQuery per HPSU Telemetry ===${NC}"
echo ""

# Verifica che gcloud sia installato
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}Errore: gcloud CLI non trovato${NC}"
    echo "Installa da: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Verifica che PROJECT_ID sia stato impostato
if [ "$PROJECT_ID" == "your-project-id" ]; then
    echo -e "${RED}Errore: Devi specificare il PROJECT_ID${NC}"
    echo "Uso: $0 <project-id>"
    echo "Esempio: $0 my-hpsu-project"
    exit 1
fi

echo -e "${YELLOW}Project ID:${NC} $PROJECT_ID"
echo -e "${YELLOW}Dataset ID:${NC} $DATASET_ID"
echo -e "${YELLOW}Table ID:${NC} $TABLE_ID"
echo -e "${YELLOW}Location:${NC} $LOCATION"
echo ""

# Imposta il progetto corrente
echo "Setting project to $PROJECT_ID..."
gcloud config set project "$PROJECT_ID"

# Abilita BigQuery API
echo ""
echo -e "${GREEN}Abilitazione BigQuery API...${NC}"
gcloud services enable bigquery.googleapis.com

# Crea il dataset
echo ""
echo -e "${GREEN}Creazione dataset $DATASET_ID...${NC}"
if bq ls -d "$PROJECT_ID:$DATASET_ID" &> /dev/null; then
    echo -e "${YELLOW}Dataset già esistente, skip...${NC}"
else
    bq mk \
        --dataset \
        --location="$LOCATION" \
        --description="Dataset per telemetria pompa di calore HPSU" \
        --default_table_expiration=0 \
        "$PROJECT_ID:$DATASET_ID"

    echo -e "${GREEN}✓ Dataset creato${NC}"
fi

# Verifica che il file schema.json esista
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCHEMA_FILE="$SCRIPT_DIR/schema.json"

if [ ! -f "$SCHEMA_FILE" ]; then
    echo -e "${RED}Errore: File schema.json non trovato in $SCRIPT_DIR${NC}"
    exit 1
fi

# Crea la tabella con schema
echo ""
echo -e "${GREEN}Creazione tabella $TABLE_ID...${NC}"
if bq ls "$PROJECT_ID:$DATASET_ID.$TABLE_ID" &> /dev/null; then
    echo -e "${YELLOW}Tabella già esistente, skip...${NC}"
else
    bq mk \
        --table \
        --description="Telemetria pompa di calore HPSU - Serie temporale" \
        --time_partitioning_field=timestamp \
        --time_partitioning_type=DAY \
        --clustering_fields=device_id,timestamp \
        "$PROJECT_ID:$DATASET_ID.$TABLE_ID" \
        "$SCHEMA_FILE"

    echo -e "${GREEN}✓ Tabella creata${NC}"
fi

# Mostra info sulla tabella
echo ""
echo -e "${GREEN}Informazioni tabella:${NC}"
bq show "$PROJECT_ID:$DATASET_ID.$TABLE_ID"

# Configura retention policy per ottimizzare i costi (opzionale)
# Commenta se vuoi mantenere tutti i dati
echo ""
echo -e "${YELLOW}Configurazione retention policy...${NC}"
echo "Nota: Per rimanere nel tier gratuito, puoi configurare una retention policy"
echo "      per eliminare automaticamente i dati vecchi."
echo ""
echo "Opzioni:"
echo "  - 90 giorni:  manterrai ~3 mesi di dati"
echo "  - 365 giorni: manterrai 1 anno di dati"
echo "  - 0:          mantieni tutti i dati (default)"
echo ""
read -p "Vuoi configurare una retention policy? [90/365/0 per nessuna retention] (default=0): " RETENTION
RETENTION=${RETENTION:-0}

if [ "$RETENTION" != "0" ]; then
    # Converti giorni in millisecondi
    RETENTION_MS=$((RETENTION * 24 * 60 * 60 * 1000))

    bq update \
        --time_partitioning_expiration="$RETENTION_MS" \
        "$PROJECT_ID:$DATASET_ID.$TABLE_ID"

    echo -e "${GREEN}✓ Retention policy configurata: $RETENTION giorni${NC}"
else
    echo -e "${YELLOW}Nessuna retention policy configurata (dati mantenuti indefinitamente)${NC}"
fi

# Informazioni sul tier gratuito
echo ""
echo -e "${GREEN}=== Tier Gratuito BigQuery ===${NC}"
echo "✓ Storage: 10 GB al mese (primi 10 GB)"
echo "✓ Query: 1 TB al mese (primi 1 TB di dati processati)"
echo "✓ Streaming inserts: primi 1 GB al mese"
echo ""
echo "Con un dispositivo HPSU che invia dati ogni 30 secondi:"
echo "  - ~2,880 record/giorno"
echo "  - ~86,400 record/mese"
echo "  - ~2-3 MB/mese di storage"
echo "  ➜ Ben sotto il limite gratuito!"
echo ""

# Mostra comando per query di test
echo -e "${GREEN}=== Test Query ===${NC}"
echo "Per testare la tabella, esegui:"
echo ""
echo "  bq query --use_legacy_sql=false \\"
echo "    'SELECT * FROM \`$PROJECT_ID.$DATASET_ID.$TABLE_ID\` LIMIT 10'"
echo ""

echo -e "${GREEN}✓ Setup completato!${NC}"
echo ""
echo "Next steps:"
echo "  1. Deploy della Cloud Function (vedi cloud-function/deploy.sh)"
echo "  2. Configura e avvia pyHPSU per inviare dati"
echo "  3. Monitora i dati in arrivo con la query di test sopra"
echo ""
