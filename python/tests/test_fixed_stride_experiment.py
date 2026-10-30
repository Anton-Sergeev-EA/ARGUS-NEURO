from __future__ import annotations

import numpy as np

from argus.battery import fixed_stride_experiment as fse


def fade(n: int, rate: float) -> tuple[np.ndarray, np.ndarray]:
    cycles = np.arange(1, n * fse.STRIDE, fse.STRIDE, dtype=float)
    return cycles, 1.0 - rate * np.arange(n)


def test_window_offsets_do_not_depend_on_the_length_of_the_history() -> None:
    short_c, short_q = fade(120, 0.002)
    long_c, long_q = fade(400, 0.0005)
    a = fse.windows(short_c, short_q, 1.0, None)
    b = fse.windows(long_c, long_q, 1.0, None)
    assert a and b
    np.testing.assert_array_equal(a["off"][0], b["off"][0])
    assert np.unique(a["off"][:, -1]).tolist() == [WINDOW_SPAN]


WINDOW_SPAN = (fse.WINDOW - 1) * fse.STRIDE / 100


def test_windows_end_before_the_event_and_target_counts_cycles() -> None:
    cycles, capacity = fade(150, 0.002)
    w = fse.windows(cycles, capacity, 1.0, None)
    event = fse.event_index(capacity, 1.0)
    assert event is not None
    assert w["pos"].max() < cycles[event]
    np.testing.assert_allclose(w["y"], cycles[event] - w["pos"])
    assert w["y"].min() > 0


def test_cells_that_never_cross_the_threshold_produce_no_windows() -> None:
    cycles, capacity = fade(100, 0.0001)
    assert fse.windows(cycles, capacity, 1.0, None) == {}


def test_indicator_channels_are_carried_with_nan_for_missing_values() -> None:
    cycles, capacity = fade(150, 0.002)
    indicators = np.ones((len(cycles), 4))
    indicators[10, 0] = np.nan
    w = fse.windows(cycles, capacity, 1.0, indicators)
    assert w["ind"].shape[1:] == (fse.WINDOW, 4)
    assert np.isnan(w["ind"]).any()


def test_every_cell_is_tested_once_and_partitions_are_disjoint() -> None:
    names = [f"c{i}" for i in range(77)]
    folds = fse.make_folds(names)
    tested = [n for f in folds for n in f["test"]]
    assert sorted(tested) == sorted(names)
    for f in folds:
        groups = [set(f[k]) for k in ("train", "validation", "calibration", "test")]
        assert sum(len(g) for g in groups) == len(names)
        assert set.union(*groups) == set(names)
    assert fse.make_folds(names) == folds


def test_conformal_radius_uses_the_finite_sample_rank() -> None:
    scores = np.arange(1.0, 20.0)
    assert fse.conformal_radius(scores) == 18.0
    assert fse.conformal_radius(np.array([1.0, 2.0])) == 2.0


def test_interval_score_penalises_misses_and_width() -> None:
    y = np.array([5.0, 20.0])
    low, high = np.array([0.0, 0.0]), np.array([10.0, 10.0])
    score = fse.interval_score(y, low, high, 0.1)
    assert score[0] == 10.0
    assert score[1] == 10.0 + 20.0 * 10.0


def test_macro_averages_cells_not_windows() -> None:
    cells = np.array(["a", "a", "a", "b"])
    error = np.array([1.0, 1.0, 1.0, 5.0])
    values = fse.macro(cells, error)
    assert values == {"a": 1.0, "b": 5.0}
