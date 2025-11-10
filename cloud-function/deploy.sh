#!/bin/bash

# Script per deployare Cloud Function per HPSU telemetry
# Ottimizzato per rimanere nel tier gratuito

set -e  # Exit on error

# Colori per output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configurazione (MODIFICA QUESTI VALORI)
PROJECT_ID="${1:-your-project-id}"
REGION="${2:-europe-west1}"  # Scegli la region più vicina
FUNCTION_NAME="hpsu-to-bigquery"
TOPIC_ID="hpsu-telemetry"
DATASET_ID="hpsu_data"
TABLE_ID="telemetry"

# Impostazioni per minimizzare i costi
MEMORY="256MB"           # Minimo per Python (tier gratuito)
TIMEOUT="60s"            # 60 secondi dovrebbero bastare
MAX_INSTANCES="1"        # Limita le istanze parallele
MIN_INSTANCES="0"        # Nessuna istanza sempre attiva (scaling to zero)
GEN="2"                  # Usa Gen 2 (più efficiente)

echo -e "${GREEN}=== Deploy Cloud Function per HPSU Telemetry ===${NC}"
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
    echo "Uso: $0 <project-id> [region]"
    echo "Esempio: $0 my-hpsu-project europe-west1"
    exit 1
fi

echo -e "${YELLOW}Project ID:${NC} $PROJECT_ID"
echo -e "${YELLOW}Region:${NC} $REGION"
echo -e "${YELLOW}Function Name:${NC} $FUNCTION_NAME"
echo -e "${YELLOW}Pub/Sub Topic:${NC} $TOPIC_ID"
echo -e "${YELLOW}Generation:${NC} $GEN"
echo -e "${YELLOW}Memory:${NC} $MEMORY"
echo -e "${YELLOW}Timeout:${NC} $TIMEOUT"
echo ""

# Imposta il progetto corrente
echo "Setting project to $PROJECT_ID..."
gcloud config set project "$PROJECT_ID"

# Abilita le API necessarie
echo ""
echo -e "${GREEN}Abilitazione API necessarie...${NC}"
gcloud services enable cloudfunctions.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com  # Necessario per Gen 2
gcloud services enable eventarc.googleapis.com  # Necessario per Gen 2

# Verifica che il topic Pub/Sub esista
echo ""
echo -e "${GREEN}Verifica topic Pub/Sub...${NC}"
if gcloud pubsub topics describe "$TOPIC_ID" &> /dev/null; then
    echo -e "${GREEN}✓ Topic $TOPIC_ID trovato${NC}"
else
    echo -e "${RED}Errore: Topic $TOPIC_ID non trovato${NC}"
    echo "Crea il topic prima con:"
    echo "  gcloud pubsub topics create $TOPIC_ID"
    exit 1
fi

# Verifica che il dataset BigQuery esista
echo ""
echo -e "${GREEN}Verifica dataset BigQuery...${NC}"
if bq ls "$PROJECT_ID:$DATASET_ID" &> /dev/null; then
    echo -e "${GREEN}✓ Dataset $DATASET_ID trovato${NC}"
else
    echo -e "${RED}Errore: Dataset $DATASET_ID non trovato${NC}"
    echo "Crea il dataset prima con:"
    echo "  cd bigquery && ./create_dataset.sh $PROJECT_ID"
    exit 1
fi

# Verifica che i file necessari esistano
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ ! -f "$SCRIPT_DIR/main.py" ]; then
    echo -e "${RED}Errore: main.py non trovato${NC}"
    exit 1
fi

if [ ! -f "$SCRIPT_DIR/requirements.txt" ]; then
    echo -e "${RED}Errore: requirements.txt non trovato${NC}"
    exit 1
fi

