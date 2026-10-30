# Kit de terrain : nomenclature (30/10/2026)

Pièces nécessaires pour relier ARGUS-NEURO à des appareils réels, par point surveillé. Complète `FIELD_KIT.ru.md` (quel kit pour quel appareil) avec les connecteurs, câbles, cartes et capteurs concrets.

**Repères d'état.** ✔ vérifié le 30/10/2026 sur la page d'un fabricant ou d'un vendeur. ◐ connaissance générale d'ingénieur ou calcul de notre part : à confirmer dans la fiche technique avant de commander. ✖ non vérifié : à choisir sur place. Les prix sont des prix de détail, hors livraison, droits de douane et restrictions liées aux sanctions, et varient selon le vendeur.

**Ce qui existe côté ARGUS.** Seulement le collecteur OCPP et l'entrée HTTP (`POST /api/ingest/equipment`). Il n'y a pas encore de code pour lire CAN, I²C, SPI ou Modbus : le logiciel de passerelle correspondant reste à écrire, et les pièces ci-dessous n'ont pas été essayées avec ARGUS.

## 0. Deux corrections au brouillon précédent du kit

1. Le module RevPi Con CAN **ne fonctionne pas** avec le RevPi Connect 4 (la boutique du fabricant l'indique comme non compatible). Sur le Connect 4, le CAN passe par un adaptateur USB (section 3).
2. Le Connect 4 n'a pas de connecteur I²C/SPI libre : il offre 2× USB-A, 2× RJ45, RS485 et PiBridge. Les capteurs I²C/SPI demandent un pont USB ou un petit nœud à microcontrôleur qui parle à la passerelle en RS485 (section 5).

## 1. Partie commune : passerelle et armoire (kits B et C)

| Élément | Pièce / exigence | Qté | État | Remarque |
|---|---|---|---|---|
| Passerelle | Revolution Pi Connect 4 (choisir la variante de mémoire) | 1 | ✔ | De 389 € (fabricant) à 535 € hors TVA (Distrelec). 10,8–28,8 V CC, jusqu'à 20 W avec charge USB, −25…+55 °C, rail DIN TH35, IP20, 2× USB-A, 2× RJ45, RS485 sur le connecteur X2 |
| Alimentation | 24 V CC, rail DIN, au moins 30 W | 1 | ◐ | Modèle non choisi : dépend du réseau de l'armoire |
| Protection | Fusible ou disjoncteur CC sur la ligne 24 V | 1 | ◐ | Adapté à la tension de la source |
| Boîtier | Armoire avec rail TH35, indice IP selon le site | 1 | ✖ | Prévoir la place du shunt et de son fusible |
| Réseau | Cordon Cat5e/6 blindé avec RJ45 | 1 | ✖ | Jusqu'au routeur qui atteint ARGUS |
| Câblage | Embouts et câble pour les bornes X2 | lot | ✖ | Sections : voir la fiche technique du Connect 4 |

## 2. Kit A : cellules de laboratoire

Si le cycleur exporte un CSV (cycle équivalent, capacité Ah, condition, température), **aucun matériel n'est nécessaire** : le fichier est chargé sur la page de la batterie. En option, la température du boîtier :

| Élément | Pièce / exigence | Qté | État | Remarque |
|---|---|---|---|---|
| Amplificateur de thermocouple | Carte Adafruit MAX31856 (ADA3263), SPI | 1 par cellule | ✔ | Environ 17 £ hors TVA (The Pi Hut) ou 28 A$ (Core Electronics). Fournie avec un bornier 2 broches et un connecteur ; logique 3–5 V |
| Thermocouple | Type K, sonde ou pointe adhésive | 1 par cellule | ✔ | Vendu séparément ; la précision de la sonde elle-même n'est que de ±2…±6 °C |
| Hôte | Ordinateur portable ou Raspberry Pi avec SPI | 1 | ✖ | Le Connect 4 n'a pas de connecteur SPI |
| Câbles du cycleur, supports | Selon le format de cellule | lot | ✖ | Câbles à quatre fils (Kelvin) recommandés |

## 3. Kit B : véhicules et packs avec CAN/BMS

| Élément | Pièce / exigence | Qté | État | Remarque |
|---|---|---|---|---|
| Adaptateur CAN | PEAK PCAN-USB FD, `IPEH-004022` (USB-A) | 1 | ✔ | 340 $ (Gridconnect), 267,50 £ hors TVA (Control Technologies UK). Isolation galvanique, CAN FD, D-Sub 9 broches selon CiA 303-1. Une variante USB-C `IPEH-004023` existe. Fonctionne sous Linux via SocketCAN (d'après un revendeur) |
| Terminaison | PEAK PCAN-Term ou PCAN-MiniTerm, ou résistance de 120 Ω | 1–2 | ✔ | La terminaison interne de l'adaptateur est désactivée à la livraison ; PEAK recommande de la placer sur le câblage |
| Câble vers le bus | Paire torsadée blindée 120 Ω pour CAN, D-Sub 9 côté adaptateur | 1 | ◐ | D-Sub 9 (CiA 303-1) : broche 2 CAN_L, broche 7 CAN_H, broche 3 masse |
| Côté véhicule | Câble de dérivation OBD-II (SAE J1962) ou connecteur homologue de la BMS | 1 | ◐ | OBD-II : broche 6 CAN_H, broche 14 CAN_L, broches 4/5 masse. Modèle de câble non choisi ; connecteur d'une BMS donnée : ✖ |
| Description des signaux | Fichier DBC du véhicule ou de la BMS | 1 | ✖ | **Sans lui, les trames ne peuvent pas être décodées.** À demander au fabricant ; souvent fermé |
| Câble USB | USB-A, selon l'adaptateur | 1 | ✖ | Court, blindé |
| Courant pour la capacité | Module INA228 et shunt, section 5 | 1 | ◐ | Seulement si les données CAN n'ont pas de courant exploitable |

Se connecter **en écoute seule**, avec l'accord du propriétaire. Ne pas poser une seconde terminaison au milieu d'un bus en service.

## 4. Kit C : bornes de recharge et armoires

| Élément | Pièce / exigence | Qté | État | Remarque |
|---|---|---|---|---|
| Énergie et puissance | OCPP 1.6J `MeterValues` via le collecteur ARGUS | – | ✔ | **Aucun matériel** : un chemin réseau et l'accord de l'opérateur. Testé seulement avec l'émulateur |
| Température de l'armoire | Thermocouple type K et MAX31856 (kit A) ou capteur numérique | 1–3 | ✔ / ✖ | OCPP ne transmet pas la température de l'armoire |
| Vibration du ventilateur | Analog Devices EVAL-ADXL355-PMDZ (ADXL355, Pmod) | 1 par ventilateur | ✔ | Environ 37–70 $ selon le vendeur ; disponibilité irrégulière (certaines pages affichent 0). Fixation : goujon ou colle ✖ |
| Analyseur de réseau | Compteur avec Modbus RTU/TCP | 1 | ✖ | Non étudié ; ARGUS ne lit pas encore Modbus |
| Câble RS485 | Paire torsadée blindée, terminaison 120 Ω aux deux extrémités | 1 | ◐ | Respecter la polarité A/B ; relier le blindage à la terre d'un seul côté |
| Liaison capteur-USB | Pont USB–I²C/SPI (carte de classe FT232H ou MCP2221A) | 1 | ✖ | Le Connect 4 n'a pas de connecteur I²C/SPI ; une carte précise n'a pas été vérifiée |

## 5. Capteur de courant, tension et charge

| Élément | Pièce / exigence | Qté | État | Remarque |
|---|---|---|---|---|
| Module | Adafruit INA228 (produit 5832) | 1 par ligne mesurée | ✔ | 14,95 $. 85 V en mode commun, 20 bits, I²C (adresse par défaut 0x40), logique 3 ou 5 V, STEMMA QT, **shunt de 15 mΩ à 0,1 % sur la carte**. Courant continu seulement. Un SparkFun Qwiic INA228 existe aussi ✔ |
| Limite de courant de la carte | Environ 10 A | – | ◐ | Notre calcul : 163,84 mV de pleine échelle ÷ 15 mΩ ≈ 10,9 A |
| Shunt externe pour plus | R ≈ 0,8 × 163,84 mV ÷ Imax ; puissance au moins 2 × Imax² × R | 1 | ◐ | Shunt externe avec fils de mesure Kelvin ; la précision de toute la chaîne dépend du shunt |
| Fusible | Dans la ligne de puissance, adapté au CC, sous la limite du câble | 1 | ◐ | Obligatoire ; voir FIELD_KIT section 6 |
| Isolation | Isolateur I²C côté données | 1 | ◐ | La masse du module suit la ligne mesurée ; l'isoler de la passerelle |
| Fil | Câble pour le courant de défaut de la ligne | – | ✖ | Dimensionné par l'électricien |

## 6. Ce qui n'est pas couvert et ce qu'il faut décider avant l'achat

- Logiciels de lecture de CAN, INA228/ADXL355 et Modbus (seul OCPP existe).
- Modèles exacts de l'alimentation, du boîtier, des câbles, de l'isolateur, du pont USB, du compteur Modbus, des terminaisons et du câble OBD.
- Connecteur et DBC de chaque véhicule ou BMS concret.
- Quantités et coût total : ils dépendent du nombre de points. Commander d'abord un lot pilote (une passerelle, un adaptateur CAN, un INA228, un ADXL355), enregistrer une semaine de données et vérifier la part de trous.
- Les travaux sur le réseau électrique et la batterie sont faits par un électricien qualifié, avec l'accord écrit du propriétaire.

## 7. Sources (vérifiées le 30/10/2026)

- Compatibilité du RevPi Con CAN : [revolutionpi.com/shop/en/canbus-module](https://revolutionpi.com/shop/en/canbus-module)
- Fiche technique du RevPi Connect 4 : [copie Mouser](https://hr.mouser.com/datasheet/3/5999/1/Technical_Datasheet_RevPi_Connect_4.pdf), [documentation](https://revolutionpi.com/en/docs/revpi-connect-4)
- Manuel du PCAN-USB FD : [Control Technologies UK](https://controltech.uk.com/cdn/shop/files/PCAN-USB-FD_UserMan_eng1.pdf)
- Carte INA228 : [Adafruit 5832](https://adafruit.com/product/5832), [SparkFun](https://www.sparkfun.com/sparkfun-current-sensor-ina228-qwiic.html)
- Carte ADXL355 : [Analog Devices](https://www.analog.com/EVAL-ADXL355-PMDZ), [DigiKey](https://www.digikey.sg/en/products/detail/analog-devices-inc/EVAL-ADXL355-PMDZ/7324256)
- Carte MAX31856 : [The Pi Hut](https://thepihut.com/products/adafruit-universal-thermocouple-amplifier-max31856-breakout)
