# Do charge-curve indicators improve prediction beyond capacity?

**Hypothesis.** The voltage rise time and the dQ/dV peak of the constant-current charge, computed by the C++ core, reduce the remaining-life error compared with a window of capacity values alone.

**Setup.** 77 HUST cells, threshold 90%. The same eight-point windows, the same asset-grouped split and the same gradient-boosting model; only the input channels differ. Five different split seeds show how much is split luck. Config and metrics: `config.json`, `metrics.json`.

**Result (test macro-MAE in cycles, mean ± std over 5 splits; number of splits better than capacity only).**

| Inputs | MAE | Better in |
|---|---|---|
| capacity only | 68.6 ± 8.2 | – |
| + rise time | 57.7 ± 7.0 | 4 of 5 |
| + dQ/dV peak (position, height, width) | 53.1 ± 5.2 | 5 of 5 |
| + all four indicators | 52.4 ± 4.5 | 5 of 5 |

**Conclusion.** Curve indicators cut the error by about a quarter (68.6 → 52.4 cycles) and make it more stable between splits. The dQ/dV peak carries most of the gain; adding rise time on top changes little. This is one chemistry (LFP), one protocol and one model type, and the indicators need a recorded charge curve, which a capacity-only CSV does not have. The result supports using curve data when available; it is not yet wired into the report.
