# 现场套件：物料清单（2026-10-30）

将 ARGUS-NEURO 接入真实设备所需的部件，按每个监测点计算。本文补充 `FIELD_KIT.ru.md`（哪种设备用哪种套件），给出具体的连接器、线缆、电路板和传感器。

**状态标记。** ✔ 2026-10-30 已在厂商或销售页面核对。◐ 一般工程常识或我们自己的计算：下单前请对照数据手册确认。✖ 未核对：现场选定。价格为零售价，不含运费、关税和制裁限制，各卖家之间有差异。

**ARGUS 一侧现有的内容。** 只有 OCPP 采集器和 HTTP 接收端点（`POST /api/ingest/equipment`）。读取 CAN、I²C、SPI 或 Modbus 的代码尚不存在：这些网关软件需要另行编写，下列部件也尚未与 ARGUS 联合测试。

## 0. 对早先套件草稿的两处更正

1. RevPi Con CAN 模块**不能**用于 RevPi Connect 4（厂商商店标明其不兼容）。在 Connect 4 上，CAN 通过 USB 适配器接入（第 3 节）。
2. Connect 4 没有空闲的 I²C/SPI 排针：只有 2 个 USB-A、2 个 RJ45、RS485 和 PiBridge。I²C/SPI 传感器需要 USB 桥，或一个通过 RS485 与网关通信的小型微控制器节点（第 5 节）。

## 1. 公共部分：网关和机柜（套件 B 和 C）

| 项目 | 部件 / 要求 | 数量 | 状态 | 备注 |
|---|---|---|---|---|
| 网关 | Revolution Pi Connect 4（选择内存版本） | 1 | ✔ | 厂商价 €389，Distrelec 不含税 €535。10.8–28.8 V 直流，含 USB 负载最高 20 W，−25…+55 °C，TH35 导轨，IP20，2× USB-A，2× RJ45，X2 接头上有 RS485 |
| 电源 | 24 V 直流，导轨式，不低于 30 W | 1 | ◐ | 型号未定：取决于机柜供电 |
| 保护 | 24 V 供电线上的熔断器或直流断路器 | 1 | ◐ | 按电源电压选型 |
| 机箱 | 带 TH35 导轨的机柜，防护等级按现场 | 1 | ✖ | 为分流器及其熔断器留出空间 |
| 网络 | 带 RJ45 的屏蔽 Cat5e/6 跳线 | 1 | ✖ | 连到能访问 ARGUS 的路由器 |
| 接线 | X2 端子用的线鼻子和线缆 | 套 | ✖ | 线径见 Connect 4 数据手册 |

## 2. 套件 A：实验室电芯

如果循环仪能导出 CSV（等效循环、容量 Ah、条件、温度），**无需任何硬件**：将文件上传到电池页面即可。可选的外壳温度测量：

| 项目 | 部件 / 要求 | 数量 | 状态 | 备注 |
|---|---|---|---|---|
| 热电偶放大器 | Adafruit MAX31856 开发板（ADA3263），SPI | 每电芯 1 | ✔ | 约 £17 不含税（The Pi Hut）或 A$28（Core Electronics）。含 2 针端子和排针；3–5 V 逻辑 |
| 热电偶 | K 型，探头或粘贴式 | 每电芯 1 | ✔ | 另售；探头本身精度仅 ±2…±6 °C |
| 主机 | 带 SPI 的笔记本或 Raspberry Pi | 1 | ✖ | Connect 4 没有 SPI 排针 |
| 循环仪引线、电芯夹具 | 按电芯规格 | 套 | ✖ | 建议四线（开尔文）引线 |

## 3. 套件 B：带 CAN/BMS 的车辆和电池包

| 项目 | 部件 / 要求 | 数量 | 状态 | 备注 |
|---|---|---|---|---|
| CAN 适配器 | PEAK PCAN-USB FD，`IPEH-004022`（USB-A） | 1 | ✔ | $340（Gridconnect），£267.50 不含税（Control Technologies UK）。电气隔离，CAN FD，符合 CiA 303-1 的 9 针 D-Sub。另有 USB-C 版本 `IPEH-004023`。在 Linux 下通过 SocketCAN 工作（经销商说明） |
| 终端电阻 | PEAK PCAN-Term 或 PCAN-MiniTerm，或 120 Ω 电阻 | 1–2 | ✔ | 适配器内部终端出厂时关闭；PEAK 建议把终端放在线缆上 |
| 总线线缆 | 120 Ω 屏蔽双绞线用于 CAN，适配器一侧为 D-Sub 9 | 1 | ◐ | D-Sub 9（CiA 303-1）：2 脚 CAN_L，7 脚 CAN_H，3 脚地 |
| 车辆一侧 | OBD-II（SAE J1962）分接线，或 BMS 的配套连接器 | 1 | ◐ | OBD-II：6 脚 CAN_H，14 脚 CAN_L，4/5 脚地。线缆型号未定；具体 BMS 的连接器：✖ |
| 信号说明 | 车辆或 BMS 的 DBC 文件 | 1 | ✖ | **没有它就无法解码帧。** 向厂商索取；常不公开 |
| USB 线 | 按适配器需要的 USB-A | 1 | ✖ | 短、带屏蔽 |
| 容量所需电流 | INA228 模块和分流器，见第 5 节 | 1 | ◐ | 仅当 CAN 数据中没有可用电流时 |

