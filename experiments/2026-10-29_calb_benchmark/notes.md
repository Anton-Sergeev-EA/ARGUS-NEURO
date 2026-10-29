# CALB benchmark: sequence models vs a straight line

**Hypothesis.** Models trained on whole cells predict remaining cycles to 90% capacity on cells they never saw better than a straight line through the same eight-point window.

**Setup.** 28 CALB cells (27 reach 90%; one is censored and excluded from targets). Cells, not windows, are split 13/5/5/5 into train/validation/calibration/test, so no cell appears on both sides. Validation picks the winner; the test set is read once per seed. Config and metrics: `config.json`, `metrics.json`.

**Result (test macro-MAE, cycles, mean of 3 seeds).** Median predictor 319, ridge 132, straight line 96, gradient boosting 51, GRU 51, TCN 47.

**Conclusion.** Gradient boosting, GRU and TCN halve the error of the straight-line window on unseen cells. The gap is real but rests on 5 test cells of one chemistry and protocol; the three learned models are within seed noise of each other, and the calibration split (5 cells) is too small for a conformal interval (reported as insufficient). The learned models are therefore a research benchmark, not a production forecast: the explainable calibrated estimate remains the reported one until a larger and more varied cell set exists.
