# Feld-Kit: Stückliste (30.10.2026)

Teile, um ARGUS-NEURO an reale Geräte anzuschließen, je überwachtem Messpunkt. Ergänzt `FIELD_KIT.ru.md` (welches Kit für welches Gerät) um die konkreten Stecker, Kabel, Platinen und Sensoren.

**Statusmarken.** ✔ am 30.10.2026 auf einer Hersteller- oder Händlerseite geprüft. ◐ allgemeines Ingenieurwissen oder eigene Rechnung: vor der Bestellung im Datenblatt bestätigen. ✖ nicht geprüft: vor Ort wählen. Preise sind Einzelhandelspreise ohne Versand, Zoll und Sanktionsbeschränkungen und weichen je nach Händler ab.

**Was es auf ARGUS-Seite gibt.** Nur den OCPP-Collector und den HTTP-Eingang (`POST /api/ingest/equipment`). Code zum Lesen von CAN, I²C, SPI oder Modbus fehlt noch: die Gateway-Software dafür muss geschrieben werden, und die Teile unten sind mit ARGUS nicht erprobt.

## 0. Zwei Korrekturen am früheren Kit-Entwurf

1. Das Modul RevPi Con CAN funktioniert **nicht** mit dem RevPi Connect 4 (der Shop des Herstellers führt es als nicht kompatibel). Am Connect 4 kommt CAN über einen USB-Adapter (Abschnitt 3).
2. Der Connect 4 hat keine freie I²C/SPI-Stiftleiste: 2× USB-A, 2× RJ45, RS485 und PiBridge. I²C/SPI-Sensoren brauchen eine USB-Brücke oder einen kleinen Mikrocontroller-Knoten, der per RS485 mit dem Gateway spricht (Abschnitt 5).

## 1. Gemeinsamer Teil: Gateway und Schrank (Kits B und C)

| Position | Teil / Anforderung | Anz. | Status | Hinweis |
|---|---|---|---|---|
| Gateway | Revolution Pi Connect 4 (Speichervariante wählen) | 1 | ✔ | €389 (Hersteller) bis €535 ohne MwSt. (Distrelec). 10,8–28,8 V DC, bis 20 W mit USB-Last, −25…+55 °C, Hutschiene TH35, IP20, 2× USB-A, 2× RJ45, RS485 am Stecker X2 |
| Netzteil | 24 V DC, Hutschiene, mindestens 30 W | 1 | ◐ | Modell nicht gewählt: hängt vom Netz im Schrank ab |
| Schutz | Sicherung oder DC-Schutzschalter in der 24-V-Zuleitung | 1 | ◐ | Für die Versorgungsspannung ausgelegt |
| Gehäuse | Schrank mit TH35-Schiene, Schutzart nach Standort | 1 | ✖ | Platz für Shunt und dessen Sicherung lassen |
| Netzwerk | Geschirmtes Cat5e/6-Patchkabel mit RJ45 | 1 | ✖ | Zum Router, der ARGUS erreicht |
| Verdrahtung | Aderendhülsen und Kabel für die X2-Klemmen | Satz | ✖ | Querschnitte: siehe Datenblatt des Connect 4 |

## 2. Kit A: Laborzellen

Exportiert der Zyklisierer eine CSV (äquivalenter Zyklus, Kapazität Ah, Bedingung, Temperatur), ist **keine Hardware nötig**: die Datei geht auf die Batterieseite. Optional die Gehäusetemperatur:

| Position | Teil / Anforderung | Anz. | Status | Hinweis |
|---|---|---|---|---|
| Thermoelement-Verstärker | Adafruit MAX31856 Breakout (ADA3263), SPI | 1 je Zelle | ✔ | Etwa £17 ohne MwSt. (The Pi Hut) oder A$28 (Core Electronics). Mit 2-poliger Klemme und Stiftleiste; 3–5-V-Logik |
| Thermoelement | Typ K, Fühler oder Klebespitze | 1 je Zelle | ✔ | Separat erhältlich; die Genauigkeit des Fühlers selbst beträgt nur ±2…±6 °C |
| Host | Laptop oder Raspberry Pi mit SPI | 1 | ✖ | Der Connect 4 hat keine SPI-Stiftleiste |
| Zyklisierer-Leitungen, Zellhalter | Je nach Zellformat | Satz | ✖ | Vierleiter (Kelvin) empfohlen |

