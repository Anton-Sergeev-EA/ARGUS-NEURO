# Kit de campo: lista de materiales (30/10/2026)

Piezas necesarias para conectar ARGUS-NEURO a dispositivos reales, por cada punto monitorizado. Complementa `FIELD_KIT.ru.md` (qué kit para qué dispositivo) con los conectores, cables, placas y sensores concretos.

**Marcas de estado.** ✔ comprobado el 30/10/2026 en la página de un fabricante o vendedor. ◐ conocimiento general de ingeniería o cálculo propio: confirmar en la hoja de datos antes de pedir. ✖ no comprobado: elegir sobre el terreno. Los precios son de venta al público, sin envío, aranceles ni restricciones por sanciones, y varían según el vendedor.

**Qué existe en el lado de ARGUS.** Solo el colector OCPP y la entrada HTTP (`POST /api/ingest/equipment`). Aún no hay código que lea CAN, I²C, SPI ni Modbus: hay que escribir el software de la pasarela para ellos, y las piezas de abajo no se han probado con ARGUS.

## 0. Dos correcciones al borrador anterior del kit

1. El módulo RevPi Con CAN **no** funciona con el RevPi Connect 4 (la tienda del fabricante lo indica como no compatible). En el Connect 4 el CAN llega por un adaptador USB (sección 3).
2. El Connect 4 no tiene un cabezal I²C/SPI libre: ofrece 2× USB-A, 2× RJ45, RS485 y PiBridge. Los sensores I²C/SPI necesitan un puente USB o un pequeño nodo con microcontrolador que hable con la pasarela por RS485 (sección 5).

## 1. Parte común: pasarela y armario (kits B y C)

| Elemento | Pieza / requisito | Cant. | Estado | Nota |
|---|---|---|---|---|
| Pasarela | Revolution Pi Connect 4 (elegir la variante de memoria) | 1 | ✔ | De 389 € (fabricante) a 535 € sin IVA (Distrelec). 10,8–28,8 V CC, hasta 20 W con carga USB, −25…+55 °C, carril DIN TH35, IP20, 2× USB-A, 2× RJ45, RS485 en el conector X2 |
| Fuente de alimentación | 24 V CC, carril DIN, al menos 30 W | 1 | ◐ | Modelo sin elegir: depende de la red del armario |
| Protección | Fusible o interruptor de CC en la línea de 24 V | 1 | ◐ | Para la tensión de la fuente |
| Caja | Armario con carril TH35, grado IP según el lugar | 1 | ✖ | Dejar sitio para el shunt y su fusible |
| Red | Cable de red Cat5e/6 apantallado con RJ45 | 1 | ✖ | Hasta el router desde el que se ve ARGUS |
| Cableado | Punteras y cable para los bornes X2 | juego | ✖ | Secciones: ver la hoja de datos del Connect 4 |

## 2. Kit A: celdas de laboratorio

Si el ciclador exporta un CSV (ciclo equivalente, capacidad Ah, condición, temperatura), **no hace falta hardware**: el archivo se carga en la página de la batería. Opcional, la temperatura de la carcasa:

| Elemento | Pieza / requisito | Cant. | Estado | Nota |
|---|---|---|---|---|
| Amplificador de termopar | Placa Adafruit MAX31856 (ADA3263), SPI | 1 por celda | ✔ | Unas 17 £ sin IVA (The Pi Hut) o 28 A$ (Core Electronics). Incluye un borne de 2 pines y un cabezal; lógica de 3–5 V |
| Termopar | Tipo K, sonda o punta adhesiva | 1 por celda | ✔ | Se vende aparte; la precisión de la propia sonda es solo de ±2…±6 °C |
| Anfitrión | Portátil o Raspberry Pi con SPI | 1 | ✖ | El Connect 4 no tiene cabezal SPI |
| Cables del ciclador, soportes | Según el formato de celda | juego | ✖ | Se recomiendan cables de cuatro hilos (Kelvin) |

## 3. Kit B: vehículos y packs con CAN/BMS

| Elemento | Pieza / requisito | Cant. | Estado | Nota |
|---|---|---|---|---|
| Adaptador CAN | PEAK PCAN-USB FD, `IPEH-004022` (USB-A) | 1 | ✔ | 340 $ (Gridconnect), 267,50 £ sin IVA (Control Technologies UK). Aislamiento galvánico, CAN FD, D-Sub de 9 pines según CiA 303-1. Existe una variante USB-C `IPEH-004023`. En Linux funciona con SocketCAN (según un vendedor) |
| Terminador | PEAK PCAN-Term o PCAN-MiniTerm, o resistencia de 120 Ω | 1–2 | ✔ | La terminación interna del adaptador viene desactivada; PEAK recomienda ponerla en el cableado |
| Cable al bus | Par trenzado apantallado de 120 Ω para CAN, D-Sub 9 en el lado del adaptador | 1 | ◐ | D-Sub 9 (CiA 303-1): pin 2 CAN_L, pin 7 CAN_H, pin 3 masa |
| Lado del vehículo | Cable de derivación OBD-II (SAE J1962) o conector complementario de la BMS | 1 | ◐ | OBD-II: pin 6 CAN_H, pin 14 CAN_L, pines 4/5 masa. Modelo de cable sin elegir; conector de una BMS concreta: ✖ |
| Descripción de señales | Archivo DBC del vehículo o la BMS | 1 | ✖ | **Sin él no se pueden decodificar las tramas.** Pedirlo al fabricante; a menudo es cerrado |
| Cable USB | USB-A, según pida el adaptador | 1 | ✖ | Corto y apantallado |
| Corriente para la capacidad | Módulo INA228 y shunt, sección 5 | 1 | ◐ | Solo si los datos CAN no traen una corriente utilizable |

