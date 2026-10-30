# Remaining-life backtest

> **Re-run at a fixed stride (30 October 2026).** The earlier version of this page used a thinning stride of ceil(N/600) that depends on the full history length and leaks the answer ([SAMPLING_AUDIT.md](SAMPLING_AUDIT.md)). Every number below comes from the re-run at a fixed physical stride of 5 cycles (NASA: every discharge test, no thinning); the earlier figures are withdrawn.

How well does the remaining-life interval hold up on cells it has never seen? This page records the answer, not the hope.

## Method

- **Data (108 cells, three sources):**
  - NASA PCoE: B0005, B0006, B0007, B0018 (NCA 18650, 24 °C).
  - CALB: 28 prismatic NCM cells, 0 °C to 45 °C, full-depth 1C cycles (Zenodo 17960956, CC BY 4.0). Preparation: `python -m argus.battery.calb`.
  - HUST: 77 LFP/graphite cells, 30 °C (Mendeley Data nsc7hnsg4s, CC BY 4.0, archive checksum pinned). Preparation: `python -m argus.battery.hust`; the pickled files are read with a loader that accepts only array and table classes.
- **Thresholds:** NASA 80% and 70%; CALB and HUST 90%, 85% and 80% of each cell's own reference capacity. A cell enters a threshold's test only if it crossed it; cells that never did are censored and left out.
- **Forecast points:** for every cell and threshold, about twelve observed prefixes. Each forecast sees only its prefix. The truth is the number of cycles until the first measurement at or below the threshold.
- **Calibration:** split-conformal quantile of the relative midpoint error in which every source dataset has the same total weight, so the 77 HUST cells do not set the radius for everybody.
- **Evaluation:** leave-one-cell-out (a cell never calibrates itself) and leave-one-dataset-out (calibrate on two sources, test on the third).
- **Reproduce:** `python -m argus.battery.backtest` (about 35 minutes on one CPU core). Raw per-forecast rows are in [assets/backtest.json](assets/backtest.json).

## Result

| | Linear trend (default) | Curve chosen by held-out error |
|---|---|---|
| Forecast points / with a number | 3713 / 1413 | 3713 / 1610 |
| Cells with a forecast | 108 | 108 |
| Abstained (no number shown) | 62% | 57% |
| Coverage of the raw bootstrap 5–95% interval | **9%** | 26% |
| Mean absolute midpoint error (cycles) | 83 | 61 |
| Median relative midpoint error | 24% | 11% |
| Calibrated coverage, leave-one-cell-out | **96%** | 96% |
| Calibrated coverage, leave-one-dataset-out | **95%** | 95% |
| Median calibrated width (relative to remaining life) | 1.6× | 1.7× |

Coverage when a whole dataset is held out (linear, nominal 90%): CALB 83%, HUST 100%, **NASA 73%**. Two of the three sources are therefore **below the nominal 90%** when they are the unseen one; the pooled 95% is carried by HUST.

Findings:

1. The bootstrap interval alone is **badly over-confident**: it contains the truth in about one forecast of eleven while presenting itself as 90%. It only measures scatter around the fitted line, not the way real cells change their rate of fade.
2. An interval widened by the measured relative error (radius 0.65 of the midpoint) covers about 96% on cells it did not see, at the price of width: the median interval is about 1.6× the remaining life. That is the honest size of the uncertainty with a capacity history only.
3. **Calibration does not transfer evenly between sources.** Equal weighting per source keeps the pooled figure high, but a held-out CALB or NASA dataset is covered only 83% and 73% of the time. Those NCM and NCA cells behave differently from the 77 LFP cells (NASA shows capacity regeneration spikes). A new chemistry or protocol may be under-covered; the report says the interval is laboratory-cell level, not guaranteed.
4. At the fixed stride, curved fits (exponential, quadratic) chosen by held-out error beat the straight line on both error measures (mean 61 vs 83 cycles, median relative 11% vs 24%). The earlier statement that they bring no reliable gain came from the leaking stride and is withdrawn. The default has **not** been changed: this page gives no per-cell confidence interval for the difference, and the selection rule was not fixed in advance. `ProjectionConfig(model="auto")` stays available; switching the default is an open decision.
5. More than half of the forecasts abstain by design (62% for the straight line). A refusal is better than a confident wrong number.

## Where this applies

The calibrated interval is applied only to laboratory-cell reports (`measurement_scope=cell`). Nothing here validates it for EV packs, calendar ageing or field use, so pack reports keep the uncalibrated interval and are labelled that way.
