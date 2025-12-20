#!/bin/bash

# Script di installazione automatica per MQTT Integration pyHPSU
# Installa Docker, Docker Compose e configura l'ambiente MQTT

set -e

echo "=== Installazione MQTT Integration per pyHPSU ==="
echo "Questo script installerà:"
echo "- Docker e Docker Compose"
echo "- Client MQTT (mosquitto-clients)"
echo "- Configurazione container Mosquitto"
echo "- Script di monitoraggio HPSU"
echo "- Configurazione automatica crontab"
echo

# Verifica che sia eseguito come root
if [[ $EUID -eq 0 ]]; then
   echo "Questo script non deve essere eseguito come root. Usa sudo solo quando necessario."
   exit 1
fi

# Funzione per rilevare l'IP della macchina locale
detect_local_ip() {
    # Prova diversi metodi per ottenere l'IP locale
    local ip
    ip=$(hostname -I | awk '{print $1}' 2>/dev/null) || \
    ip=$(ip route get 1 | awk '{print $7; exit}' 2>/dev/null) || \
    ip=$(ifconfig | grep -Eo 'inet (addr:)?([0-9]*\.){3}[0-9]*' | grep -Eo '([0-9]*\.){3}[0-9]*' | grep -v '127.0.0.1' | head -1 2>/dev/null) || \
    ip="192.168.1.100"  # fallback
    echo "$ip"
}

# Sistema già aggiornato - evitare update automatici per problemi di compatibilità
echo "Verifica dipendenze..."

# Installa Docker se non presente
if ! command -v docker &> /dev/null; then
    echo "Installazione Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    rm get-docker.sh
    echo "Docker installato. Potrebbe essere necessario riavviare per applicare i permessi di gruppo."
else
    echo "Docker già installato"
fi

# Installa Docker Compose se non presente
if ! command -v docker-compose &> /dev/null; then
    echo "Installazione Docker Compose..."
    sudo apt install -y docker-compose
else
    echo "Docker Compose già installato"
fi

# Installa client MQTT
if ! command -v mosquitto_pub &> /dev/null; then
    echo "Installazione mosquitto-clients..."
    sudo apt install -y mosquitto-clients
else
    echo "mosquitto-clients già installato"
fi

# Abilita Docker al boot
sudo systemctl enable docker

# Rileva l'IP locale automaticamente
LOCAL_IP=$(detect_local_ip)
echo "IP locale rilevato: $LOCAL_IP"

# Crea directory di lavoro
WORK_DIR="$HOME/hpsu-mqtt"
echo "Creazione directory di lavoro: $WORK_DIR"
mkdir -p "$WORK_DIR"

# Copia e configura gli script
echo "Copia e configurazione degli script..."
cp "$(dirname "$0")/hpsu_mqtt_all.sh" "$HOME/"

# Aggiorna automaticamente l'IP nello script
sed -i "s/MQTT_HOST=\".*\"/MQTT_HOST=\"$LOCAL_IP\"/" "$HOME/hpsu_mqtt_all.sh"
chmod +x "$HOME/hpsu_mqtt_all.sh"

# Crea directory per Docker Compose
mkdir -p "$WORK_DIR/docker"
cp "$(dirname "$0")/../docker/docker-compose.yml" "$WORK_DIR/docker/"
cp "$(dirname "$0")/../docker/mosquitto.conf" "$WORK_DIR/docker/"

# Crea directory per volumi Mosquitto
mkdir -p "$WORK_DIR/docker/volumes/mosquitto/"{config,data,log,pwfile}
# Copia il file di configurazione
cp "$WORK_DIR/docker/mosquitto.conf" "$WORK_DIR/docker/volumes/mosquitto/config/"

echo "Configurazione automatica completata!"
echo "IP configurato: $LOCAL_IP"

# Chiedi conferma per avviare i servizi
read -p "Vuoi avviare automaticamente il container Mosquitto? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Avvio container Mosquitto..."
    cd "$WORK_DIR/docker"
    docker-compose up -d
    echo "Container Mosquitto avviato!"
    
    # Attendi che il container sia pronto
    sleep 3
    
    # Testa la connessione MQTT
    echo "Test connessione MQTT..."
    if mosquitto_pub -h "$LOCAL_IP" -t "test/connection" -m "hello" -d; then
        echo "✅ Connessione MQTT funzionante!"
    else
        echo "⚠️  Possibili problemi di connessione MQTT"
    fi
fi

# Chiedi conferma per configurare il crontab
read -p "Vuoi configurare automaticamente il crontab per l'esecuzione ogni minuto? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Backup del crontab attuale
    crontab -l > /tmp/crontab_backup_$(date +%Y%m%d_%H%M%S) 2>/dev/null || true
    
    # Verifica se la riga esiste già
    if crontab -l 2>/dev/null | grep -q "hpsu_mqtt_all.sh"; then
        echo "Configurazione crontab già presente, aggiornamento..."
        # Rimuovi righe esistenti e aggiungi la nuova
        (crontab -l 2>/dev/null | grep -v "hpsu_mqtt_all.sh"; echo "* * * * * $HOME/hpsu_mqtt_all.sh >/dev/null 2>&1") | crontab -
    else
        echo "Aggiunta configurazione crontab..."
        (crontab -l 2>/dev/null; echo "* * * * * $HOME/hpsu_mqtt_all.sh >/dev/null 2>&1") | crontab -
    fi
    echo "✅ Crontab configurato per esecuzione ogni minuto"
fi

echo
echo "🎉 === Installazione completata ==="
echo "Configurazione:"
echo "  - IP broker MQTT: $LOCAL_IP"
echo "  - Script principale: $HOME/hpsu_mqtt_all.sh"
echo "  - Directory Docker: $WORK_DIR/docker"
echo
echo "Comandi utili:"
echo "  - Test manuale: $HOME/hpsu_mqtt_all.sh"
echo "  - Monitoraggio MQTT: mosquitto_sub -h $LOCAL_IP -t 'rotex/+'"
echo "  - Stato container: docker ps"
echo "  - Log container: docker logs mosquitto"
echo "  - Crontab attuale: crontab -l"
echo
echo "📱 Per MQTT Dash configura:"
echo "  - Server: $LOCAL_IP"
echo "  - Porta: 1883"  
echo "  - Topic: rotex/flow_rate, rotex/t_ext, ecc."