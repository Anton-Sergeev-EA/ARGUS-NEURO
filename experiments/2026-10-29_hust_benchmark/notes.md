# HUST benchmark: does the learned-model advantage replicate?

**Hypothesis.** The CALB result (learned models about twice as accurate as a straight line on unseen cells) also holds on an independent chemistry, and 15 calibration cells are enough for a conformal interval.

**Setup.** 77 HUST LFP/graphite cells, threshold 90% of each cell's reference capacity. Cells split 32/15/15/15 into train/validation/calibration/test; the test set is read once per seed. Config and metrics: `config.json`, `metrics.json`.

**Result (test macro-MAE, cycles, mean of 3 seeds).** Median predictor 312, straight line 156, ridge 88, gradient boosting 77, TCN 78, GRU 75. The first-prefix conformal interval (radius about 210 cycles, width about 420) covered 87% of the 15 test cells at nominal 90%.

**Conclusion.** The advantage replicates: learned models halve the error of a straight line on a second chemistry. With 15 test cells the 87% coverage is consistent with 90% but cannot confirm it. The three learned models are within seed noise, so the simplest one (gradient boosting) is used for the optional second opinion in `argus.battery.second_opinion`, which refuses requests outside the trained chemistry, scope, axis, threshold and sampling spacing.
