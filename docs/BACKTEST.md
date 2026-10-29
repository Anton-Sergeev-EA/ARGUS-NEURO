# Remaining-life backtest

How well does the remaining-life interval hold up on cells it has never seen? This page records the answer, not the hope.

## Method

- **Data:** 4 NASA PCoE cells (B0005, B0006, B0007, B0018) and 28 CALB prismatic NCM cells (Zenodo record 17960956, CC BY 4.0, 0 °C to 45 °C, full-depth 1C cycles). Preparation: `python -m argus.battery.calb` after placing the workbook in `artifacts/battery-local/calb-raw/`.
- **Thresholds:** NASA 80% and 70%; CALB 90%, 85% and 80% of each cell's own reference capacity. A cell enters a threshold's test only if it actually crossed it; cells that never did are censored and left out.
- **Forecast points:** for every cell and threshold, about twelve observed prefixes. Each forecast sees only its prefix. The truth is the true number of cycles until the first measurement at or below the threshold.
- **Calibration:** split-conformal quantile of the relative midpoint error, evaluated **leave-one-cell-out**: a cell never calibrates its own forecast.
- **Reproduce:** `python -m argus.battery.backtest` (about 7 minutes on one CPU core). Raw per-forecast rows are in [assets/backtest.json](assets/backtest.json).

## Result

| | Linear trend (default) | Curve chosen by held-out error |
|---|---|---|
| Forecast points / with a number | 744 / 340 | 744 / 335 |
| Cells with a forecast | 31 | 31 |
| Abstained (no number shown) | 54% | 55% |
| Coverage of the raw bootstrap 5–95% interval | **22%** | 26% |
| Mean absolute midpoint error (cycles) | 59 | 82 |
| Median relative midpoint error | 24% | 20% |
| Coverage after calibration, leave-one-cell-out | **90%** | 90% |

Findings:

1. The bootstrap interval alone is **badly over-confident**: it contains the truth in about one forecast of five while presenting itself as 90%. It only measures scatter around the fitted line, not the way real cells change their rate of fade.
2. Calibrating the interval with the measured relative error (radius 0.70 of the midpoint) restores 90% coverage on unseen cells. It does so at the price of wide intervals (median width about 1.3× the remaining life). That is the honest size of the uncertainty at this level of information.
3. Curved fits (exponential, quadratic) chosen by held-out error lower the typical error but raise the mean error through occasional wild extrapolations. They did not give a reliable gain, so **linear stays the default**; `ProjectionConfig(model="auto")` is available for research.
4. More than half of forecasts abstain by design. A refusal is better than a confident wrong number.

## Where this applies

The calibrated interval is applied only to laboratory-cell reports (`measurement_scope=cell`). The data are small cells under controlled cycling. Nothing here validates the interval for EV packs, calendar ageing or field use, so pack reports keep the uncalibrated interval and are labelled that way.