只以**仅监听**方式连接，并取得所有者同意。不要在运行中的总线中间再加第二个终端电阻。

## 4. 套件 C：充电桩和机柜

| 项目 | 部件 / 要求 | 数量 | 状态 | 备注 |
|---|---|---|---|---|
| 电量和功率 | 通过 ARGUS 采集器获取 OCPP 1.6J `MeterValues` | – | ✔ | **无需硬件**：只需网络通路和运营方同意。仅用模拟器测试过 |
| 机柜温度 | K 型热电偶加 MAX31856（套件 A），或数字传感器 | 1–3 | ✔ / ✖ | OCPP 不传输机柜温度 |
| 风扇振动 | Analog Devices EVAL-ADXL355-PMDZ（ADXL355，Pmod） | 每风扇 1 | ✔ | 约 $37–70，视卖家而定；库存不稳定（部分页面显示 0）。安装：螺柱或粘胶 ✖ |
| 电网分析仪 | 带 Modbus RTU/TCP 的电表 | 1 | ✖ | 未调研；ARGUS 尚不能读取 Modbus |
| RS485 线缆 | 屏蔽双绞线，两端各接 120 Ω 终端 | 1 | ◐ | 注意 A/B 极性；屏蔽层只在一端接地 |
| 传感器到 USB 的连接 | USB–I²C/SPI 桥（FT232H 或 MCP2221A 类板） | 1 | ✖ | Connect 4 没有 I²C/SPI 排针；未核对具体板型 |

## 5. 电流、电压和电荷传感器

| 项目 | 部件 / 要求 | 数量 | 状态 | 备注 |
|---|---|---|---|---|
| 模块 | Adafruit INA228（产品 5832） | 每条被测线路 1 | ✔ | $14.95。85 V 共模，20 位，I²C（默认地址 0x40），3 V 或 5 V 逻辑，STEMMA QT，**板载 15 mΩ 0.1 % 分流电阻**。仅限直流。另有 SparkFun Qwiic INA228 ✔ |
| 板载电流上限 | 约 10 A | – | ◐ | 我们的计算：满量程 163.84 mV ÷ 15 mΩ ≈ 10.9 A |
| 更大电流用外部分流器 | R ≈ 0.8 × 163.84 mV ÷ Imax；额定功率不低于 2 × Imax² × R | 1 | ◐ | 外部分流器配开尔文检测线；整条链路的精度由分流器决定 |
| 熔断器 | 串在电力线上，直流额定，低于线缆承载上限 | 1 | ◐ | 必须；见 FIELD_KIT 第 6 节 |
| 隔离 | 数据侧的 I²C 隔离器 | 1 | ◐ | 模块的地跟随被测线路；需与网关隔离 |
| 导线 | 按线路故障电流选型的线缆 | – | ✖ | 由电工确定规格 |

## 6. 未涵盖的内容，以及采购前要决定的事

- CAN、INA228/ADXL355 和 Modbus 的读取软件（目前只有 OCPP）。
- 电源、机箱、线缆、隔离器、USB 桥、Modbus 电表、终端电阻和 OBD 线缆的具体型号。
- 每辆具体车辆或 BMS 的连接器和 DBC。
- 数量和总成本：取决于监测点数量。先订一套试点件（一台网关、一个 CAN 适配器、一个 INA228、一个 ADXL355），记录一周数据并检查缺失比例。
- 电网和电池作业由合格电工完成，并取得所有者的书面同意。

## 7. 来源（2026-10-30 核对）

- RevPi Con CAN 兼容性：[revolutionpi.com/shop/en/canbus-module](https://revolutionpi.com/shop/en/canbus-module)
- RevPi Connect 4 数据手册：[Mouser 副本](https://hr.mouser.com/datasheet/3/5999/1/Technical_Datasheet_RevPi_Connect_4.pdf)，[文档](https://revolutionpi.com/en/docs/revpi-connect-4)
- PCAN-USB FD 手册：[Control Technologies UK](https://controltech.uk.com/cdn/shop/files/PCAN-USB-FD_UserMan_eng1.pdf)
- INA228 板：[Adafruit 5832](https://adafruit.com/product/5832)，[SparkFun](https://www.sparkfun.com/sparkfun-current-sensor-ina228-qwiic.html)
- ADXL355 板：[Analog Devices](https://www.analog.com/EVAL-ADXL355-PMDZ)，[DigiKey](https://www.digikey.sg/en/products/detail/analog-devices-inc/EVAL-ADXL355-PMDZ/7324256)
- MAX31856 板：[The Pi Hut](https://thepihut.com/products/adafruit-universal-thermocouple-amplifier-max31856-breakout)