# Aggiorna main.py con PROJECT_ID corretto
echo ""
echo -e "${GREEN}Aggiornamento configurazione in main.py...${NC}"
sed -i.bak "s/PROJECT_ID = \".*\"/PROJECT_ID = \"$PROJECT_ID\"/" "$SCRIPT_DIR/main.py"
sed -i.bak "s/DATASET_ID = \".*\"/DATASET_ID = \"$DATASET_ID\"/" "$SCRIPT_DIR/main.py"
sed -i.bak "s/TABLE_ID = \".*\"/TABLE_ID = \"$TABLE_ID\"/" "$SCRIPT_DIR/main.py"
echo -e "${GREEN}✓ Configurazione aggiornata${NC}"

# Deploy della function
echo ""
echo -e "${GREEN}Deploy della Cloud Function...${NC}"
echo "Questo può richiedere alcuni minuti..."
echo ""

if [ "$GEN" == "2" ]; then
    # Deploy Gen 2
    gcloud functions deploy "$FUNCTION_NAME" \
        --gen2 \
        --runtime=python311 \
        --region="$REGION" \
        --source="$SCRIPT_DIR" \
        --entry-point=hpsu_to_bigquery \
        --trigger-topic="$TOPIC_ID" \
        --memory="$MEMORY" \
        --timeout="$TIMEOUT" \
        --max-instances="$MAX_INSTANCES" \
        --min-instances="$MIN_INSTANCES" \
        --no-allow-unauthenticated \
        --set-env-vars="PROJECT_ID=$PROJECT_ID,DATASET_ID=$DATASET_ID,TABLE_ID=$TABLE_ID"
else
    # Deploy Gen 1
    gcloud functions deploy "$FUNCTION_NAME" \
        --runtime=python311 \
        --region="$REGION" \
        --source="$SCRIPT_DIR" \
        --entry-point=pubsub_to_bigquery \
        --trigger-topic="$TOPIC_ID" \
        --memory="$MEMORY" \
        --timeout="$TIMEOUT" \
        --max-instances="$MAX_INSTANCES" \
        --no-allow-unauthenticated \
        --set-env-vars="PROJECT_ID=$PROJECT_ID,DATASET_ID=$DATASET_ID,TABLE_ID=$TABLE_ID"
fi

echo ""
echo -e "${GREEN}✓ Deploy completato!${NC}"
echo ""

# Mostra informazioni sulla function
echo -e "${GREEN}=== Informazioni Cloud Function ===${NC}"
gcloud functions describe "$FUNCTION_NAME" --region="$REGION" --gen2 2>/dev/null || \
    gcloud functions describe "$FUNCTION_NAME" --region="$REGION"

# Test della function
echo ""
echo -e "${GREEN}=== Test della Function ===${NC}"
echo "Per testare la function, pubblica un messaggio di test su Pub/Sub:"
echo ""
echo "  gcloud pubsub topics publish $TOPIC_ID --message='{\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%S.%6N+00:00)\",\"device_id\":\"test-device\",\"measurements\":{\"t_hs\":\"32.5\",\"t_dhw\":\"45.0\"}}'"
echo ""
echo "Poi controlla i log:"
echo ""
echo "  gcloud functions logs read $FUNCTION_NAME --region=$REGION --limit=50"
echo ""

# Informazioni sul tier gratuito
echo -e "${GREEN}=== Tier Gratuito Cloud Functions ===${NC}"
echo "✓ Invocazioni: 2 milioni al mese"
echo "✓ Compute time: 400,000 GB-seconds al mese"
echo "✓ Networking: 5 GB egress al mese"
echo ""
echo "Con un dispositivo HPSU che invia dati ogni 30 secondi:"
echo "  - ~2,880 invocazioni/giorno"
echo "  - ~86,400 invocazioni/mese"
echo "  - ~1.7 GB-seconds/mese (256MB memory * 60s timeout * 2880)"
echo "  ➜ Ben sotto il limite gratuito!"
echo ""

echo -e "${GREEN}✓ Setup completato!${NC}"
echo ""
echo "Next steps:"
echo "  1. Testa la function con il comando sopra"
echo "  2. Controlla i log per verificare che funzioni"
echo "  3. Avvia pyHPSU per iniziare a inviare dati reali"
echo "  4. Monitora i dati in BigQuery"
echo ""

# Cleanup
rm -f "$SCRIPT_DIR/main.py.bak"
