# Remaining-life backtest

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
| Forecast points / with a number | 3723 / 1151 | 3723 / 1242 |
| Cells with a forecast | 108 | 108 |
| Abstained (no number shown) | 69% | 67% |
| Coverage of the raw bootstrap 5–95% interval | **12%** | 22% |
| Mean absolute midpoint error (cycles) | 49 | 77 |
| Median relative midpoint error | 17% | 14% |
| Calibrated coverage, leave-one-cell-out | **97%** | 95% |
| Calibrated coverage, leave-one-dataset-out | **96%** | 95% |
| Median calibrated width (relative to remaining life) | 1.6× | 1.7× |

Coverage when a whole dataset is held out (linear, nominal 90%): CALB 90%, HUST 100%, **NASA 67%**.

Findings:

1. The bootstrap interval alone is **badly over-confident**: it contains the truth in about one forecast of eight while presenting itself as 90%. It only measures scatter around the fitted line, not the way real cells change their rate of fade.
2. An interval widened by the measured relative error (radius 0.70 of the midpoint) covers at least 90% on cells it did not see, at the price of width: the median interval is about 1.6× the remaining life. That is the honest size of the uncertainty with a capacity history only.
3. **Calibration does not transfer evenly between sources.** The first pooled calibration, dominated by the 77 HUST cells, gave a narrow radius (0.38) that covered only 61% of CALB and 46% of NASA when those sources were held out. Equal weighting per source fixes CALB (90%) but NASA stays at 67%: those NCA cells show capacity regeneration spikes unlike the others. A new chemistry or protocol may therefore be under-covered; the report says the interval is laboratory-cell level, not guaranteed.
4. Curved fits (exponential, quadratic) chosen by held-out error lower the median relative error (14% vs 17%) but raise the mean absolute error (77 vs 49 cycles) through occasional wild extrapolations. There is no reliable gain, so **linear stays the default**; `ProjectionConfig(model="auto")` is available for research.
5. Two thirds of forecasts abstain by design (69%). A refusal is better than a confident wrong number.

## Where this applies

The calibrated interval is applied only to laboratory-cell reports (`measurement_scope=cell`). Nothing here validates it for EV packs, calendar ageing or field use, so pack reports keep the uncalibrated interval and are labelled that way.
