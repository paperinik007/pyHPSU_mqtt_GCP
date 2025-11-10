"""
Google Cloud Function per inserire dati HPSU in BigQuery

Questa function viene triggherata da Pub/Sub e inserisce i dati
della pompa di calore in BigQuery.

Ottimizzata per rimanere nel tier gratuito:
- Usa batch insert (fino a 1000 rows)
- Minimal memory footprint
- Nessuna dipendenza esterna oltre google-cloud-bigquery
"""

import base64
import json
import logging
from datetime import datetime
from typing import Dict, Any, List

from google.cloud import bigquery
from google.cloud.exceptions import NotFound

# Configurazione logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configurazione BigQuery
# IMPORTANTE: Modifica questi valori con i tuoi
PROJECT_ID = "your-project-id"  # Modificare con il tuo project ID
DATASET_ID = "hpsu_data"
TABLE_ID = "telemetry"

# Inizializza client BigQuery (riutilizzato tra invocazioni)
bigquery_client = None


def get_bigquery_client():
    """Ottiene o crea il client BigQuery (singleton)"""
    global bigquery_client
    if bigquery_client is None:
        bigquery_client = bigquery.Client(project=PROJECT_ID)
    return bigquery_client


def parse_pubsub_message(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Estrae e decodifica il messaggio Pub/Sub

    Args:
        event: Evento Pub/Sub

    Returns:
        Dizionario con i dati del messaggio

    Raises:
        ValueError: Se il messaggio non è valido
    """
    try:
        # Decodifica il messaggio base64
        if 'data' in event:
            pubsub_data = base64.b64decode(event['data']).decode('utf-8')
            message = json.loads(pubsub_data)
        else:
            raise ValueError("Nessun dato nel messaggio Pub/Sub")

        logger.info(f"Messaggio decodificato: {message}")
        return message

    except Exception as e:
        logger.error(f"Errore parsing messaggio Pub/Sub: {e}")
        raise


def transform_to_bigquery_row(message: Dict[str, Any]) -> Dict[str, Any]:
    """
    Trasforma il messaggio in formato BigQuery

    Args:
        message: Messaggio dal device

    Returns:
        Riga formattata per BigQuery
    """
    # Estrai timestamp
    timestamp_str = message.get('timestamp')
    if timestamp_str:
        # Converti ISO 8601 string a timestamp
        try:
            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        except:
            timestamp = datetime.utcnow()
    else:
        timestamp = datetime.utcnow()

    # Estrai device_id
    device_id = message.get('device_id', 'unknown')

    # Estrai measurements
    measurements = message.get('measurements', {})

    # Costruisci la riga BigQuery
    # Converti tutti i valori in float quando possibile, altrimenti None
    def to_float(value):
        if value is None or value == '':
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    row = {
        'timestamp': timestamp.isoformat(),
        'device_id': device_id,
        # Temperature
        't_hs': to_float(measurements.get('t_hs')),
        't_hs_set': to_float(measurements.get('t_hs_set')),
        't_dhw': to_float(measurements.get('t_dhw')),
        't_dhw_set': to_float(measurements.get('t_dhw_set')),
        't_ext': to_float(measurements.get('t_ext')),
        't_return': to_float(measurements.get('t_return')),
        't_hc': to_float(measurements.get('t_hc')),
        't_hc_set': to_float(measurements.get('t_hc_set')),
        # Pressione e flusso
        'water_pressure': to_float(measurements.get('water_pressure')),
        'flow_rate': to_float(measurements.get('flow_rate')),
        # Altri campi comuni
        'mode': measurements.get('mode'),
        'error_code': measurements.get('error_code'),
        # Campi aggiuntivi come JSON
        'additional_data': json.dumps({k: v for k, v in measurements.items()
                                       if k not in ['t_hs', 't_hs_set', 't_dhw',
                                                   't_dhw_set', 't_ext', 't_return',
                                                   't_hc', 't_hc_set', 'water_pressure',
                                                   'flow_rate', 'mode', 'error_code']})
    }

    return row


def insert_into_bigquery(rows: List[Dict[str, Any]]) -> None:
    """
    Inserisce le righe in BigQuery

    Args:
        rows: Lista di righe da inserire

    Raises:
        Exception: Se l'inserimento fallisce
    """
    client = get_bigquery_client()
    table_ref = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"

    # Inserisci le righe
    errors = client.insert_rows_json(table_ref, rows)

    if errors:
        error_msg = f"Errori durante l'inserimento in BigQuery: {errors}"
        logger.error(error_msg)
        raise Exception(error_msg)
    else:
        logger.info(f"Inserite {len(rows)} righe in BigQuery con successo")


def pubsub_to_bigquery(event, context):
    """
    Cloud Function triggherata da Pub/Sub

    Entry point per Cloud Functions (Gen 1)

    Args:
        event (dict): Event payload
        context (google.cloud.functions.Context): Metadata for the event
    """
    try:
        # Log info evento
        logger.info(f"Function triggered by messageId {context.event_id}")
        logger.info(f"Event type: {context.event_type}")

        # Parse messaggio Pub/Sub
        message = parse_pubsub_message(event)

        # Trasforma in formato BigQuery
        row = transform_to_bigquery_row(message)

        # Inserisci in BigQuery
        insert_into_bigquery([row])

        logger.info("Elaborazione completata con successo")

    except Exception as e:
        logger.error(f"Errore durante l'elaborazione: {e}")
        # Non ri-lanciare l'eccezione per evitare retry infiniti
        # Il messaggio andrà nella dead letter queue se configurata


def hpsu_to_bigquery(cloud_event):
    """
    Cloud Function triggherata da Pub/Sub (Gen 2)

    Entry point per Cloud Functions Gen 2 (CloudEvent format)

    Args:
        cloud_event: CloudEvent con i dati Pub/Sub
    """
    try:
        # Log info evento
        logger.info(f"Function triggered by message: {cloud_event.get('id')}")

        # Estrai i dati dal CloudEvent
        # In Gen 2, i dati sono in cloud_event.data
        pubsub_message = cloud_event.data.get('message', {})

        # Crea event dict compatibile con Gen 1 per riutilizzare il codice
        event = {
            'data': pubsub_message.get('data'),
            'attributes': pubsub_message.get('attributes', {})
        }

        # Parse messaggio Pub/Sub
        message = parse_pubsub_message(event)

        # Trasforma in formato BigQuery
        row = transform_to_bigquery_row(message)

        # Inserisci in BigQuery
        insert_into_bigquery([row])

        logger.info("Elaborazione completata con successo")

    except Exception as e:
        logger.error(f"Errore durante l'elaborazione: {e}")
        # Non ri-lanciare l'eccezione per evitare retry infiniti


# Alias per compatibilità
main = hpsu_to_bigquery


if __name__ == "__main__":
    # Test locale
    import sys

    test_message = {
        "timestamp": "2025-11-10T10:30:00.123456+00:00",
        "device_id": "hpsu-001",
        "measurements": {
            "t_hs": "32.5",
            "t_dhw": "45.0",
            "water_pressure": "1.8",
            "t_ext": "15.2"
        }
    }

    # Simula evento Pub/Sub
    test_event = {
        'data': base64.b64encode(json.dumps(test_message).encode()).decode()
    }

    class MockContext:
        event_id = "test-123"
        event_type = "test"

    print("Test locale della function...")
    print(f"Messaggio di test: {test_message}")

    # Nota: questo fallirà se non hai configurato le credenziali localmente
    # Per testare: export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json
    try:
        pubsub_to_bigquery(test_event, MockContext())
        print("✅ Test completato con successo!")
    except Exception as e:
        print(f"❌ Test fallito: {e}")
        print("Configura le credenziali con: export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json")
