# Kit da campo: distinta dei materiali (30/10/2026)

Parti necessarie per collegare ARGUS-NEURO a dispositivi reali, per ogni punto monitorato. Integra `FIELD_KIT.ru.md` (quale kit per quale dispositivo) con i connettori, i cavi, le schede e i sensori concreti.

**Segni di stato.** ✔ verificato il 30/10/2026 sulla pagina di un produttore o di un venditore. ◐ conoscenza ingegneristica generale o nostro calcolo: confermare nella scheda tecnica prima di ordinare. ✖ non verificato: scegliere sul posto. I prezzi sono al dettaglio, senza spedizione, dazi e restrizioni dovute alle sanzioni, e variano da un venditore all'altro.

**Cosa esiste lato ARGUS.** Solo il collettore OCPP e l'ingresso HTTP (`POST /api/ingest/equipment`). Non c'è ancora codice che legga CAN, I²C, SPI o Modbus: il software del gateway per questi va scritto, e le parti qui sotto non sono state provate con ARGUS.

## 0. Due correzioni alla bozza precedente del kit

1. Il modulo RevPi Con CAN **non** funziona con il RevPi Connect 4 (il negozio del produttore lo indica come non compatibile). Sul Connect 4 il CAN arriva da un adattatore USB (sezione 3).
2. Il Connect 4 non ha una barra I²C/SPI libera: offre 2× USB-A, 2× RJ45, RS485 e PiBridge. I sensori I²C/SPI richiedono un ponte USB o un piccolo nodo con microcontrollore che parli col gateway via RS485 (sezione 5).

## 1. Parte comune: gateway e armadio (kit B e C)

| Voce | Parte / requisito | Q.tà | Stato | Nota |
|---|---|---|---|---|
| Gateway | Revolution Pi Connect 4 (scegliere la variante di memoria) | 1 | ✔ | Da 389 € (produttore) a 535 € IVA esclusa (Distrelec). 10,8–28,8 V CC, fino a 20 W con carico USB, −25…+55 °C, guida DIN TH35, IP20, 2× USB-A, 2× RJ45, RS485 sul connettore X2 |
| Alimentatore | 24 V CC, guida DIN, almeno 30 W | 1 | ◐ | Modello non scelto: dipende dalla rete dell'armadio |
| Protezione | Fusibile o interruttore CC sulla linea a 24 V | 1 | ◐ | Adatto alla tensione della sorgente |
| Contenitore | Armadio con guida TH35, grado IP secondo il sito | 1 | ✖ | Lasciare spazio per lo shunt e il suo fusibile |
| Rete | Cavo Cat5e/6 schermato con RJ45 | 1 | ✖ | Fino al router che raggiunge ARGUS |
| Cablaggio | Puntalini e cavo per i morsetti X2 | set | ✖ | Sezioni: vedere la scheda tecnica del Connect 4 |

## 2. Kit A: celle di laboratorio

Se il ciclatore esporta un CSV (ciclo equivalente, capacità Ah, condizione, temperatura), **non serve hardware**: il file va caricato nella pagina della batteria. Facoltativa, la temperatura dell'involucro:

| Voce | Parte / requisito | Q.tà | Stato | Nota |
|---|---|---|---|---|
| Amplificatore per termocoppia | Scheda Adafruit MAX31856 (ADA3263), SPI | 1 per cella | ✔ | Circa 17 £ IVA esclusa (The Pi Hut) o 28 A$ (Core Electronics). Include un morsetto a 2 poli e una barra; logica 3–5 V |
| Termocoppia | Tipo K, sonda o punta adesiva | 1 per cella | ✔ | Venduta a parte; la precisione della sonda stessa è solo di ±2…±6 °C |
| Host | Portatile o Raspberry Pi con SPI | 1 | ✖ | Il Connect 4 non ha una barra SPI |
| Cavi del ciclatore, supporti | Secondo il formato della cella | set | ✖ | Consigliati cavi a quattro fili (Kelvin) |

## 3. Kit B: veicoli e pacchi con CAN/BMS

| Voce | Parte / requisito | Q.tà | Stato | Nota |
|---|---|---|---|---|
| Adattatore CAN | PEAK PCAN-USB FD, `IPEH-004022` (USB-A) | 1 | ✔ | 340 $ (Gridconnect), 267,50 £ IVA esclusa (Control Technologies UK). Isolamento galvanico, CAN FD, D-Sub a 9 pin secondo CiA 303-1. Esiste una variante USB-C `IPEH-004023`. Su Linux funziona con SocketCAN (secondo un rivenditore) |
| Terminatore | PEAK PCAN-Term o PCAN-MiniTerm, oppure resistenza da 120 Ω | 1–2 | ✔ | La terminazione interna dell'adattatore è disattivata alla consegna; PEAK consiglia di metterla sul cablaggio |
| Cavo verso il bus | Doppino intrecciato schermato da 120 Ω per CAN, D-Sub 9 lato adattatore | 1 | ◐ | D-Sub 9 (CiA 303-1): pin 2 CAN_L, pin 7 CAN_H, pin 3 massa |
| Lato veicolo | Cavo di derivazione OBD-II (SAE J1962) o connettore della BMS | 1 | ◐ | OBD-II: pin 6 CAN_H, pin 14 CAN_L, pin 4/5 massa. Modello del cavo non scelto; connettore di una BMS specifica: ✖ |
| Descrizione dei segnali | File DBC del veicolo o della BMS | 1 | ✖ | **Senza di esso i frame non si possono decodificare.** Chiederlo al produttore; spesso è chiuso |
| Cavo USB | USB-A, come richiesto dall'adattatore | 1 | ✖ | Corto, schermato |
| Corrente per la capacità | Modulo INA228 e shunt, sezione 5 | 1 | ◐ | Solo se i dati CAN non hanno una corrente utilizzabile |

