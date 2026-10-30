# Fixed-stride re-run on HUST: how much did the adaptive stride inflate the results?

**Hypothesis.** Charge-curve indicators lower the remaining-life error against the best simple capacity-only baseline on unseen HUST cells when sampling does not depend on the future length of the history. Protocol and provisional go/no-go rules were written before the run: `preregistration.json`.

**Setup.** 77 HUST cells, raw pickles, physical cycle IDs (contiguous 1..N, no gaps, no non-positive capacities in the raw data). Fixed stride of 5 cycles, 8-point windows, threshold 90%. Five-fold CV grouped by cell, each cell tested once (calibration 12 / validation 12 cells per fold, rest train). Code: `python/argus/battery/fixed_stride_experiment.py`; run: `build` then `run --output metrics.json`. Adaptive-stride arms use the existing caches on the same folds as diagnostic controls. Single deterministic run, seeds fixed; CPU.

**Result (macro-MAE over 77 cells, cycles).**

| Arm | median | linear | ridge | GB | GPR | GRU | GB + indicators |
|---|---|---|---|---|---|---|---|
| fixed stride, capacity | 307 | 156 | 116 | 106 | **89** | 119 | **90** |
| adaptive stride, capacity + offset (old pipeline) | 309 | 155 | 83 | 73 | 67 | 71 | 62 |
| adaptive stride, capacity only (no offset) | 309 | 155 | 118 | 113 | 111 | not valid* | – |
| adaptive stride, span only | – | – | – | 301 | – | – | – |

*The GRU always receives the offset channel, so its "capacity only" row repeats the offset row and must be ignored.

- Removing the offset channel from the adaptive arm: GB 72.7 → 112.8, paired difference −40 cycles, 95% CI [−57, −23]. The adaptive-stride advantage comes from that channel; the span alone predicts nothing (301 vs median 309), so the information sits in the interaction with capacity.
- Fixed-stride GB (106) is about 46% worse than the published adaptive GB number (73 here, 77 in the earlier benchmark). Density of windows differs between arms (18 255 vs 25 327), so the within-adaptive ablation is the clean evidence, the cross-arm difference is not.
- Indicators on fixed stride: GB 106 → 90 (−15.6, 95% CI [1.2, 30.7], better in 46 of 77 cells). The gain over the strongest capacity-only model, GPR (89), is zero. The preregistered baseline pool excluded GPR and GRU, so the formal gate G2 compares with GB only.
- Intervals (split conformal, 90%): relative radius, per-cell coverage 0.912, mean width 458 cycles (median event about 1265 cycles); 3 of 77 cells have coverage below 0.5.
- 30% of indicator points removed in test windows: 90 → 101, still slightly better than capacity-only GB (106). Age-limited windows (position ≤ 300): 172 → 141.
- Abstention: ranking by disagreement of the two GB models does not reduce risk (60% accepted: 89.1 vs 90.5 at 100%); inverse predicted remaining life makes it worse.
- Proposed model: 0.0013 s per 1000 windows, 205 KB.

**Gates as declared.** G1 (span-only over median < 0.8): ratio 0.974, formally "not material", but the offset ablation above contradicts the intent of this gate; the gate measured the wrong thing. G2: passed against the declared pool, not against GPR. G3 passed. G4 failed.

**Conclusion.** The earlier headline numbers are not reproduced without the stride channel. Indicators help moderately relative to GB, not relative to a GPR with noise, and the abstention rule shows no benefit. This is one dataset, one charge protocol, discharge protocol groups unmapped, correlated windows, one run: a retrospective laboratory check, not field validation.
