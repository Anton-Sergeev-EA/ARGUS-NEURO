# フィールドキット：部品表（2026-10-30）

ARGUS-NEURO を実機に接続するために必要な部品を、監視ポイントごとにまとめたものです。`FIELD_KIT.ru.md`（どの機器にどのキットか）を補い、具体的なコネクタ、ケーブル、基板、センサーを示します。

**状態マーク。** ✔ 2026-10-30 にメーカーまたは販売店のページで確認済み。◐ 一般的な技術知識または当方の計算：発注前にデータシートで確認してください。✖ 未確認：現地で選定。価格は小売価格で、送料、関税、制裁による制限は含まず、販売店によって異なります。

**ARGUS 側にあるもの。** OCPP コレクタと HTTP 受け口（`POST /api/ingest/equipment`）のみです。CAN、I²C、SPI、Modbus を読むコードはまだなく、そのためのゲートウェイ用ソフトウェアは今後書く必要があります。以下の部品も ARGUS との組み合わせでは未検証です。

## 0. 以前のキット案への 2 点の訂正

1. RevPi Con CAN モジュールは RevPi Connect 4 では**使えません**（メーカーのショップで非対応と表示されています）。Connect 4 では CAN は USB アダプタで接続します（第 3 節）。
2. Connect 4 には空いている I²C/SPI ヘッダがありません。あるのは USB-A ×2、RJ45 ×2、RS485、PiBridge です。I²C/SPI センサーには USB ブリッジか、RS485 でゲートウェイと通信する小型マイコンノードが必要です（第 5 節）。

## 1. 共通部分：ゲートウェイと盤（キット B と C）

| 品目 | 部品 / 要件 | 数量 | 状態 | 備考 |
|---|---|---|---|---|
| ゲートウェイ | Revolution Pi Connect 4（メモリ構成を選択） | 1 | ✔ | メーカー価格 €389 から Distrelec 税抜 €535。10.8–28.8 V DC、USB 負荷込みで最大 20 W、−25…+55 °C、TH35 DIN レール、IP20、USB-A ×2、RJ45 ×2、X2 コネクタに RS485 |
| 電源 | 24 V DC、DIN レール、30 W 以上 | 1 | ◐ | 型番未定：盤の電源環境による |
| 保護 | 24 V 給電ラインのヒューズまたは DC ブレーカ | 1 | ◐ | 電源電圧に適合するもの |
| 筐体 | TH35 レール付きの盤、保護等級は設置場所による | 1 | ✖ | シャントとそのヒューズの場所を空けておく |
| ネットワーク | RJ45 付きシールド Cat5e/6 パッチケーブル | 1 | ✖ | ARGUS に届くルータまで |
| 配線 | X2 端子用の棒端子とケーブル | 一式 | ✖ | 太さは Connect 4 のデータシート参照 |

## 2. キット A：実験室のセル

サイクラが CSV（等価サイクル、容量 Ah、条件、温度）を出力できるなら、**ハードウェアは不要**です。ファイルをバッテリーのページに読み込みます。任意で、ケース温度：

| 品目 | 部品 / 要件 | 数量 | 状態 | 備考 |
|---|---|---|---|---|
| 熱電対アンプ | Adafruit MAX31856 ブレークアウト（ADA3263）、SPI | セルごとに 1 | ✔ | 約 £17 税抜（The Pi Hut）または A$28（Core Electronics）。2 ピン端子台とヘッダ付き。3–5 V ロジック |
| 熱電対 | K 型、プローブまたは貼り付け型 | セルごとに 1 | ✔ | 別売。プローブ自体の精度は ±2…±6 °C に過ぎない |
| ホスト | SPI のあるノート PC または Raspberry Pi | 1 | ✖ | Connect 4 には SPI ヘッダがない |
| サイクラのリード、セルホルダ | セルの形状に合わせる | 一式 | ✖ | 四線式（ケルビン）リードを推奨 |

## 3. キット B：CAN/BMS を持つ車両とパック

| 品目 | 部品 / 要件 | 数量 | 状態 | 備考 |
|---|---|---|---|---|
| CAN アダプタ | PEAK PCAN-USB FD、`IPEH-004022`（USB-A） | 1 | ✔ | $340（Gridconnect）、£267.50 税抜（Control Technologies UK）。ガルバニック絶縁、CAN FD、CiA 303-1 準拠の 9 ピン D-Sub。USB-C 版 `IPEH-004023` もある。Linux では SocketCAN で動作（販売店の説明） |
| 終端 | PEAK PCAN-Term または PCAN-MiniTerm、もしくは 120 Ω 抵抗 | 1–2 | ✔ | アダプタ内蔵の終端は出荷時オフ。PEAK は配線側に付けることを推奨 |
| バスへのケーブル | CAN 用 120 Ω シールドツイストペア、アダプタ側は D-Sub 9 | 1 | ◐ | D-Sub 9（CiA 303-1）：2 番 CAN_L、7 番 CAN_H、3 番 GND |
| 車両側 | OBD-II（SAE J1962）分岐ケーブル、または BMS の対向コネクタ | 1 | ◐ | OBD-II：6 番 CAN_H、14 番 CAN_L、4/5 番 GND。ケーブル型番は未定。特定の BMS のコネクタ：✖ |
| 信号の定義 | 車両または BMS の DBC ファイル | 1 | ✖ | **これがないとフレームを解読できません。** メーカーに依頼する。非公開のことが多い |
| USB ケーブル | アダプタが必要とする USB-A | 1 | ✖ | 短く、シールド付き |
| 容量計算用の電流 | INA228 モジュールとシャント（第 5 節） | 1 | ◐ | CAN データに使える電流がない場合のみ |

