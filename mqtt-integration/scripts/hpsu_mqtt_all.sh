#!/bin/bash

# Script per crontab - legge TUTTI i parametri ogni volta
# Configurazione MQTT
MQTT_HOST="192.168.0.106"  # Modifica con l'IP del tuo container/rete
MQTT_PORT="1883"
MQTT_BASE_TOPIC="rotex"

# Funzione per estrarre il valore dal JSON output di pyHPSU
extract_value() {
    local param="$1"
    local output

    # Esegui pyHPSU e cattura l'output
    output=$(pyHPSU.py -c "$param" 2>/dev/null)

    # Estrai il valore gestendo sia stringhe che numeri
    echo "$output" | sed -n "s/.*'resp': '\([^']*\)'.*/\1/p; s/.*'resp': \([0-9.-]*\).*/\1/p" | head -1
}

# Funzione per pubblicare un parametro su MQTT
publish_param() {
    local param="$1"
    local value

    echo "Leggendo $param..."
    value=$(extract_value "$param")

    if [ -n "$value" ]; then
        topic="${MQTT_BASE_TOPIC}/${param}"
        mosquitto_pub -h "$MQTT_HOST" -p "$MQTT_PORT" -t "$topic" -m "$value"
        echo "Pubblicato: $topic = $value"
    else
        echo "Errore nella lettura di $param"
    fi
}

# Lista dei parametri da leggere
PARAMS=(
    "flow_rate"
    "t_v1"
    "t_dhw1"
    "pump"
    "t_ext"
    "water_pressure"
)

# Log inizio
echo "$(date): Inizio lettura parametri HPSU"

# Leggi e pubblica tutti i parametri
for param in "${PARAMS[@]}"; do
    publish_param "$param"
    sleep 0.5  # Piccola pausa tra le letture per non sovraccaricare il CAN bus
done

echo "$(date): Completato - tutti i parametri pubblicati"