Collegarsi **solo in ascolto** (listen-only), con il consenso del proprietario. Non mettere un secondo terminatore in mezzo a un bus in funzione.

## 4. Kit C: stazioni di ricarica e armadi

| Voce | Parte / requisito | Q.tà | Stato | Nota |
|---|---|---|---|---|
| Energia e potenza | OCPP 1.6J `MeterValues` tramite il collettore ARGUS | – | ✔ | **Nessun hardware**: un percorso di rete e il consenso dell'operatore. Provato solo con l'emulatore |
| Temperatura dell'armadio | Termocoppia tipo K e MAX31856 (kit A) o sensore digitale | 1–3 | ✔ / ✖ | OCPP non trasmette la temperatura dell'armadio |
| Vibrazione della ventola | Analog Devices EVAL-ADXL355-PMDZ (ADXL355, Pmod) | 1 per ventola | ✔ | Circa 37–70 $ secondo il venditore; disponibilità irregolare (alcune pagine mostrano 0). Fissaggio: prigioniero o adesivo ✖ |
| Analizzatore di rete | Contatore con Modbus RTU/TCP | 1 | ✖ | Non indagato; ARGUS non legge ancora Modbus |
| Cavo RS485 | Doppino intrecciato schermato, terminazione da 120 Ω a entrambe le estremità | 1 | ◐ | Rispettare la polarità A/B; collegare lo schermo a terra da un solo lato |
| Collegamento sensore-USB | Ponte USB–I²C/SPI (scheda di classe FT232H o MCP2221A) | 1 | ✖ | Il Connect 4 non ha una barra I²C/SPI; una scheda precisa non è stata verificata |

## 5. Sensore di corrente, tensione e carica

| Voce | Parte / requisito | Q.tà | Stato | Nota |
|---|---|---|---|---|
| Modulo | Adafruit INA228 (prodotto 5832) | 1 per linea misurata | ✔ | 14,95 $. 85 V di modo comune, 20 bit, I²C (indirizzo predefinito 0x40), logica 3 o 5 V, STEMMA QT, **shunt da 15 mΩ allo 0,1 % sulla scheda**. Solo corrente continua. Esiste anche uno SparkFun Qwiic INA228 ✔ |
| Limite di corrente della scheda | Circa 10 A | – | ◐ | Nostro calcolo: 163,84 mV di fondo scala ÷ 15 mΩ ≈ 10,9 A |
| Shunt esterno per correnti maggiori | R ≈ 0,8 × 163,84 mV ÷ Imax; potenza almeno 2 × Imax² × R | 1 | ◐ | Shunt esterno con fili di misura Kelvin; la precisione dell'intera catena la fissa lo shunt |
| Fusibile | Nella linea di potenza, adatto al CC, sotto il limite del cavo | 1 | ◐ | Obbligatorio; vedere FIELD_KIT sezione 6 |
| Isolamento | Isolatore I²C sul lato dati | 1 | ◐ | La massa del modulo segue la linea misurata; isolarla dal gateway |
| Cavo | Cavo per la corrente di guasto della linea | – | ✖ | Dimensionato dall'elettricista |

## 6. Cosa non è coperto e cosa decidere prima dell'acquisto

- Software di lettura per CAN, INA228/ADXL355 e Modbus (esiste solo OCPP).
- Modelli esatti di alimentatore, contenitore, cavi, isolatore, ponte USB, contatore Modbus, terminatori e cavo OBD.
- Connettore e DBC di ogni veicolo o BMS concreti.
- Quantità e costo totale: dipendono dal numero di punti. Ordinare prima un set pilota (un gateway, un adattatore CAN, un INA228, un ADXL355), registrare una settimana di dati e controllare la quota di vuoti.
- I lavori sulla rete elettrica e sulla batteria li esegue un elettricista qualificato, con il consenso scritto del proprietario.

## 7. Fonti (verificate il 30/10/2026)

- Compatibilità del RevPi Con CAN: [revolutionpi.com/shop/en/canbus-module](https://revolutionpi.com/shop/en/canbus-module)
- Scheda tecnica del RevPi Connect 4: [copia Mouser](https://hr.mouser.com/datasheet/3/5999/1/Technical_Datasheet_RevPi_Connect_4.pdf), [documentazione](https://revolutionpi.com/en/docs/revpi-connect-4)
- Manuale del PCAN-USB FD: [Control Technologies UK](https://controltech.uk.com/cdn/shop/files/PCAN-USB-FD_UserMan_eng1.pdf)
- Scheda INA228: [Adafruit 5832](https://adafruit.com/product/5832), [SparkFun](https://www.sparkfun.com/sparkfun-current-sensor-ina228-qwiic.html)
- Scheda ADXL355: [Analog Devices](https://www.analog.com/EVAL-ADXL355-PMDZ), [DigiKey](https://www.digikey.sg/en/products/detail/analog-devices-inc/EVAL-ADXL355-PMDZ/7324256)
- Scheda MAX31856: [The Pi Hut](https://thepihut.com/products/adafruit-universal-thermocouple-amplifier-max31856-breakout)
