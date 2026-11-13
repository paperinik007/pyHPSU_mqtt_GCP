#!/bin/bash

# Script parametrico per invio dati HPSU via MQTT
# Uso: ./hpsu_mqtt_custom.sh <MQTT_HOST> <MQTT_PORT> <TOPIC>
# Esempio: ./hpsu_mqtt_custom.sh 192.168.1.100 1883 hpsu/data

# Controllo parametri
if [ $# -ne 3 ]; then
    echo "Uso: $0 <MQTT_HOST> <MQTT_PORT> <TOPIC>"
    echo "Esempio: $0 192.168.1.100 1883 hpsu/data"
    exit 1
fi

# Configurazione MQTT da parametri
MQTT_HOST="$1"
MQTT_PORT="$2"
MQTT_TOPIC="$3"

# Log inizio
echo "$(date): Inizio lettura parametri HPSU verso $MQTT_HOST:$MQTT_PORT"

# Esegui pyHPSU con tutti i parametri e cattura l'output completo
payload=$(pyHPSU.py -c flow_rate -c posmix -c bpv -c t_v1 -c t_dhw1 -c t_r1 -c pump -c ehs -c mode -c t_hc_set -c t_dhw_set -c t_vbh -c t_ext -c water_pressure -c tdhw2 2>/dev/null | sed "s/'/\"/g")

# Verifica se il payload è valido
if [ -n "$payload" ]; then
    # Pubblica l'intero payload JSON sul topic specificato
    mosquitto_pub -h "$MQTT_HOST" -p "$MQTT_PORT" -t "$MQTT_TOPIC" -m "$payload"
    echo "Pubblicato payload completo su: $MQTT_TOPIC"
    echo "Payload: $payload"
else
    echo "Errore: payload vuoto o comando fallito"
    exit 1
fi

echo "$(date): Completato - payload pubblicato su $MQTT_TOPIC"