Conectar **solo en escucha**, con el consentimiento del propietario. No poner un segundo terminador en medio de un bus en marcha.

## 4. Kit C: estaciones de carga y armarios

| Elemento | Pieza / requisito | Cant. | Estado | Nota |
|---|---|---|---|---|
| Energía y potencia | OCPP 1.6J `MeterValues` mediante el colector de ARGUS | – | ✔ | **Sin hardware**: una ruta de red y el consentimiento del operador. Probado solo con el emulador |
| Temperatura del armario | Termopar tipo K y MAX31856 (kit A) o un sensor digital | 1–3 | ✔ / ✖ | OCPP no transmite la temperatura del armario |
| Vibración del ventilador | Analog Devices EVAL-ADXL355-PMDZ (ADXL355, Pmod) | 1 por ventilador | ✔ | Unos 37–70 $ según el vendedor; la disponibilidad es irregular (algunas páginas muestran 0). Montaje: espárrago o adhesivo ✖ |
| Analizador de red | Contador con Modbus RTU/TCP | 1 | ✖ | No investigado; ARGUS aún no lee Modbus |
| Cable RS485 | Par trenzado apantallado, terminador de 120 Ω en ambos extremos | 1 | ◐ | Respetar la polaridad A/B; conectar la pantalla a tierra en un solo extremo |
| Enlace sensor-USB | Puente USB–I²C/SPI (placa de la clase FT232H o MCP2221A) | 1 | ✖ | El Connect 4 no tiene cabezal I²C/SPI; no se comprobó una placa concreta |

## 5. Sensor de corriente, tensión y carga

| Elemento | Pieza / requisito | Cant. | Estado | Nota |
|---|---|---|---|---|
| Módulo | Adafruit INA228 (producto 5832) | 1 por línea medida | ✔ | 14,95 $. 85 V en modo común, 20 bits, I²C (dirección por defecto 0x40), lógica de 3 o 5 V, STEMMA QT, **shunt de 15 mΩ al 0,1 % en la placa**. Solo corriente continua. También existe un SparkFun Qwiic INA228 ✔ |
| Límite de corriente de la placa | Unos 10 A | – | ◐ | Cálculo propio: 163,84 mV de fondo de escala ÷ 15 mΩ ≈ 10,9 A |
| Shunt externo para más corriente | R ≈ 0,8 × 163,84 mV ÷ Imax; potencia al menos 2 × Imax² × R | 1 | ◐ | Shunt externo con hilos Kelvin; la precisión de toda la cadena la fija el shunt |
| Fusible | En la línea de potencia, apto para CC, por debajo del límite del cable | 1 | ◐ | Obligatorio; véase FIELD_KIT sección 6 |
| Aislamiento | Aislador I²C en el lado de datos | 1 | ◐ | La masa del módulo sigue a la línea medida; aislarla de la pasarela |
| Cable | Cable para la corriente de falta de la línea | – | ✖ | Lo dimensiona el electricista |

## 6. Lo no cubierto y qué decidir antes de comprar

- Programas de lectura de CAN, INA228/ADXL355 y Modbus (solo existe OCPP).
- Modelos exactos de fuente, caja, cables, aislador, puente USB, contador Modbus, terminadores y cable OBD.
- Conector y DBC de cada vehículo o BMS concretos.
- Cantidades y coste total: dependen del número de puntos. Pedir primero un juego piloto (una pasarela, un adaptador CAN, un INA228, un ADXL355), registrar una semana de datos y comprobar la proporción de huecos.
- El trabajo en la red eléctrica y la batería lo realiza un electricista cualificado, con consentimiento escrito del propietario.

## 7. Fuentes (comprobadas el 30/10/2026)

- Compatibilidad del RevPi Con CAN: [revolutionpi.com/shop/en/canbus-module](https://revolutionpi.com/shop/en/canbus-module)
- Hoja de datos del RevPi Connect 4: [copia de Mouser](https://hr.mouser.com/datasheet/3/5999/1/Technical_Datasheet_RevPi_Connect_4.pdf), [documentación](https://revolutionpi.com/en/docs/revpi-connect-4)
- Manual del PCAN-USB FD: [Control Technologies UK](https://controltech.uk.com/cdn/shop/files/PCAN-USB-FD_UserMan_eng1.pdf)
- Placa INA228: [Adafruit 5832](https://adafruit.com/product/5832), [SparkFun](https://www.sparkfun.com/sparkfun-current-sensor-ina228-qwiic.html)
- Placa ADXL355: [Analog Devices](https://www.analog.com/EVAL-ADXL355-PMDZ), [DigiKey](https://www.digikey.sg/en/products/detail/analog-devices-inc/EVAL-ADXL355-PMDZ/7324256)
- Placa MAX31856: [The Pi Hut](https://thepihut.com/products/adafruit-universal-thermocouple-amplifier-max31856-breakout)
