#!/bin/bash

# Script di test per verificare il funzionamento dell'integrazione MQTT

echo "=== Test MQTT Integration pyHPSU ==="
echo

# Verifica prerequisiti
echo "🔍 Verifica prerequisiti..."

# Verifica pyHPSU
if command -v pyHPSU.py &> /dev/null; then
    echo "✅ pyHPSU.py trovato"
else
    echo "❌ pyHPSU.py non trovato - installare prima pyHPSU"
    exit 1
fi

# Verifica mosquitto clients
if command -v mosquitto_pub &> /dev/null; then
    echo "✅ mosquitto-clients installati"
else
    echo "❌ mosquitto-clients non installati"
    exit 1
fi

# Verifica Docker
if command -v docker &> /dev/null; then
    echo "✅ Docker installato"
else
    echo "❌ Docker non installato"
    exit 1
fi

# Verifica script principale
SCRIPT_PATH="$HOME/hpsu_mqtt_all.sh"
if [ -x "$SCRIPT_PATH" ]; then
    echo "✅ Script $SCRIPT_PATH trovato ed eseguibile"
else
    echo "❌ Script $SCRIPT_PATH non trovato o non eseguibile"
    exit 1
fi

echo

# Test connessione HPSU
echo "🔧 Test connessione HPSU..."
if timeout 10 pyHPSU.py -c t_ext >/dev/null 2>&1; then
    echo "✅ Connessione HPSU funzionante"
else
    echo "⚠️  Possibili problemi di connessione HPSU"
    echo "   Verifica la connessione CAN e la configurazione"
fi

echo

# Verifica container Mosquitto
echo "🐳 Verifica container Mosquitto..."
if docker ps | grep -q mosquitto; then
    echo "✅ Container Mosquitto in esecuzione"
    
    # Estrai l'IP dal container
    CONTAINER_IP=$(docker inspect mosquitto | grep '"IPAddress"' | tail -1 | cut -d'"' -f4)
    
    # Prova anche con l'IP dell'host
    HOST_IP=$(hostname -I | awk '{print $1}')
    
    echo "   IP container: $CONTAINER_IP"
    echo "   IP host: $HOST_IP"
    
    # Test connessione MQTT
    echo
    echo "📡 Test connessione MQTT..."
    
    # Test con IP host
    if timeout 5 mosquitto_pub -h "$HOST_IP" -t "test/connection" -m "test_$(date)" -d 2>/dev/null; then
        echo "✅ Connessione MQTT funzionante (IP host: $HOST_IP)"
        MQTT_IP="$HOST_IP"
    elif timeout 5 mosquitto_pub -h "localhost" -t "test/connection" -m "test_$(date)" -d 2>/dev/null; then
        echo "✅ Connessione MQTT funzionante (localhost)"
        MQTT_IP="localhost"
    else
        echo "❌ Problemi di connessione MQTT"
        echo "   Verifica che il container sia avviato e i port forwarding siano corretti"
    fi
else
    echo "❌ Container Mosquitto non in esecuzione"
    echo "   Avvia con: cd ~/hpsu-mqtt/docker && docker-compose up -d"
fi

echo

# Test script completo
if [ -n "$MQTT_IP" ]; then
    echo "🚀 Test script completo..."
    
    # Aggiorna l'IP nello script se necessario
    sed -i "s/MQTT_HOST=\".*\"/MQTT_HOST=\"$MQTT_IP\"/" "$SCRIPT_PATH"
    
    echo "Esecuzione test (timeout 30s)..."
    if timeout 30 "$SCRIPT_PATH"; then
        echo "✅ Script eseguito con successo"
        
        # Verifica che i messaggi siano stati pubblicati
        echo
        echo "📊 Verifica messaggi pubblicati (timeout 5s)..."
        timeout 5 mosquitto_sub -h "$MQTT_IP" -t "rotex/+" -C 6 | while read -r line; do
            echo "   Ricevuto: $line"
        done
        
    else
        echo "❌ Errore durante l'esecuzione dello script"
    fi
fi

echo

# Verifica crontab
echo "⏰ Verifica crontab..."
if crontab -l 2>/dev/null | grep -q "hpsu_mqtt_all.sh"; then
    echo "✅ Crontab configurato correttamente"
    echo "   $(crontab -l | grep hpsu_mqtt_all.sh)"
else
    echo "⚠️  Crontab non configurato"
    echo "   Aggiungi manualmente: * * * * * $HOME/hpsu_mqtt_all.sh >/dev/null 2>&1"
fi

echo
echo "=== Riepilogo Test ==="
echo "📱 Per configurare MQTT Dash:"
echo "   Server: $MQTT_IP"
echo "   Porta: 1883"
echo "   Topic esempi:"
echo "   - rotex/flow_rate (Portata)"
echo "   - rotex/t_ext (Temperatura esterna)"
echo "   - rotex/t_v1 (Temperatura mandata)"
echo "   - rotex/water_pressure (Pressione acqua)"
echo
echo "🔧 Comandi utili:"
echo "   - Monitoraggio real-time: mosquitto_sub -h $MQTT_IP -t 'rotex/+'"
echo "   - Test manuale: $HOME/hpsu_mqtt_all.sh"
echo "   - Log container: docker logs mosquitto"