## 3. Kit B: Fahrzeuge und Packs mit CAN/BMS

| Position | Teil / Anforderung | Anz. | Status | Hinweis |
|---|---|---|---|---|
| CAN-Adapter | PEAK PCAN-USB FD, `IPEH-004022` (USB-A) | 1 | ✔ | $340 (Gridconnect), £267,50 ohne MwSt. (Control Technologies UK). Galvanische Trennung, CAN FD, 9-poliger D-Sub nach CiA 303-1. Eine USB-C-Variante `IPEH-004023` existiert. Unter Linux über SocketCAN (Händlerangabe) |
| Abschluss | PEAK PCAN-Term oder PCAN-MiniTerm, oder 120-Ω-Widerstand | 1–2 | ✔ | Die interne Terminierung des Adapters ist ab Werk aus; PEAK empfiehlt sie auf der Verkabelung |
| Kabel zum Bus | Geschirmtes verdrilltes Paar 120 Ω für CAN, D-Sub 9 auf Adapterseite | 1 | ◐ | D-Sub 9 (CiA 303-1): Pin 2 CAN_L, Pin 7 CAN_H, Pin 3 Masse |
| Fahrzeugseite | OBD-II-Abgriffkabel (SAE J1962) oder Gegenstecker der BMS | 1 | ◐ | OBD-II: Pin 6 CAN_H, Pin 14 CAN_L, Pins 4/5 Masse. Kabelmodell nicht gewählt; Stecker einer konkreten BMS: ✖ |
| Signalbeschreibung | DBC-Datei des Fahrzeugs oder der BMS | 1 | ✖ | **Ohne sie lassen sich die Frames nicht dekodieren.** Beim Hersteller anfragen; oft geschlossen |
| USB-Kabel | USB-A, wie vom Adapter verlangt | 1 | ✖ | Kurz, geschirmt |
| Strom für die Kapazität | INA228-Modul und Shunt, Abschnitt 5 | 1 | ◐ | Nur wenn die CAN-Daten keinen brauchbaren Strom enthalten |

Nur **lauschend** (listen-only) und mit Zustimmung des Eigentümers anschließen. Keinen zweiten Abschlusswiderstand mitten in einen laufenden Bus setzen.

## 4. Kit C: Ladestationen und Schränke

| Position | Teil / Anforderung | Anz. | Status | Hinweis |
|---|---|---|---|---|
| Energie und Leistung | OCPP 1.6J `MeterValues` über den ARGUS-Collector | – | ✔ | **Keine Hardware**: ein Netzwerkweg und die Zustimmung des Betreibers. Nur mit dem Emulator getestet |
| Schranktemperatur | Typ-K-Thermoelement und MAX31856 (Kit A) oder digitaler Sensor | 1–3 | ✔ / ✖ | OCPP überträgt keine Schranktemperatur |
| Lüftervibration | Analog Devices EVAL-ADXL355-PMDZ (ADXL355, Pmod) | 1 je Lüfter | ✔ | Etwa $37–70 je nach Händler; Verfügbarkeit schwankt (manche Seiten zeigen 0). Befestigung: Stehbolzen oder Klebstoff ✖ |
| Netzanalysator | Zähler mit Modbus RTU/TCP | 1 | ✖ | Nicht untersucht; ARGUS liest Modbus noch nicht |
| RS485-Kabel | Geschirmtes verdrilltes Paar, 120-Ω-Abschluss an beiden Enden | 1 | ◐ | Polarität A/B beachten; Schirm einseitig erden |
| Sensor-zu-USB-Verbindung | USB-I²C/SPI-Brücke (Platine der Klasse FT232H oder MCP2221A) | 1 | ✖ | Der Connect 4 hat keine I²C/SPI-Leiste; eine konkrete Platine wurde nicht geprüft |

