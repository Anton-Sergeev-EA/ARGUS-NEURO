# Sampling audit: a leak in the earlier results

**Status (30 October 2026): the numbers listed below as superseded must not be quoted.**

## What was wrong

To keep histories under 600 points, the cache builders for CALB and HUST kept every `ceil(N / 600)`-th cycle, where `N` is the **full** length of the cell's life. A model that sees a window of eight points also sees their spacing, so the spacing reveals how long the whole history is, and a longer life means a later failure. The correlation between the stride and the cycle at which a cell reaches 90% capacity is 0.880 on HUST (77 cells) and 0.851 on CALB (27 cells). The window's `cycle offset` channel carried this information into every learned model, the backtest windows and the second opinion.

An independent experiment with a fixed physical stride (see `experiments/2026-10-30_fixed_stride_hust`, written by a separate reviewer and not yet part of the repository history) measured the effect on gradient boosting: 72.7 cycles with the offset channel against 112.8 without it in the same adaptive sampling, a difference of about 40 cycles (95% interval of the paired difference −57 to −23).

## What is superseded

| Earlier statement | Where | Status |
|---|---|---|
| Learned models halve the error of a straight line (CALB 47 vs 96, HUST 77 vs 156 cycles) | `experiments/2026-10-29_calb_benchmark`, `…_hust_benchmark`, README research block | Superseded: obtained with the leaking stride |
| Curve indicators cut the error by 24% (68.6 → 52.4) | `experiments/2026-10-30_curve_indicators_hust`, `docs/CURVES.md` | Superseded: leaking stride; on the repaired pipeline see below |
| Calibrated interval covers 97% / 96% and the radius 0.70 | `docs/BACKTEST.md`, `python/argus/battery/calibration.json` | Superseded until the backtest is re-run at a fixed stride; the radius shipped in `calibration.json` is marked accordingly |
| The raw interval covered the truth 12% of the time | `docs/BACKTEST.md` | Not yet re-measured |

Arithmetic that does not depend on the stride (SOH formula, bootstrap trend, the simulator, the fleet triage rules) is unaffected, but it has no new validation either.

## The rule now

Cycle `c` is kept if `(c - 1) % stride == 0`, with the stride fixed in advance (default 5) and written into the metadata of every cache and report. Truncating a history does not change which of its remaining cycles are kept (`python/tests/test_sampling.py`). Physical cycle numbers are read from the raw files (HUST: the pickle keys; CALB: the workbook counter column, row order for two cells that have none). The old rule is still available as `--stride adaptive` and is labelled `diagnostic_only` everywhere; the second opinion and the indicator experiment refuse caches built with it.

Every feature set that is compared now goes through one window constructor with a common requirement (every indicator present), so a missing indicator removes the window for all sets and the numbers of cells and windows appear in the report.

## First check of the repaired pipeline

Single run on 2026-10-30, five grouped splits (seeds 41–45), gradient boosting on 8-point windows at stride 5, 18,255 windows on 77 cells (not preregistered; a pipeline check, not a result):

| Inputs | Test macro-MAE, cycles (mean ± std over splits) | Better than capacity only |
|---|---|---|
| capacity only | 108.6 ± 10.0 | – |
| + rise time | 112.5 ± 11.6 | 3 of 5 |
| + dQ/dV peak | 96.4 ± 18.2 | 4 of 5 |
| + all four indicators | 96.2 ± 15.8 | 4 of 5 |

Capacity-only error is now about 109 cycles instead of 69, which is the size of the leak. The indicator gain is smaller and less certain than the earlier 24%. The preregistered study of the next step decides whether any gain is real.
