"""Unit checks of the method-comparison helpers (no dataset needed)."""

from __future__ import annotations

import zlib

import numpy as np

from argus.battery import method_experiment as me
from argus.battery.windows import CellWindows


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


# ----------------------------------------------------- synthetic end-to-end


def _cell(name: str, rate: float, n: int = 40) -> CellWindows:
    rng = np.random.default_rng(zlib.crc32(name.encode()))
    pos = np.arange(n) * me.STRIDE + me.SIZE * me.STRIDE
    soh = 1.0 - rate * (pos[:, None] - np.arange(me.SIZE)[::-1] * me.STRIDE)
    soh = soh + rng.normal(0, 1e-4, soh.shape)
    event = 0.1 / rate
    ind = {
        k: soh * (1 + 0.01 * i) + rng.normal(0, 1e-3, soh.shape)
        for i, k in enumerate(me.CHANNELS)
    }
    return CellWindows(
        cell_id=name,
        capacity=soh,
        cycle_offset=np.zeros_like(soh),
        indicators=ind,
        position=pos.astype(float),
        target=np.maximum(event - pos, 0.0),
        event_cycle=event,
        censored=False,
    )


def _split() -> tuple[list[CellWindows], ...]:
    rates = np.linspace(2e-4, 6e-4, 12)
    cells = [_cell(f"c{i}", float(r)) for i, r in enumerate(rates)]
    return cells[:5], cells[5:7], cells[7:10], cells[10:]


def test_design_and_capacity_shapes() -> None:
    train = _split()[0]
    x, y, owner = me.design(train)
    assert x.shape == (len(y), me.SIZE * (1 + len(me.CHANNELS)))
    assert me.capacity(x).shape == (len(y), me.SIZE)
    assert set(owner) == set(range(len(train)))


def test_macro_averages_cells_not_windows() -> None:
    err = np.array([1.0, 1.0, 1.0, 9.0])
    owner = np.array([0, 0, 0, 1])
    assert me.macro(err, owner) == 5.0


def test_group_keeps_requested_order() -> None:
    cells = {c.cell_id: c for c in _split()[0]}
    assert [c.cell_id for c in me.group(cells, ["c2", "c0"])] == ["c2", "c0"]


def test_run_split_produces_every_field_without_leaking_shapes() -> None:
    train, val, cal, test = _split()
    out = me.run_split(train, val, cal, test, seed=1)
    n = sum(len(c) for c in test)
    for name in me.ALL_MODELS:
        assert len(out["pred"][name]) == n
    assert set(out["pred_missing"]) == {"gb_indicators", "ensemble", "ensemble_gated"}
    assert len(out["missing"]) == n
    for lo, hi in out["intervals"].values():
        assert all(a <= b for a, b in zip(lo, hi, strict=True))
    for mask in out["accept"].values():
        assert sum(mask) == round(me.ACCEPT * n)
    assert out["sizes"]["gpr_bytes"] > 0


def test_gated_ensemble_falls_back_to_gpr_when_indicators_missing() -> None:
    train, val, _, test = _split()
    models = me.fit_all(train, val, seed=1)
    x, _, _ = me.design(test)
    missing = np.zeros(len(x), dtype=bool)
    missing[::2] = True
    pred = me.predict_all(models, x, missing)
    assert np.allclose(pred["ensemble_gated"][missing], pred["gpr_capacity"][missing])
    assert np.allclose(pred["ensemble_gated"][~missing], pred["ensemble"][~missing])


def test_intervals_widen_with_noisier_calibration() -> None:
    y = np.linspace(100.0, 500.0, 40)
    owner = np.repeat(np.arange(4), 10)

    def preds(noise: float) -> dict[str, np.ndarray]:
        base = y + noise * np.tile([-1.0, 1.0], 20)
        return {
            "gb_indicators": base,
            "ensemble": base,
            "gpr_capacity": base,
            "_sigma": np.full(40, noise),
            "_q_lo": base - noise,
            "_q_hi": base + noise,
        }

    narrow = me.intervals(y, owner, preds(5.0), preds(5.0))
    wide = me.intervals(y, owner, preds(50.0), preds(5.0))
    for key, (lo, hi) in narrow.items():
        assert (hi - lo).mean() <= (wide[key][1] - wide[key][0]).mean() + 1e-9, key


def test_summaries_on_synthetic_splits() -> None:
    splits = [me.run_split(*_split(), seed=s) for s in (1, 2)]
    rng = np.random.default_rng(me.BOOT_SEED)
    main = me.summarize(splits, "gpr_capacity", rng)
    assert main["cells_evaluated"] == 2
    assert main["paired_vs_baseline"]["gpr_capacity"]["gain_cycles"] == 0.0
    assert set(main["models"]) == set(me.ALL_MODELS)
    assert "ensemble/relative" in me.interval_summary(splits)
    ab = me.abstention_summary(splits, rng)
    assert set(ab["rankings"]) >= {"random", "ensemble_size", "disagreement"}
    miss = me.missing_summary(splits, rng)
    assert set(miss["models"]) == {"gb_indicators", "ensemble", "ensemble_gated"}


def test_load_cells_rejects_wrong_stride(monkeypatch) -> None:
    import pytest

    monkeypatch.setattr(me, "load_histories_with_meta", lambda *_: ({"stride": 7}, []))
    with pytest.raises(ValueError, match="fixed-stride"):
        me.load_cells()
