# MQTT Integration for pyHPSU

Questa directory contiene tutto il necessario per integrare pyHPSU con un broker MQTT locale, permettendo la pubblicazione dei valori della pompa di calore su topic MQTT individuali.

## Motivazione

Questa integrazione è stata sviluppata per consentire il monitoraggio dei parametri HPSU tramite un vecchio smartphone utilizzato come display dedicato, con l'app **MQTT Dash** che permette di visualizzare agevolmente i valori in tempo reale dal broker Mosquitto. La soluzione pubblica ogni parametro su topic separati con valori semplici (non JSON) per massima compatibilità con client MQTT leggeri.

## Caratteristiche

- **Pubblicazione granulare**: Ogni parametro viene pubblicato su un topic specifico (es: `rotex/flow_rate`)
- **Valori semplici**: Solo il valore numerico/testuale, non JSON (compatibile con MQTT Dash)
- **Aggiornamento continuo**: Tutti i parametri vengono aggiornati ogni minuto
- **Container Mosquitto**: Broker MQTT locale in Docker con auto-start
- **Ottimizzato per app mobile**: Formato dati compatibile con client MQTT come MQTT Dash

## Struttura

```
mqtt-integration/
├── scripts/
│   ├── hpsu_mqtt_all.sh          # Script principale per lettura e pubblicazione
│   └── install_mqtt.sh           # Script di installazione automatica
├── docker/
│   ├── docker-compose.yml        # Configurazione Mosquitto
│   └── mosquitto.conf            # Configurazione broker (opzionale)
├── examples/
│   └── crontab.example           # Esempio configurazione cron
└── README.md                     # Questa documentazione
```

## Installazione Automatica

```bash
# Clona il repository
git clone https://github.com/tuouser/pyHPSU.git
cd pyHPSU/mqtt-integration

# Rendi eseguibili gli script
chmod +x scripts/*.sh

# Esegui l'installazione completamente automatica
./scripts/install_mqtt.sh
```

Lo script di installazione:
- ✅ Rileva automaticamente l'IP locale
- ✅ Installa Docker e Docker Compose se mancanti
- ✅ Configura il container Mosquitto
- ✅ Crea e configura lo script di monitoraggio
- ✅ Configura automaticamente il crontab (opzionale)
- ✅ Testa la connessione MQTT

## Test e Verifica

```bash
# Testa l'installazione
./scripts/test_mqtt.sh

# Monitora i valori in tempo reale
mosquitto_sub -h IP_LOCAL -t "rotex/+"

# Esegui manualmente
~/hpsu_mqtt_all.sh
```

## Configurazione

### Parametri Monitorati

Di default vengono monitorati questi parametri:
- `flow_rate`: Portata dell'impianto
- `t_v1`: Temperatura mandata
- `t_dhw1`: Temperatura acqua calda sanitaria  
- `pump`: Stato pompa
- `t_ext`: Temperatura esterna
- `water_pressure`: Pressione acqua

### Topic MQTT

I valori vengono pubblicati sui topic:
- `rotex/flow_rate`
- `rotex/t_v1`
- `rotex/t_dhw1`
- `rotex/pump`
- `rotex/t_ext`
- `rotex/water_pressure`

### Personalizzazione

Modifica il file `scripts/hpsu_mqtt_all.sh` per:
- Cambiare l'IP del broker MQTT (`MQTT_HOST`)
- Aggiungere/rimuovere parametri (array `PARAMS`)
- Modificare il prefisso dei topic (`MQTT_BASE_TOPIC`)

## Utilizzo con MQTT Dash

Per configurare **MQTT Dash** sul tuo smartphone:

1. **Installa MQTT Dash** dal Play Store
2. **Configurazione broker**:
   - Server: IP del Raspberry Pi (es: 192.168.0.106)
   - Porta: 1883
3. **Aggiungi tile per ogni parametro**:
   - Topic: `rotex/flow_rate`, `rotex/t_v1`, etc.
   - Tipo: Text o Gauge
   - Unità di misura: °C, bar, l/h secondo il parametro

## Monitoraggio

```bash
# Testa manualmente lo script
./scripts/hpsu_mqtt_all.sh

# Monitora i topic MQTT
mosquitto_sub -h IP_BROKER -t "rotex/+"

# Verifica i log del container
docker logs mosquitto

# Controlla il crontab
crontab -l
```

## Gestione

### Script disponibili

```bash
# Installazione
./scripts/install_mqtt.sh      # Installazione automatica completa

# Test e diagnostica  
./scripts/test_mqtt.sh         # Verifica funzionamento completo

# Disinstallazione
./scripts/uninstall_mqtt.sh    # Rimozione completa dell'integrazione
```

### Comandi utili

```bash
# Gestione container
docker-compose up -d           # Avvia Mosquitto
docker-compose down            # Ferma Mosquitto  
docker logs mosquitto          # Log del broker

# Gestione crontab
crontab -l                     # Mostra configurazione attuale
crontab -e                     # Modifica configurazione
```

## Troubleshooting

### Container non si avvia
```bash
# Verifica Docker
sudo systemctl status docker
sudo systemctl start docker

# Controlla i log
docker logs mosquitto
```

### Valori non pubblicati
```bash
# Testa pyHPSU manualmente
pyHPSU.py -c flow_rate

# Verifica connessione MQTT
mosquitto_pub -h IP_BROKER -t "test" -m "hello"
```

### Crontab non funziona
```bash
# Controlla i log di cron
sudo tail -f /var/log/syslog | grep CRON

# Testa lo script manualmente
/home/pi/hpsu_mqtt_all.sh
```

## Integrazione con Home Assistant

Aggiungi questo alla configurazione di Home Assistant:

```yaml
mqtt:
  sensor:
    - name: "HPSU Flow Rate"
      state_topic: "rotex/flow_rate"
      unit_of_measurement: "l/h"
      
    - name: "HPSU Temperatura Mandata"
      state_topic: "rotex/t_v1"
      unit_of_measurement: "°C"
      
    - name: "HPSU Temperatura Esterna"
      state_topic: "rotex/t_ext"
      unit_of_measurement: "°C"
      
    - name: "HPSU Pressione Acqua"
      state_topic: "rotex/water_pressure"
      unit_of_measurement: "bar"
```