接続は**受信専用**（listen-only）で、所有者の同意を得て行います。稼働中のバスの途中に 2 つ目の終端抵抗を入れないでください。

## 4. キット C：充電ステーションと盤

| 品目 | 部品 / 要件 | 数量 | 状態 | 備考 |
|---|---|---|---|---|
| 電力量と電力 | ARGUS コレクタ経由の OCPP 1.6J `MeterValues` | – | ✔ | **ハードウェア不要**：ネットワーク経路と運用者の同意のみ。エミュレータでのみ試験済み |
| 盤内温度 | K 型熱電対と MAX31856（キット A）、またはデジタルセンサー | 1–3 | ✔ / ✖ | OCPP は盤内温度を送らない |
| ファン振動 | Analog Devices EVAL-ADXL355-PMDZ（ADXL355、Pmod） | ファンごとに 1 | ✔ | 販売店により約 $37–70。在庫は不安定（0 と表示されるページもある）。取り付け：スタッドまたは接着 ✖ |
| 電力品質計 | Modbus RTU/TCP 付きのメータ | 1 | ✖ | 未調査。ARGUS はまだ Modbus を読めない |
| RS485 ケーブル | シールドツイストペア、両端に 120 Ω 終端 | 1 | ◐ | A/B の極性を守る。シールドは片側のみ接地 |
| センサーと USB の接続 | USB–I²C/SPI ブリッジ（FT232H または MCP2221A クラスの基板） | 1 | ✖ | Connect 4 には I²C/SPI ヘッダがない。具体的な基板は未確認 |

## 5. 電流・電圧・電荷センサー

| 品目 | 部品 / 要件 | 数量 | 状態 | 備考 |
|---|---|---|---|---|
| モジュール | Adafruit INA228（製品 5832） | 測定ラインごとに 1 | ✔ | $14.95。同相 85 V、20 ビット、I²C（既定アドレス 0x40）、3 V または 5 V ロジック、STEMMA QT、**基板上に 15 mΩ 0.1 % のシャント**。直流のみ。SparkFun Qwiic INA228 もある ✔ |
| 基板の電流上限 | 約 10 A | – | ◐ | 当方の計算：フルスケール 163.84 mV ÷ 15 mΩ ≈ 10.9 A |
| それ以上は外付けシャント | R ≈ 0.8 × 163.84 mV ÷ Imax、定格電力は 2 × Imax² × R 以上 | 1 | ◐ | ケルビン検出線付きの外付けシャント。全体の精度はシャントで決まる |
| ヒューズ | 電力ラインに、DC 定格で、ケーブルの限界以下 | 1 | ◐ | 必須。FIELD_KIT 第 6 節参照 |
| 絶縁 | データ側の I²C アイソレータ | 1 | ◐ | モジュールの GND は測定ラインに追従するため、ゲートウェイから絶縁する |
| 電線 | ラインの故障電流に耐えるケーブル | – | ✖ | 電気技術者が選定 |

## 6. 対象外のものと、購入前に決めること

- CAN、INA228/ADXL355、Modbus の読み取りソフトウェア（OCPP のみ存在）。
- 電源、筐体、ケーブル、アイソレータ、USB ブリッジ、Modbus メータ、終端、OBD ケーブルの具体的な型番。
- 個々の車両や BMS のコネクタと DBC。
- 数量と総額：ポイント数によります。まず試験用セット（ゲートウェイ 1、CAN アダプタ 1、INA228 1、ADXL355 1）を発注し、1 週間のデータを記録して欠損率を確認してください。
- 電源系統とバッテリーの作業は有資格の電気技術者が行い、所有者の書面による同意を得ます。

## 7. 出典（2026-10-30 確認）

- RevPi Con CAN の互換性：[revolutionpi.com/shop/en/canbus-module](https://revolutionpi.com/shop/en/canbus-module)
- RevPi Connect 4 データシート：[Mouser のコピー](https://hr.mouser.com/datasheet/3/5999/1/Technical_Datasheet_RevPi_Connect_4.pdf)、[ドキュメント](https://revolutionpi.com/en/docs/revpi-connect-4)
- PCAN-USB FD マニュアル：[Control Technologies UK](https://controltech.uk.com/cdn/shop/files/PCAN-USB-FD_UserMan_eng1.pdf)
- INA228 基板：[Adafruit 5832](https://adafruit.com/product/5832)、[SparkFun](https://www.sparkfun.com/sparkfun-current-sensor-ina228-qwiic.html)
- ADXL355 基板：[Analog Devices](https://www.analog.com/EVAL-ADXL355-PMDZ)、[DigiKey](https://www.digikey.sg/en/products/detail/analog-devices-inc/EVAL-ADXL355-PMDZ/7324256)
- MAX31856 基板：[The Pi Hut](https://thepihut.com/products/adafruit-universal-thermocouple-amplifier-max31856-breakout)