## 5. Sensor für Strom, Spannung und Ladung

| Position | Teil / Anforderung | Anz. | Status | Hinweis |
|---|---|---|---|---|
| Modul | Adafruit INA228 (Produkt 5832) | 1 je Messleitung | ✔ | $14,95. 85 V Gleichtakt, 20 Bit, I²C (Standardadresse 0x40), 3-V- oder 5-V-Logik, STEMMA QT, **15-mΩ-Shunt 0,1 % auf der Platine**. Nur Gleichstrom. Auch ein SparkFun Qwiic INA228 existiert ✔ |
| Stromgrenze der Platine | Etwa 10 A | – | ◐ | Eigene Rechnung: 163,84 mV Vollausschlag ÷ 15 mΩ ≈ 10,9 A |
| Externer Shunt für mehr | R ≈ 0,8 × 163,84 mV ÷ Imax; Belastbarkeit mindestens 2 × Imax² × R | 1 | ◐ | Externer Shunt mit Kelvin-Messleitungen; die Genauigkeit der Kette bestimmt der Shunt |
| Sicherung | In der Leistungsleitung, DC-tauglich, unter der Grenze des Kabels | 1 | ◐ | Pflicht; siehe FIELD_KIT Abschnitt 6 |
| Trennung | I²C-Isolator auf der Datenseite | 1 | ◐ | Die Masse des Moduls folgt der gemessenen Leitung; vom Gateway trennen |
| Leitung | Kabel für den Fehlerstrom der Leitung | – | ✖ | Auslegung durch die Elektrofachkraft |

## 6. Nicht abgedeckt, und was vor dem Kauf zu entscheiden ist

- Software zum Lesen von CAN, INA228/ADXL355 und Modbus (nur OCPP existiert).
- Genaue Modelle für Netzteil, Gehäuse, Kabel, Isolator, USB-Brücke, Modbus-Zähler, Abschlüsse und OBD-Kabel.
- Stecker und DBC jedes konkreten Fahrzeugs oder jeder BMS.
- Mengen und Gesamtkosten: sie hängen von der Zahl der Messpunkte ab. Zuerst ein Pilotset bestellen (ein Gateway, ein CAN-Adapter, ein INA228, ein ADXL355), eine Woche Daten aufzeichnen und den Lückenanteil prüfen.
- Arbeiten an Netz und Batterie führt eine Elektrofachkraft aus, mit schriftlicher Zustimmung des Eigentümers.

## 7. Quellen (geprüft am 30.10.2026)

- Kompatibilität RevPi Con CAN: [revolutionpi.com/shop/en/canbus-module](https://revolutionpi.com/shop/en/canbus-module)
- Datenblatt RevPi Connect 4: [Mouser-Kopie](https://hr.mouser.com/datasheet/3/5999/1/Technical_Datasheet_RevPi_Connect_4.pdf), [Dokumentation](https://revolutionpi.com/en/docs/revpi-connect-4)
- Handbuch PCAN-USB FD: [Control Technologies UK](https://controltech.uk.com/cdn/shop/files/PCAN-USB-FD_UserMan_eng1.pdf)
- INA228-Platine: [Adafruit 5832](https://adafruit.com/product/5832), [SparkFun](https://www.sparkfun.com/sparkfun-current-sensor-ina228-qwiic.html)
- ADXL355-Platine: [Analog Devices](https://www.analog.com/EVAL-ADXL355-PMDZ), [DigiKey](https://www.digikey.sg/en/products/detail/analog-devices-inc/EVAL-ADXL355-PMDZ/7324256)
- MAX31856-Platine: [The Pi Hut](https://thepihut.com/products/adafruit-universal-thermocouple-amplifier-max31856-breakout)
