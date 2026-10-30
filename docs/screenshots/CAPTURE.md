# Interface captures

Captured on 30 October 2026 from the locally running application (`bash scripts/run_dashboard.sh`) with headless Chrome at a 1280×860 viewport, once per interface language (`en`, `ru`, `zh`, `hi`, `es`, `fr`, `de`, `ja`, `it`). These are direct application screenshots; the interface language was set through the language selector's stored value, and every flow below was clicked through in the running page.

- `public-data-selection-<lang>.jpg`: the public NASA data selector and observed-history controls.
- `battery-nasa-<lang>.jpg`: NASA B0018, first 40 measured discharge tests, 70% end-of-life threshold. Capacity SOH is 83.8%; the conditional remaining trend estimate is 11.3–64.2 additional controlled discharge tests. SOC is unknown. These are laboratory cell measurements, not a vehicle pack forecast.
- `battery-trend-<lang>.jpg`: measured capacity for tests 1–40, the 70% threshold, the projected capacity line and the shaded uncertainty range. The recent trend uses tests 11–40 (a change of −6.8 points).
- `fleet-<lang>.jpg`: fleet triage of the built-in 13-battery synthetic example with the e-scooter preset: 2 service now, 3 plan service, 8 monitor, 0 not enough data. An asterisk marks an uncalibrated pack-level range.
- `equipment-live-<lang>.jpg`: the live nine-asset server simulation (shipboard converters, UAV power units, DC fast-charger cabinets) with ML/DL diagnostics, an anomaly log and an explicit simulated-source banner. It does not show connected physical equipment. Health indices and the anomaly log change from capture to capture.

Public data source and reuse caveats: [public battery data](../PUBLIC_BATTERY_DATA.md).
