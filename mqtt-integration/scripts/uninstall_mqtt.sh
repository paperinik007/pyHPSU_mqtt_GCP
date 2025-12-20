#!/bin/bash

# Script di disinstallazione per MQTT Integration pyHPSU

echo "=== Disinstallazione MQTT Integration pyHPSU ==="
echo
echo "⚠️  Questo script rimuoverà:"
echo "   - Container Mosquitto"
echo "   - Script hpsu_mqtt_all.sh"
echo "   - Configurazione crontab"
echo "   - Directory di lavoro hpsu-mqtt"
echo
read -p "Vuoi continuare? (y/N): " -n 1 -r
echo

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Disinstallazione annullata"
    exit 0
fi

# Backup crontab
echo "📋 Backup crontab..."
crontab -l > "/tmp/crontab_backup_before_uninstall_$(date +%Y%m%d_%H%M%S)" 2>/dev/null || true

# Rimuovi da crontab
echo "⏰ Rimozione configurazione crontab..."
if crontab -l 2>/dev/null | grep -q "hpsu_mqtt_all.sh"; then
    (crontab -l 2>/dev/null | grep -v "hpsu_mqtt_all.sh") | crontab -
    echo "✅ Configurazione crontab rimossa"
else
    echo "ℹ️  Nessuna configurazione crontab trovata"
fi

# Ferma e rimuovi container
echo "🐳 Rimozione container Mosquitto..."
if docker ps -a | grep -q mosquitto; then
    docker stop mosquitto 2>/dev/null || true
    docker rm mosquitto 2>/dev/null || true
    echo "✅ Container Mosquitto rimosso"
else
    echo "ℹ️  Container Mosquitto non trovato"
fi

# Rimuovi script
echo "📜 Rimozione script..."
if [ -f "$HOME/hpsu_mqtt_all.sh" ]; then
    rm "$HOME/hpsu_mqtt_all.sh"
    echo "✅ Script $HOME/hpsu_mqtt_all.sh rimosso"
else
    echo "ℹ️  Script non trovato"
fi

# Rimuovi directory di lavoro
WORK_DIR="$HOME/hpsu-mqtt"
if [ -d "$WORK_DIR" ]; then
    read -p "Vuoi rimuovere anche la directory $WORK_DIR con i dati Mosquitto? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$WORK_DIR"
        echo "✅ Directory $WORK_DIR rimossa"
    else
        echo "ℹ️  Directory $WORK_DIR conservata"
    fi
else
    echo "ℹ️  Directory di lavoro non trovata"
fi

# Chiedi se rimuovere Docker e mosquitto-clients
echo
read -p "Vuoi rimuovere anche Docker e mosquitto-clients? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🗑️  Rimozione Docker e mosquitto-clients..."
    sudo apt remove -y docker.io docker-compose mosquitto-clients || true
    sudo apt autoremove -y
    echo "✅ Docker e mosquitto-clients rimossi"
else
    echo "ℹ️  Docker e mosquitto-clients conservati"
fi

echo
echo "🎉 === Disinstallazione completata ==="
echo
echo "📋 File di backup creati:"
echo "   $(ls /tmp/crontab_backup_* 2>/dev/null | tail -1 || echo 'Nessun backup crontab')"
echo
echo "ℹ️  pyHPSU principale non è stato rimosso"
echo "ℹ️  Per reinstallare: ./install_mqtt.sh"