
**L'uso di pyHPSU può causare _danni_ all'impianto di riscaldamento. Lo usi a tuo rischio: l'autore non risponde di eventuali danni.**

**Si rischia la perdita della garanzia e dell'assistenza del costruttore!**

**Questo software non è supportato dal costruttore!**

# pyHPSU (fork con integrazione MQTT/GCP)

pyHPSU è un insieme di script Python che legge (e, volendo, modifica) i valori della pompa di calore Rotex® **HPSU**, e probabilmente anche delle pompe Daikin® identiche, parlando sul bus CAN a 20 kbit/s.

Storia del codice: nasce da **[Vanni Brutto (Zanac)](https://github.com/zanac/pyHPSU)**, è proseguito in **[Spanni26/pyHPSU](https://github.com/Spanni26/pyHPSU)** e questo repository è un fork di quest'ultimo.

**Cosa aggiunge questo fork rispetto all'originale**
- il plugin di uscita `mqtt`, che qui **non** parla con un broker MQTT ma pubblica su Google Cloud Pub/Sub (vedi [Plugin di uscita](#plugin-di-uscita--o));
- il plugin `invio_mqtt_gcp`, variante che pubblica anche su un broker MQTT locale con indirizzo fisso nel sorgente;
- la cartella `mqtt-integration/`: script di shell per cron che pubblicano su un broker Mosquitto. **È questo, oggi, il modo in cui il fork viene usato in produzione** (vedi [Pubblicazione MQTT con cron](#pubblicazione-mqtt-con-cron-mqtt-integration)).

Il resto (driver CAN, catalogo dei 147 comandi, plugin per emoncms, fhem, homematic, influxdb, mysql, openhab, `contrib/`) è del progetto originale.

> Le note «dal codice» in questo documento sono state ricavate **leggendo i sorgenti**, non eseguendoli: quando un comportamento è importante, provalo prima sul tuo impianto.

---

# Hardware

pyHPSU funziona solo su sistemi unix/linux. Il bus CAN della HPSU si raggiunge dal connettore **J13** della scheda madre della pompa: servono CAN-H, CAN-L e massa (l'alimentazione sul lato CAN non serve).

## 1. SocketCAN (consigliato)
Un'interfaccia CAN vista dal kernel come `can0` (nel fork gira su un Raspberry Pi con HAT **MCP2515**). Il kernel accoda i messaggi, quindi più programmi o più valori in un solo comando possono usare la stessa interfaccia.

Esempio per un Raspberry Pi con MCP2515 (`/boot/config.txt`):
```
dtparam=spi=on
dtoverlay=mcp2515-can0,oscillator=12000000,interrupt=25,spimaxfrequency=2000000
```
(`oscillator` dipende dal quarzo del tuo modulo: 8 o 12 MHz.)

Bitrate 20 kbit/s. Con `/etc/network/interfaces` (Debian):
```
auto can0
iface can0 inet manual
    pre-up /sbin/ip link set $IFACE type can bitrate 20000 triple-sampling on
    up /sbin/ifconfig $IFACE up
    down /sbin/ifconfig $IFACE down
```
oppure, come nell'installazione di produzione, con `systemd-networkd` (`/etc/systemd/network/80-can.network`):
```
[Match]
Name=can0
[CAN]
BitRate=20K
RestartSec=100ms
```
Il driver `PYCAN` apre il canale **`can0`** con `bustype='socketcan_native'` (nome fisso nel codice, `HPSU/canpi.py`).

## 2. Interfaccia seriale ELM327
Funziona con driver `ELM327`. Molti cloni economici non vanno, perché non implementano il comando `AT PP`. Servono una presa OBD2 a 16 poli e questi collegamenti sul connettore J13: CAN-High al pin 6, CAN-Low al pin 14, massa al pin 5. Il nome del dispositivo si legge in `dmesg` al collegamento.

Una linea seriale può essere usata da un solo processo alla volta: per più richieste in parallelo serve il demone (vedi [Modalità](#modalità-di-esecuzione)).

---

# Installazione

Dipendenze (versioni usate in produzione tra parentesi):
- `python3`, `python3-can` (python-can 3.3.2: `socketcan_native` è disponibile solo nelle versioni vecchie), `python3-serial` (`pyHPSU.py` importa `serial` sempre, anche con SocketCAN)
- `python3-pika` e `rabbitmq-server`: solo per il driver `HPSUD` e per il demone
- `python3-paho-mqtt` (1.5.1) e `google-cloud-pubsub`: per i plugin `mqtt` e `invio_mqtt_gcp`
- `python3-requests`, `python3-mysql.connector`, `python3-urllib3`, `python3-influxdb`, `reportlab`: ciascuno per il proprio plugin
- per gli script di `mqtt-integration/`: `mosquitto-clients` (`mosquitto_pub`)

Installazione (come root o con `sudo`):
```
git clone https://github.com/paperinik007/pyHPSU_mqtt_GCP.git
cd pyHPSU_mqtt_GCP
sudo sh install.sh
```
`install.sh` copia:
- cataloghi e `pyhpsu.conf` in `/etc/pyHPSU/` (se `pyhpsu.conf` esiste già scrive `pyhpsu.conf.new` e non lo sovrascrive);
- il pacchetto Python in `/usr/lib/python3/dist-packages/HPSU/` (compresi i plugin, `contrib` e le chiavi/certificati);
- `pyHPSU.py` e `pyHPSUd.py` in `/usr/bin/`;
- le unit systemd `hpsu.service` e `hpsud.service` in `/etc/systemd/system/` (non le abilita).

La cartella dei plugin è fissa nel codice: `pyHPSU.py` cerca i plugin in `/usr/lib/python3/dist-packages/HPSU/plugins`. Senza `install.sh` l'opzione `-o` non vede i plugin.

---

# Uso

## Valori predefiniti
- Driver: `PYCAN` (SocketCAN, interfaccia `can0`)
- Lingua delle etichette: `EN` (con `-l IT` o `-l DE` si cambiano le descrizioni)
- Formato di uscita: `JSON`

## Opzioni (`pyHPSU.py`)
| Opzione | Significato |
|---|---|
| `-c <comando>` | comando da leggere (si ripete per più valori); `-c nome:valore` **scrive** il valore |
| `-d <driver>` | `PYCAN` (predefinito), `ELM327`, `HPSUD`, `EMU` (emulatore) |
| `-p <porta>` | porta seriale, solo per `ELM327` (es. `/dev/ttyUSB0`) |
| `-o <uscita>` | `JSON`, `CSV`, `BACKUP` o il nome di un plugin (vedi sotto) |
| `-l <lingua>` | `EN`, `IT`, `DE` |
| `-a` | modalità automatica: legge i comandi di `[JOBS]` in `pyhpsu.conf` |
| `-f <file>` | file di configurazione |
| `-b <file>` / `-r <file>` | salva / ripristina su file le impostazioni scrivibili |
| `-v 2` | uscita più descrittiva (unità, ON/OFF, data in formato leggibile) |
| `-g <file>` | log degli errori su file |
| `-h` | elenco dei comandi; `-h -c <comando>` ne mostra la descrizione |

I nomi dei driver sono quelli della tabella (il programma li converte in maiuscolo): `canpi`, `canelm327` e `CANTCP` sono nomi di classi o file interni, non valori validi per `-d`.

## Esempi
```
pyHPSU.py -h                    # elenco di tutti i comandi
pyHPSU.py -h -c t_hs            # descrizione di un comando
pyHPSU.py -c t_hs               # lettura, uscita JSON
pyHPSU.py -c t_hs -o CSV
pyHPSU.py -c t_hs -d ELM327 -p /dev/ttyUSB0 -o CSV
pyHPSU.py -c flow_rate -c t_ext -c water_pressure
```
Uscita tipica:
```
[{'name': 't_hs', 'resp': '32.00', 'timestamp': 1544534667.414178}]
```
**Differenza tra repository e Raspberry di produzione.** Il `pyHPSU.py` di questo repository stampa su stdout righe di debug: `chiamo read_can JSON` *prima* dei dati e, con un plugin, `pushValues chiamato` e righe di trattini. Il `pyHPSU.py` installato sul Pi di produzione (file datato 27 aprile 2023, confrontato con il repository) **non le ha**: lì l'uscita contiene solo i dati. Chi legge l'uscita (pipe, cron, variabile di shell) con il `pyHPSU.py` del repository riceve anche quelle righe. Gli altri file installati sul Pi (`pyHPSUd.py`, `commands_hpsu*`, i driver) sono uguali a quelli del repository; cambiano soltanto l'indirizzo del broker nei plugin `mqtt.py` e `invio_mqtt_gcp.py` (sul Pi punta al broker locale) e la lingua in `pyhpsu.conf` (`DE` sul Pi, `IT` nel repository).

## Catalogo dei comandi
- `etc/pyHPSU/commands_hpsu.json`: **147 comandi** (indirizzo CAN, tipo, divisore, unità). **103** sono marcati `writable`.
- `etc/pyHPSU/commands_hpsu_{EN,DE,IT}.csv`: etichette e descrizioni.

## Scrivere sulla pompa
`pyHPSU.py -c nome:valore` invia una **scrittura** alla pompa. Il comando non chiede conferma. I valori `-b`/`-r` (backup/ripristino) riguardano solo i 103 comandi scrivibili. Le scritture possono danneggiare l'impianto e far decadere la garanzia: provale prima su valori innocui e con un backup (`-b`) già fatto.

---

# Modalità di esecuzione

1. **Singola (standalone)**: una chiamata da riga di comando o da cron, come negli esempi sopra. È il modo usato in produzione.
2. **Automatica (`-a`)**: `pyHPSU.py -a` ripete le letture all'infinito. In `/etc/pyHPSU/pyhpsu.conf`, sezione `[JOBS]`, ogni riga è `comando = periodo_in_secondi`:
   ```
   [JOBS]
   t_ext = 6
   water_pressure = 4
   ```
   La unit `hpsu.service` lancia `pyHPSU.py -a`.
3. **Con demone (`HPSUD`)**: serve solo per interfacce seriali (ELM327). `pyHPSUd.py` (unit `hpsud.service`) tiene la porta aperta e serializza le richieste ricevute da più processi via **RabbitMQ**. I client usano `-d HPSUD`. Si configura nella sezione `[PYHPSUD]` di `pyhpsu.conf`.

**Dal codice:** i valori di `[PYHPSU]` in `pyhpsu.conf` (`PYHPSU_DEVICE`, `PYHPSU_PORT`, `PYHPSU_LANG`, `OUTPUT_TYPE`) vengono applicati solo se l'opzione corrispondente è una stringa vuota, ma la riga di comando parte con valori non vuoti (`PYCAN`, `EN`, `JSON`). In pratica quei valori sono ignorati: passa `-d`, `-l`, `-o` esplicitamente, anche con `-a`. Anche `[CANPI] timeout` (e `retry`) viene ignorato: `get_with_default` in `HPSU/canpi.py` cerca una sezione chiamata `config`, che non esiste, e restituisce sempre i valori predefiniti (timeout 0,05 s, 15 tentativi).

---

# Plugin di uscita (`-o`)

`-o` accetta `JSON`, `CSV`, `BACKUP` oppure il nome di un file in `HPSU/plugins/` (in maiuscolo o minuscolo). Le impostazioni stanno in `/etc/pyHPSU/pyhpsu.conf`, in una sezione col nome del plugin; ogni plugin ne mostra il modello in cima al proprio sorgente.

| `-o` | Sezione di `pyhpsu.conf` | Cosa fa |
|---|---|---|
| `CSV` | – | `timestamp,nome,valore` su console |
| `MYSQL` | `[MYSQL]` | scrive su un database MySQL (collation `utf8_bin`). Il file è `mysql.py`: un plugin «DB» non esiste |
| `EMONCMS` | `[EMONCMS]` | invia a emoncms (locale o web) |
| `FHEM` | `[FHEM]` | invia a fhem via telnet, porta 7072 |
| `HOMEMATIC` | `[HOMEMATIC]` | invia a una CCU con `xmlapi` e una variabile di sistema (`ise_id` nel file di configurazione) |
| `INFLUXDB` | `[INFLUXDB]` | invia a InfluxDB (client `python3-influxdb`, quindi API 1.x) |
| `OPENHAB` | `[OPENHAB]` | invia a openHAB (vedi sotto) |
| `PDF` | `[PDF]` | produce un PDF con le impostazioni (richiede `reportlab`; non provato) |
| `MQTT` | – | **in questo fork non è MQTT**: vedi sotto |
| `INVIO_MQTT_GCP` | `[invio_mqtt_gcp]` | vedi sotto |

## MQTT (`mqtt.py`) e INVIO_MQTT_GCP in questo fork
**Dal codice:**
- `mqtt.py` costruisce un messaggio JSON (`{"time": ..., "nome": "valore", ...}`) e lo pubblica su **Google Cloud Pub/Sub**. Progetto e topic sono scritti nel sorgente, le credenziali vengono dalla variabile d'ambiente `GOOGLE_APPLICATION_CREDENTIALS` (note di installazione in `HPSU/plugins/leggimi-mqtt.txt`). La sezione `[MQTT]` di `pyhpsu.conf` viene letta ma **non usata**. Serve `google-cloud-pubsub`. Dal topic il dato era pensato per una Cloud Function che lo carica in BigQuery.
- `invio_mqtt_gcp.py` fa lo stesso messaggio JSON, ha la pubblicazione su Pub/Sub commentata e pubblica su un **broker MQTT locale con indirizzo e topic fissi nel sorgente** (`brokers_out`, `topic`). Importa ancora `google.cloud.pubsub_v1` e crea il `PublisherClient`. Per cambiare broker o topic si modifica il file.
- Entrambi usano `mqtt.Client("nome")`, la firma di paho-mqtt 1.x.

Se ti serve solo «pubblicare su un broker MQTT», in produzione si usano gli script di shell qui sotto, non questi plugin.

## OPENHAB
Un item per ogni comando, con un prefisso comune (es. `Rotex_`): pyHPSU scrive su `[Prefisso][comando]`.
```
Number Rotex_mode      "Modus [MAP(heatpump_mode.map):%s]"
Number Rotex_t_dhw1    "Temperatura accumulo acqua calda [%.1f °C]"
```
Per i comandi come `mode`, dove un numero indica uno stato, si può usare il [mapping di openHAB](https://www.openhab.org/addons/transformations/map/). In `pyhpsu.conf`:
```
[OPENHAB]
HOST = nome_o_ip
PORT = 8080
ITEMPREFIX = Rotex_

[JOBS]
mode = 30
t_dhw1 = 60
```
(da usare con la modalità automatica `-a`.)

---

# Pubblicazione MQTT con cron (`mqtt-integration/`)

Questo è il flusso reale: un Raspberry Pi Zero W con HAT MCP2515, **cron** (le unit systemd sono disattivate) e due script di shell. Ognuno chiama `pyHPSU.py` (uscita JSON, driver `PYCAN`) e pubblica con `mosquitto_pub`.

| Script | Cosa pubblica | Frequenza consigliata (`mqtt-integration/crontab.example`) |
|---|---|---|
| `scripts/hpsu_mqtt_all.sh` | un topic per parametro, `rotex/<parametro>`, solo il valore (non JSON). 6 parametri: `flow_rate`, `t_v1`, `t_dhw1`, `pump`, `t_ext`, `water_pressure`. Un avvio di `pyHPSU.py` **per parametro**, con 0,5 s di pausa | ogni 5 minuti |
| `scripts/hpsu_mqtt_custom.sh <host> <porta> <topic>` | un solo messaggio con tutta l'uscita di **una** chiamata di `pyHPSU.py` per 15 parametri (`flow_rate posmix bpv t_v1 t_dhw1 t_r1 pump ehs mode t_hc_set t_dhw_set t_vbh t_ext water_pressure tdhw2`), con gli apici `'` sostituiti da `"` | ogni minuto **tranne i multipli di 5** |

Gli orari sono scelti perché i due script non usino il bus CAN nello stesso momento (così dice il commento di `mqtt-integration/crontab.example`). Lo stesso file avverte che la lettura ogni minuto può sovraccaricare il bus.

Per aggiungere un parametro a `hpsu_mqtt_custom.sh` basta un `-c nome` in più (i nomi validi sono quelli di `pyHPSU.py -h`). L'ultimo parametro, `tdhw2` (secondo sensore dell'acqua calda), è stato aggiunto in coda alla riga `pyHPSU.py` il 2026-11-13; `hpsu_mqtt_all.sh` non lo legge.

**Dal codice, due cose da sapere**
- `hpsu_mqtt_custom.sh` pubblica l'**intero** stdout di `pyHPSU.py`, cioè la lista `[{"name":..., "resp":..., "timestamp":...}, ...]`. Con il `pyHPSU.py` installato in produzione è la sola lista; con quello di questo repository il messaggio comincia con la riga di debug `chiamo read_can JSON` (vedi [Uso](#uso)).
- In `hpsu_mqtt_all.sh` l'indirizzo del broker è la variabile `MQTT_HOST` all'inizio dello script (il valore nel repository è un esempio da cambiare); porta e prefisso sono `MQTT_PORT` e `MQTT_BASE_TOPIC`.

## Esempio di crontab
```
*/5 * * * * /home/pi/pyHPSU/mqtt-integration/scripts/hpsu_mqtt_all.sh >/dev/null 2>&1
1-4,6-9,11-14,16-19,21-24,26-29,31-34,36-39,41-44,46-49,51-54,56-59 * * * * /home/pi/pyHPSU/mqtt-integration/scripts/hpsu_mqtt_custom.sh <host_broker> 1883 /home/sensors >/dev/null 2>&1
```
Il reindirizzamento su `/dev/null` serve anche a non scrivere di continuo sulla scheda SD. Con questo reindirizzamento un broker irraggiungibile non lascia nessuna traccia: controlla ogni tanto che i messaggi arrivino.

## Installazione guidata di Mosquitto (`install_mqtt.sh`)
`mqtt-integration/scripts/install_mqtt.sh` (da lanciare **senza** `sudo`: lo script si rifiuta di girare come root) installa Docker e `mosquitto-clients` se mancano, avvia Mosquitto da `docker/docker-compose.yml` (immagine `arm32v6`, per Raspberry a 32 bit), copia `hpsu_mqtt_all.sh` in `$HOME` con l'IP locale come broker e, se lo confermi, aggiunge una riga di cron **ogni minuto**. È una configurazione diversa da quella di produzione (5 minuti, script nella cartella del repository). Altri script: `test_mqtt.sh` (verifica) e `uninstall_mqtt.sh`.

Il file `docker/mosquitto.conf` ha `allow_anonymous true` e il listener WebSocket sulla 9001: va bene solo in una rete locale fidata. Per tutto il resto (uso con MQTT Dash, Home Assistant, risoluzione dei problemi) vedi `mqtt-integration/README.md`, che descrive il flusso originale a un topic per parametro.

---

# `contrib/`

Script del progetto originale, non necessari per il resto:
- `capture-publish/`: unit e timer systemd che leggono un elenco di variabili e le pubblicano su emoncms.org.
- `control/`: script che **scrivono** sulla pompa (cronotermostato, controllo della temperatura di mandata, setpoint e modo estate/inverno/raffrescamento). Leggi il codice prima di usarli.

---

# Struttura del repository

```
pyHPSU.py, pyHPSUd.py     programma principale e demone (RabbitMQ)
HPSU/HPSU.py              catalogo comandi, decodifica delle risposte
HPSU/can{pi,elm327,tcp,emu}.py   driver PYCAN, ELM327, HPSUD, EMU
HPSU/plugins/             plugin di uscita (-o)
etc/pyHPSU/               commands_hpsu.json (147 comandi), CSV EN/DE/IT, pyhpsu.conf
mqtt-integration/         script cron per Mosquitto (scripts/, docker/, examples/)
contrib/                  script del progetto originale
systemd/                  hpsu.service, hpsud.service
crontab/                  esempi di cron del fork per l'invio a Pub/Sub
install.sh                installazione di sistema
```

# Limiti noti
- Nessun test automatico: tutto quanto qui sopra è stato verificato sul campo o leggendo il codice, non con una suite.
- I valori di `[PYHPSU]` e `[CANPI]` in `pyhpsu.conf` sono ignorati (vedi sopra).
- Il `pyHPSU.py` del repository stampa righe di debug su stdout oltre ai dati; quello installato sul Pi di produzione no (vedi [Uso](#uso)). Chi aggiorna il Pi dal repository con `install.sh` ottiene la versione con le righe di debug.
- Il percorso dei plugin (`/usr/lib/python3/dist-packages/HPSU/plugins`) e il nome del canale CAN (`can0`) sono fissi nel codice.
- L'indirizzo del broker e il progetto Pub/Sub dei plugin `mqtt`/`invio_mqtt_gcp` sono scritti nei sorgenti.
- Le credenziali (broker MQTT, Google, database) non vanno nel repository: tienile nei file di configurazione locali.
