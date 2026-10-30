# Methodology

Every number in a battery report can be traced to a formula below, a parameter in `python/argus/battery/config.py` and a test.

## 1. Capacity and health

`SOH = 100 × capacity_Ah / reference_capacity_Ah` for the comparable test condition. Records measured under another `condition_id` are excluded and reported. SOH is a wear indicator; it is not state of charge and not a safety statement.

## 2. Trend and remaining life

1. The last `window` (30) comparable observations are fitted with a straight line, `y = a + b·(cycle − last)`.
2. **Uncertainty of the fit.** 400 moving-block residual bootstrap refits (block length √n, seed 41) give the spread of the slope. A decline is trusted only if the 95th percentile of the slope is below −0.001 points per cycle.
3. **Time to threshold.** For each bootstrap refit that still declines, `(threshold − a) / b`; the 5th and 95th percentiles are the raw interval.
4. **Refusals.** No number is shown for fewer than 8 observations or a span under 10 cycles, an operating alert, mixed conditions, no reliable decline, a possible acceleration (recent slope over 1.5× steeper than the early one) or an interval upper end beyond five observed spans.
5. **Curved models (optional).** `ProjectionConfig(model="auto")` also fits an exponential and a quadratic curve, picks by the error on the newest held-out points, and keeps the straight line unless a curve is at least 25% better. The multi-cell backtest did not show a reliable gain, so the default is `linear`.

## 3. Calibrated interval for laboratory cells

The raw bootstrap interval measures scatter around a line; real cells also change their rate of fade. In the backtest it contained the true remaining life in only 12% of forecasts. For `measurement_scope=cell` the interval is therefore widened: the midpoint `m` is kept and the half-width is `r × max(m, 5 × median spacing)`, with `r = 0.70`, a finite-sample conformal quantile of the relative midpoint error in which each of the three source datasets (NASA, CALB, HUST) has equal weight. Leave-one-cell-out coverage is 97%, leave-one-dataset-out coverage 96% (CALB 90%, HUST 100%, NASA 67%). See [BACKTEST.md](BACKTEST.md). Pack reports are not widened because no pack data support a calibration, and the report says which interval kind it uses (`interval_kind`).

## 4. Voltage-curve indicators

Incremental capacity `dQ/dV` on a uniform voltage grid, rise time between two voltage levels and a step-based internal resistance are computed in C++20 with a NumPy fallback (identical algorithm, agreement tested to 1e-9). See [CURVES.md](CURVES.md).

## 5. Learned models

TCN, GRU, ridge and gradient boosting are trained with cells (not windows) split into train/validation/calibration/test, scaler fitted on training cells only, fixed seeds and a recorded configuration. They are compared with a median predictor and with a straight line through the same window. Results are in [`experiments/2026-10-29_calb_benchmark`](../experiments/2026-10-29_calb_benchmark/notes.md). The advantage over a straight line (about 2×) appeared on two independent chemistries (CALB NCM: 47 vs 96 cycles; HUST LFP: 77 vs 156, see [`experiments/2026-10-29_hust_benchmark`](../experiments/2026-10-29_hust_benchmark/notes.md)). They do not replace the explainable estimate. An optional gradient-boosting **second opinion** (`argus.battery.second_opinion`, trained locally with `python -m argus.battery.second_opinion <dataset.json>`; weights are not committed) is added to the API report as `second_opinion` only when the request matches the trained chemistry, scope, cycle axis, threshold and sampling spacing; otherwise the field says `out_of_domain` or `not_installed`.

Adding the charge-curve indicators of section 4 to the same model lowered the HUST error from 68.6 to 52.4 cycles (better in 5 of 5 splits); see [CURVES.md](CURVES.md). Not yet used by reports.

## 6. Recommendations

Rule-based and sourced. A limit is applied only if the user supplies it with its source; there are no built-in universal temperatures or charging percentages.

## 7. What is not claimed

- No EV-pack validation: the data are laboratory cells (NASA PCoE, CALB).
- No calendar-ageing model, no calibrated temperature or chemistry model, no censored-survival model.
- No vehicle range, safety, thermal-runaway or crash statement.
- Intervals describe past behaviour of the tested cells; they are not guarantees for another cell, protocol or chemistry.

## 8. Reproducing the numbers

```bash
bash scripts/build_cpp_core.sh
export PYTHONPATH="$PWD/python:$PWD/build/cpp_core"
python -m argus.battery.public_data --download     # NASA, see PUBLIC_BATTERY_DATA.md
python -m argus.battery.calb                       # after placing the CALB workbook, see BACKTEST.md
python -m argus.battery.hust                       # after downloading the HUST archive, see BACKTEST.md
python -m argus.battery.backtest                   # about 35 minutes
python -m argus.battery.curve_features
python -m argus.battery.training <dataset.json> --output <dir> --seeds 3 5 11
```
