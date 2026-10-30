"""Unit checks of the method-comparison helpers (no dataset needed)."""

from __future__ import annotations

import numpy as np

from argus.battery import method_experiment as me


def test_weighted_quantile_balances_cells() -> None:
    values = np.array([1.0, 1.0, 1.0, 1.0, 10.0])
    owner = np.array([0, 0, 0, 0, 1])
    w = me.cell_weights(owner)
    # The lone window of cell 1 carries half of the weight.
    assert me.weighted_quantile(values, w, 0.9) == 10.0
    assert me.weighted_quantile(values, np.ones(5), 0.5) == 1.0


def test_linear_prediction_extrapolates_and_clips() -> None:
    soh = 0.99 - 0.001 * np.arange(
        me.SIZE
    )  # falls 0.1 points per 5 cycles, 0.02 per cycle
    flat = np.full(me.SIZE, 0.99)
    x = np.stack([soh, flat])
    x = np.concatenate([x, np.zeros((2, 4 * me.SIZE))], axis=1)
    out = me.linear_prediction(x, cap=5000.0)
    assert out[0] < 5000.0 and out[0] > 0
    assert out[1] == 5000.0  # no decline: capped, never extrapolated


def test_columns_select_capacity_then_channel_blocks() -> None:
    cols = me.columns(("ica_peak_v",))
    assert cols[: me.SIZE] == list(range(me.SIZE))
    k = me.CHANNELS.index("ica_peak_v")
    assert cols[me.SIZE] == me.SIZE + me.SIZE * k


def test_interval_scores_report_per_cell_coverage() -> None:
    y = np.array([1.0, 2.0, 3.0, 4.0])
    owner = np.array([0, 0, 1, 1])
    lo, hi = y - 0.5, y + 0.5
    lo[3] = 5.0  # one miss
    hi[3] = 6.0
    s = me.interval_scores(lo, hi, y, owner)
    assert abs(s["coverage_per_cell_mean"] - 0.75) < 1e-9
    assert s["cells_below_0.85"] == 0.5


def test_bootstrap_interval_is_reproducible_and_paired() -> None:
    d = np.array([5.0, 6.0, 7.0, 4.0, 8.0])
    a = me.bootstrap_mean(d, np.random.default_rng(me.BOOT_SEED))
    b = me.bootstrap_mean(d, np.random.default_rng(me.BOOT_SEED))
    assert np.array_equal(a, b)
    assert np.percentile(a, 2.5) > 0  # every cell improved


def test_per_cell_mean_averages_appearances() -> None:
    splits = [
        {"cell_names": ["a", "a", "b"], "v": [1.0, 3.0, 10.0]},
        {"cell_names": ["a", "b"], "v": [6.0, 20.0]},
    ]
    got = me.per_cell_mean(splits, lambda s: np.array(s["v"]))
    assert got == {"a": (2.0 + 6.0) / 2, "b": 15.0}
