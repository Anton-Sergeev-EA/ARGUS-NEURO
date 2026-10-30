# Field kit: bill of materials (30 Oct 2026)

Parts needed to connect ARGUS-NEURO to real devices, per monitored point. It complements `FIELD_KIT.ru.md` (which kit for which device) with the actual connectors, cables, boards and sensors.

**Status marks.** ✔ checked on a maker or seller page on 30 Oct 2026. ◐ general engineering knowledge or a calculation of ours: confirm in the datasheet before ordering. ✖ not checked: choose on site. Prices are retail, without shipping, duty or sanctions limits, and differ between sellers.

**What exists on the ARGUS side.** Only the OCPP collector and the HTTP ingest (`POST /api/ingest/equipment`). There is no code yet that reads CAN, I²C, SPI or Modbus: the gateway software for those has to be written, and the parts below are untested with ARGUS.

## 0. Two corrections to the earlier kit draft

1. The RevPi Con CAN module does **not** work with the RevPi Connect 4 (the maker's shop lists it as not compatible). On the Connect 4, CAN comes from a USB adapter (section 3).
2. The Connect 4 has no free I²C/SPI header: it offers 2× USB-A, 2× RJ45, RS485 and PiBridge. I²C/SPI sensors need a USB bridge or a small microcontroller node that talks to the gateway over RS485 (section 5).

## 1. Common part: gateway and cabinet (kits B and C)

| Item | Part / specification | Qty | Status | Note |
|---|---|---|---|---|
| Gateway | Revolution Pi Connect 4 (choose the memory variant) | 1 | ✔ | €389 (maker) to €535 ex VAT (Distrelec). 10.8–28.8 V DC, up to 20 W with USB load, −25…+55 °C, DIN rail TH35, IP20, 2× USB-A, 2× RJ45, RS485 on the X2 connector |
| Power supply | 24 V DC, DIN rail, at least 30 W | 1 | ◐ | Model not chosen: depends on the cabinet mains |
| Protection | Fuse or DC breaker on the 24 V feed | 1 | ◐ | Rated for the supply voltage |
| Enclosure | Cabinet with TH35 rail, IP rating for the site | 1 | ✖ | Leave room for the shunt and its fuse |
| Network | Shielded Cat5e/6 patch cable with RJ45 | 1 | ✖ | To the router that reaches ARGUS |
| Wiring | Wire ferrules and cable for the X2 terminals | set | ✖ | Sizes: see the Connect 4 datasheet |

## 2. Kit A: laboratory cells

If the cycler exports a CSV (equivalent cycle, capacity Ah, condition, temperature), **no hardware is needed**: the file goes to the battery page. Optional case temperature:

| Item | Part / specification | Qty | Status | Note |
|---|---|---|---|---|
| Thermocouple amplifier | Adafruit MAX31856 breakout (ADA3263), SPI | 1 per cell | ✔ | About £17 ex VAT (The Pi Hut) or A$28 (Core Electronics). Includes a 2-pin terminal block and a header; 3–5 V logic |
| Thermocouple | Type K, probe or adhesive tip | 1 per cell | ✔ | Sold separately; accuracy of the probe itself is only ±2…±6 °C |
| Host | Laptop or Raspberry Pi with SPI | 1 | ✖ | The Connect 4 has no SPI header |
| Cycler leads, cell holders | Per cell format | set | ✖ | Four-wire (Kelvin) leads recommended |

## 3. Kit B: vehicles and packs with CAN/BMS

| Item | Part / specification | Qty | Status | Note |
|---|---|---|---|---|
| CAN adapter | PEAK PCAN-USB FD, `IPEH-004022` (USB-A) | 1 | ✔ | $340 (Gridconnect), £267.50 ex VAT (Control Technologies UK). Galvanic isolation, CAN FD, 9-pin D-Sub per CiA 303-1. A USB-C variant `IPEH-004023` exists. Works under Linux through SocketCAN (reseller statement) |
| Terminator | PEAK PCAN-Term or PCAN-MiniTerm, or 120 Ω resistor | 1–2 | ✔ | Internal termination of the adapter is off at delivery; PEAK recommends putting it on the cabling |
| Cable to the bus | Shielded twisted pair 120 Ω for CAN, D-Sub 9 on the adapter side | 1 | ◐ | D-Sub 9 (CiA 303-1): pin 2 CAN_L, pin 7 CAN_H, pin 3 ground |
| Vehicle side | OBD-II (SAE J1962) tap cable, or the mating connector of the BMS | 1 | ◐ | OBD-II: pin 6 CAN_H, pin 14 CAN_L, pins 4/5 ground. Cable model not chosen; connector of a given BMS: ✖ |
| Signal description | DBC file of the vehicle or BMS | 1 | ✖ | **Without it the frames cannot be decoded.** Ask the maker; often closed |
| USB cable | USB-A to USB-A/C as the adapter needs | 1 | ✖ | Short, shielded |
| Current for capacity | INA228 module and shunt, section 5 | 1 | ◐ | Only if the CAN data has no usable current |

Connect **listen-only**, with the owner's consent. Do not put a second terminator in the middle of a running bus.

## 4. Kit C: charging stations and cabinets

| Item | Part / specification | Qty | Status | Note |
|---|---|---|---|---|
| Energy and power | OCPP 1.6J `MeterValues` through the ARGUS collector | – | ✔ | **No hardware**: a network path and the operator's consent. Tested only with the emulator |
| Cabinet temperature | Type K thermocouple and MAX31856 (kit A) or a digital sensor | 1–3 | ✔ / ✖ | OCPP does not carry cabinet temperature |
| Fan vibration | Analog Devices EVAL-ADXL355-PMDZ (ADXL355, Pmod) | 1 per fan | ✔ | About $37–70 depending on the seller; stock is irregular (some pages show 0). Mounting: stud or adhesive ✖ |
| Grid analyzer | Meter with Modbus RTU/TCP | 1 | ✖ | Not researched; ARGUS has no Modbus reader yet |
| RS485 cable | Shielded twisted pair, 120 Ω terminator at both ends | 1 | ◐ | Keep A/B polarity; ground the shield at one end |
| Sensor-to-USB link | USB–I²C/SPI bridge (an FT232H or MCP2221A class board) | 1 | ✖ | The Connect 4 has no I²C/SPI header; a specific board was not checked |

## 5. Current, voltage and charge sensor

| Item | Part / specification | Qty | Status | Note |
|---|---|---|---|---|
| Module | Adafruit INA228 (product 5832) | 1 per measured line | ✔ | $14.95. 85 V common-mode, 20-bit, I²C (default address 0x40), 3 V or 5 V logic, STEMMA QT, **15 mΩ 0.1 % shunt on board**. DC only. A SparkFun Qwiic INA228 also exists ✔ |
| Current limit of the board | About 10 A | – | ◐ | Our calculation: 163.84 mV full scale ÷ 15 mΩ ≈ 10.9 A |
| External shunt for more | R ≈ 0.8 × 163.84 mV ÷ Imax; power rating at least 2 × Imax² × R | 1 | ◐ | Use an external shunt with Kelvin sense wires; accuracy of the whole chain is set by the shunt |
| Fuse | In the power line, DC-rated, below the cable's limit | 1 | ◐ | Mandatory; see FIELD_KIT section 6 |
| Isolation | I²C isolator on the data side | 1 | ◐ | The module's ground follows the measured line; isolate it from the gateway |
| Wire | Cable rated for the fault current of the line | – | ✖ | Sized by the electrician |

## 6. Not covered, and what to decide before buying

- Software readers for CAN, INA228/ADXL355 and Modbus (only OCPP exists).
- Exact models for the power supply, enclosure, cables, isolator, USB bridge, Modbus meter, terminators and OBD cable.
- Connector and DBC of each concrete vehicle or BMS.
- Quantities and total cost: they depend on the number of points. Order one pilot set first (one gateway, one CAN adapter, one INA228, one ADXL355), record a week of data and check the share of gaps.
- Mains and battery work by a qualified electrician, with the owner's written consent.

## 7. Sources (checked 30 Oct 2026)

- RevPi Con CAN compatibility: [revolutionpi.com/shop/en/canbus-module](https://revolutionpi.com/shop/en/canbus-module)
- RevPi Connect 4 datasheet: [Mouser copy](https://hr.mouser.com/datasheet/3/5999/1/Technical_Datasheet_RevPi_Connect_4.pdf), [documentation](https://revolutionpi.com/en/docs/revpi-connect-4)
- PCAN-USB FD manual: [Control Technologies UK](https://controltech.uk.com/cdn/shop/files/PCAN-USB-FD_UserMan_eng1.pdf)
- INA228 board: [Adafruit 5832](https://adafruit.com/product/5832), [SparkFun](https://www.sparkfun.com/sparkfun-current-sensor-ina228-qwiic.html)
- ADXL355 board: [Analog Devices](https://www.analog.com/EVAL-ADXL355-PMDZ), [DigiKey](https://www.digikey.sg/en/products/detail/analog-devices-inc/EVAL-ADXL355-PMDZ/7324256)
- MAX31856 board: [The Pi Hut](https://thepihut.com/products/adafruit-universal-thermocouple-amplifier-max31856-breakout)
