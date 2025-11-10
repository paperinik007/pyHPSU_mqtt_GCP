#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Plugin MQTT per pyHPSU - Versione aggiornata con Google Cloud Pub/Sub

Questo plugin invia i dati della pompa di calore a Google Cloud Pub/Sub.
Google Cloud IoT Core è stato deprecato il 16 agosto 2023.

Requisiti:
- pip install google-cloud-pubsub
- Autenticazione tramite Service Account JSON

Configurazione in pyhpsu.conf:
[MQTT]
# Configurazione locale MQTT (opzionale)
BROKER = localhost
PORT = 1883
CLIENTNAME = rotex_hpsu
PREFIX = rotex
QOS = 0

[GCP_PUBSUB]
# Configurazione Google Cloud Pub/Sub
PROJECT_ID = your-project-id
TOPIC_ID = your-topic-id
# Percorso al file JSON del service account
CREDENTIALS_FILE = /path/to/service-account.json
# Opzionale: abilita pubblicazione su GCP (true/false)
ENABLED = true
"""

import configparser
import datetime
import json
import logging
import os
import sys
from typing import Optional, Dict, Any

# Import per MQTT locale (opzionale)
try:
    import paho.mqtt.client as mqtt
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False
    logging.warning("paho-mqtt non disponibile. Funzionalità MQTT locale disabilitata.")

# Import per Google Cloud Pub/Sub
try:
    from google.cloud import pubsub_v1
    from google.oauth2 import service_account
    PUBSUB_AVAILABLE = True
except ImportError:
    PUBSUB_AVAILABLE = False
    logging.warning("google-cloud-pubsub non disponibile. Funzionalità GCP Pub/Sub disabilitata.")

# Configurazione logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class export():
    """Classe per esportare i dati HPSU via MQTT locale e/o Google Cloud Pub/Sub"""

    def __init__(self, hpsu=None, logger=None, config_file=None):
        """
        Inizializza l'exporter MQTT/Pub/Sub

        Args:
            hpsu: Istanza HPSU
            logger: Logger personalizzato (opzionale)
            config_file: Percorso al file di configurazione
        """
        self.hpsu = hpsu
        self.logger = logger or logging.getLogger(__name__)
        self.config_file = config_file
        self.config = configparser.ConfigParser()

        if not os.path.isfile(self.config_file):
            self.logger.error(f"File di configurazione non trovato: {self.config_file}")
            sys.exit(9)

        self.config.read(self.config_file)

        # Inizializza MQTT locale
        self._init_local_mqtt()

        # Inizializza Google Cloud Pub/Sub
        self._init_gcp_pubsub()

    def _init_local_mqtt(self):
        """Inizializza il client MQTT locale (opzionale)"""
        self.mqtt_enabled = False
        self.mqtt_client = None

        if not MQTT_AVAILABLE:
            self.logger.info("MQTT locale non disponibile (paho-mqtt non installato)")
            return

        if not self.config.has_section('MQTT'):
            self.logger.info("Sezione [MQTT] non presente nel config. MQTT locale disabilitato.")
            return

        # Configurazione MQTT locale
        self.brokerhost = self.config.get('MQTT', 'BROKER', fallback='localhost')
        self.brokerport = self.config.getint('MQTT', 'PORT', fallback=1883)
        self.clientname = self.config.get('MQTT', 'CLIENTNAME', fallback='rotex_hpsu')
        self.prefix = self.config.get('MQTT', 'PREFIX', fallback='rotex')
        self.qos = self.config.getint('MQTT', 'QOS', fallback=0)

        try:
            self.mqtt_client = mqtt.Client(self.clientname)
            self.mqtt_enabled = True
            self.logger.info(f"MQTT locale configurato: {self.brokerhost}:{self.brokerport}")
        except Exception as e:
            self.logger.error(f"Errore inizializzazione MQTT locale: {e}")

    def _init_gcp_pubsub(self):
        """Inizializza Google Cloud Pub/Sub"""
        self.pubsub_enabled = False
        self.publisher = None
        self.topic_path = None

        if not PUBSUB_AVAILABLE:
            self.logger.warning("Google Cloud Pub/Sub non disponibile (google-cloud-pubsub non installato)")
            self.logger.warning("Installa con: pip install google-cloud-pubsub")
            return

        if not self.config.has_section('GCP_PUBSUB'):
            self.logger.info("Sezione [GCP_PUBSUB] non presente nel config. Pub/Sub disabilitato.")
            return

        # Verifica se Pub/Sub è abilitato
        enabled = self.config.get('GCP_PUBSUB', 'ENABLED', fallback='false')
        if enabled.lower() not in ['true', '1', 'yes']:
            self.logger.info("GCP Pub/Sub disabilitato nella configurazione")
            return

        # Leggi configurazione
        project_id = self.config.get('GCP_PUBSUB', 'PROJECT_ID', fallback=None)
        topic_id = self.config.get('GCP_PUBSUB', 'TOPIC_ID', fallback=None)
        credentials_file = self.config.get('GCP_PUBSUB', 'CREDENTIALS_FILE', fallback=None)

        if not project_id or not topic_id:
            self.logger.error("PROJECT_ID e TOPIC_ID sono obbligatori in [GCP_PUBSUB]")
            return

        try:
            # Inizializza il publisher con o senza credentials file
            if credentials_file and os.path.exists(credentials_file):
                credentials = service_account.Credentials.from_service_account_file(credentials_file)
                self.publisher = pubsub_v1.PublisherClient(credentials=credentials)
                self.logger.info(f"Pub/Sub autenticato con service account: {credentials_file}")
            else:
                # Usa le Application Default Credentials (ADC)
                self.publisher = pubsub_v1.PublisherClient()
                self.logger.info("Pub/Sub usa Application Default Credentials")

            self.topic_path = self.publisher.topic_path(project_id, topic_id)
            self.pubsub_enabled = True
            self.logger.info(f"GCP Pub/Sub configurato: {self.topic_path}")

        except Exception as e:
            self.logger.error(f"Errore inizializzazione Google Cloud Pub/Sub: {e}")
            self.logger.error("Verifica che il service account abbia i permessi 'pubsub.publisher'")

    def pushValues(self, vars=None):
        """
        Pubblica i valori su MQTT locale e/o Google Cloud Pub/Sub

        Args:
            vars: Lista di dizionari con 'name' e 'resp'
        """
        if not vars:
            self.logger.warning("Nessun valore da pubblicare")
            return

        # Costruisce il payload JSON
        timestamp = datetime.datetime.now(datetime.timezone.utc)

        # Formato payload
        payload = {
            "timestamp": timestamp.isoformat(),
            "device_id": self.config.get('GCP_PUBSUB', 'DEVICE_ID', fallback='hpsu_device'),
            "measurements": {}
        }

        for item in vars:
            if 'name' in item and 'resp' in item:
                payload["measurements"][item['name']] = str(item['resp'])

        # Converte in JSON string
        payload_str = json.dumps(payload, ensure_ascii=False)

        # Log del payload
        self.logger.info(f"Payload da pubblicare: {payload_str}")

        # Pubblica su MQTT locale
        if self.mqtt_enabled:
            self._publish_mqtt_local(payload_str)

        # Pubblica su Google Cloud Pub/Sub
        if self.pubsub_enabled:
            self._publish_pubsub(payload_str, payload)

    def _publish_mqtt_local(self, payload_str: str):
        """Pubblica su broker MQTT locale"""
        try:
            if not self.mqtt_client:
                return

            # Connetti al broker
            self.mqtt_client.connect(self.brokerhost, self.brokerport, 60)

            # Pubblica il messaggio
            topic = f"{self.prefix}/hpsu/data"
            result = self.mqtt_client.publish(topic, payload_str, qos=self.qos)

            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                self.logger.info(f"Pubblicato su MQTT locale: {topic}")
            else:
                self.logger.error(f"Errore pubblicazione MQTT: {result.rc}")

            self.mqtt_client.disconnect()

        except Exception as e:
            self.logger.error(f"Errore pubblicazione MQTT locale: {e}")

    def _publish_pubsub(self, payload_str: str, payload_dict: Dict[str, Any]):
        """Pubblica su Google Cloud Pub/Sub"""
        try:
            if not self.publisher or not self.topic_path:
                return

            # Converti il payload in bytes
            data = payload_str.encode('utf-8')

            # Aggiungi attributi del messaggio (opzionale, utile per filtering)
            attributes = {
                "device_id": payload_dict.get("device_id", "unknown"),
                "timestamp": payload_dict.get("timestamp", ""),
                "source": "pyHPSU"
            }

            # Pubblica il messaggio
            future = self.publisher.publish(
                self.topic_path,
                data,
                **attributes
            )

            # Attendi la conferma (opzionale, commentare per operazione asincrona)
            message_id = future.result(timeout=10)

            self.logger.info(f"Pubblicato su Pub/Sub - Message ID: {message_id}")

        except Exception as e:
            self.logger.error(f"Errore pubblicazione Google Cloud Pub/Sub: {e}")
            import traceback
            self.logger.error(traceback.format_exc())


# Funzione di test
def test_pubsub():
    """Funzione di test per verificare la configurazione"""
    import sys

    if len(sys.argv) < 2:
        print("Uso: python mqtt.py <config_file>")
        sys.exit(1)

    config_file = sys.argv[1]

    # Crea un'istanza del plugin
    exporter = export(hpsu=None, logger=None, config_file=config_file)

    # Dati di test
    test_data = [
        {"name": "t_hs", "resp": "32.5"},
        {"name": "t_dhw", "resp": "45.0"},
        {"name": "water_pressure", "resp": "1.8"},
    ]

    # Pubblica i dati di test
    print("\nTest pubblicazione dati...")
    exporter.pushValues(test_data)
    print("\nTest completato!")


if __name__ == "__main__":
    test_pubsub()
