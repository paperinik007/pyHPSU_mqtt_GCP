# Integrazione MQTT per pyHPSU

Script di shell, lanciati da **cron**, che leggono la pompa con `pyHPSU.py` e pubblicano i valori su un broker MQTT con `mosquitto_pub`. È la configurazione usata in produzione. Per il resto di pyHPSU (hardware, installazione, opzioni) vedi il `README.md` nella radice del repository.

## Due flussi

| Script | Cosa pubblica | Frequenza |
|---|---|---|
| `scripts/hpsu_mqtt_all.sh` | **un topic per parametro**, `rotex/<parametro>`, solo il valore (non JSON). 6 parametri: `flow_rate`, `t_v1`, `t_dhw1`, `pump`, `t_ext`, `water_pressure`. Un avvio di `pyHPSU.py` per parametro, con 0,5 s di pausa | ogni 5 minuti |
| `scripts/hpsu_mqtt_custom.sh <host> <porta> <topic>` | **un solo messaggio** con l'uscita di una chiamata di `pyHPSU.py` per 15 parametri: `flow_rate posmix bpv t_v1 t_dhw1 t_r1 pump ehs mode t_hc_set t_dhw_set t_vbh t_ext water_pressure tdhw2`. È una lista `[{"name":..., "resp":..., "timestamp":...}, ...]` con gli apici `'` sostituiti da `"` | ogni minuto **tranne i multipli di 5** |

Il primo serve per un telefono usato come display (app **MQTT Dash**, valori semplici), il secondo per alimentare un database o una dashboard. Gli orari sono scelti perché i due script non usino il bus CAN nello stesso momento; la lettura ogni minuto di tutto può sovraccaricare il bus.

## Contenuto

```
mqtt-integration/
├── scripts/
│   ├── hpsu_mqtt_all.sh       un topic per parametro (rotex/<parametro>)
│   ├── hpsu_mqtt_custom.sh    un messaggio JSON, host/porta/topic come argomenti
│   ├── install_mqtt.sh        installazione guidata di Mosquitto + cron (vedi sotto)
│   ├── test_mqtt.sh           verifica dell'installazione
│   └── uninstall_mqtt.sh      rimozione
├── docker/
│   ├── docker-compose.yml     Mosquitto (immagine arm32v6, Raspberry a 32 bit)
│   └── mosquitto.conf
├── examples/crontab.example   esempio per lo script installato in $HOME da install_mqtt.sh
├── crontab.example            esempio della configurazione di produzione
└── README.md
```

## Configurazione

- **`hpsu_mqtt_all.sh`**: l'indirizzo del broker è la variabile `MQTT_HOST` all'inizio dello script (il valore nel repository è un esempio da cambiare); poi `MQTT_PORT`, `MQTT_BASE_TOPIC` (`rotex`) e l'array `PARAMS`.
- **`hpsu_mqtt_custom.sh`**: host, porta e topic si passano come argomenti; i parametri sono nella riga `pyHPSU.py -c ...` (un `-c nome` in più per aggiungerne, i nomi validi sono quelli di `pyHPSU.py -h`).
- Entrambi richiedono `pyHPSU.py` nel `PATH` (installato con `install.sh` del repository) e `mosquitto-clients`.

## Crontab di produzione

```
*/5 * * * * /home/pi/pyHPSU/mqtt-integration/scripts/hpsu_mqtt_all.sh >/dev/null 2>&1
1-4,6-9,11-14,16-19,21-24,26-29,31-34,36-39,41-44,46-49,51-54,56-59 * * * * /home/pi/pyHPSU/mqtt-integration/scripts/hpsu_mqtt_custom.sh <host_broker> 1883 /home/sensors >/dev/null 2>&1
```
L'uscita su `/dev/null` serve anche a non scrivere di continuo sulla scheda SD. Con questo reindirizzamento un broker irraggiungibile non lascia nessuna traccia: controlla ogni tanto che i messaggi arrivino (`mosquitto_sub -h <host_broker> -t '#' -v`).

## Installazione guidata di Mosquitto (`install_mqtt.sh`)

```bash
git clone https://github.com/paperinik007/pyHPSU_mqtt_GCP.git
cd pyHPSU_mqtt_GCP/mqtt-integration
chmod +x scripts/*.sh
./scripts/install_mqtt.sh        # senza sudo: lo script si rifiuta di girare come root
```
Lo script: rileva l'IP locale, installa Docker, Docker Compose e `mosquitto-clients` se mancano, avvia Mosquitto da `docker/docker-compose.yml`, copia `hpsu_mqtt_all.sh` in `$HOME` con l'IP locale come broker e, se lo confermi, aggiunge una riga di cron **ogni minuto** per quella copia. È una configurazione diversa da quella di produzione (5 minuti, script nella cartella del repository): se vuoi quella, modifica il cron a mano dopo l'installazione. In produzione Mosquitto è gestito da IOTstack, non da questo compose.

`docker/mosquitto.conf` ha `allow_anonymous true` e un listener WebSocket sulla 9001: va bene solo in una rete locale fidata.

## Verifica

```bash
./scripts/test_mqtt.sh                          # prova guidata
mosquitto_sub -h <host_broker> -t "rotex/+" -v  # valori di hpsu_mqtt_all.sh
./scripts/hpsu_mqtt_all.sh                      # esecuzione manuale
docker logs mosquitto                           # log del broker (se in Docker)
crontab -l
```

## MQTT Dash (telefono)

1. Installa **MQTT Dash** dal Play Store.
2. Broker: IP del Raspberry (o di dove gira Mosquitto), porta 1883.
3. Una tile per parametro: topic `rotex/flow_rate`, `rotex/t_v1`, ecc.; tipo Text o Gauge; unità secondo il parametro (°C, bar, l/h).

## Home Assistant

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

## Problemi comuni

- **Valori non pubblicati**: prova `pyHPSU.py -c flow_rate` a mano; poi `mosquitto_pub -h <host_broker> -t test -m hello`.
- **Il cron non parte**: `sudo grep CRON /var/log/syslog | tail`; gli script devono essere eseguibili (`chmod +x`).
- **Il container non si avvia**: `sudo systemctl status docker`, `docker logs mosquitto`.
