"""The thinning rule and the window constructor must not depend on the future."""

from __future__ import annotations

import json

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from argus.battery import (
    calb,
    hust_curves,
    indicator_experiment,
    sampling,
    second_opinion,
)
from argus.battery.schema import BatteryRequest
from argus.battery.training import asset_split
from argus.battery.windows import cell_windows, stack


def fade(n: int, rate: float = 0.001) -> np.ndarray:
    return 1.0 - rate * np.arange(n)


@pytest.mark.parametrize("cut", [37, 120, 411, 999])
def test_fixed_stride_keeps_the_same_cycles_whatever_the_history_length(
    cut: int,
) -> None:
    ids = np.arange(1, 1501, dtype=float)
    full, _, _ = sampling.thin(ids, ids, 5)
    truncated, _, _ = sampling.thin(ids[:cut], ids[:cut], 5)
    np.testing.assert_array_equal(truncated, full[: len(truncated)])
    assert len(truncated) == len(range(1, cut + 1, 5))


def test_a_short_and_a_long_history_share_spacing_and_cycle_numbers() -> None:
    short = calb.to_history("S", 25.0, fade(300))
    long = calb.to_history("L", 25.0, fade(3000))
    a = [r.equivalent_cycles for r in short.records]
    b = [r.equivalent_cycles for r in long.records]
    assert np.unique(np.diff(a)).tolist() == [5.0] == np.unique(np.diff(b)).tolist()
    assert b[: len(a)] == a


def test_the_legacy_stride_does_depend_on_length_and_is_labelled() -> None:
    ids = np.arange(1, 3001, dtype=float)
    long_ids, _, info = sampling.thin(ids, ids, "adaptive")
    short_ids, _, _ = sampling.thin(ids[:300], ids[:300], "adaptive")
    assert (
        np.diff(long_ids)[0] != np.diff(short_ids)[0]
    )  # the leak the new rule removes
    assert info["diagnostic_only"] is True and info["sampling"] == sampling.ADAPTIVE
    assert sampling.thin(ids, ids, 5)[2]["diagnostic_only"] is False
    with pytest.raises(ValueError):
        sampling.keep_mask(ids, 0)


def history(n: int = 90, rate: float = 0.004) -> BatteryRequest:
    return BatteryRequest.model_validate(
        {
            "data_origin": "laboratory",
            "profile": {
                "battery_id": "HUST-X", "application": "ev", "chemistry": "lfp",
                "measurement_scope": "cell", "cycle_axis": "equivalent_cycles",
                "reference_capacity_ah": 1.0, "reference_condition_id": "c",
                "service_threshold_pct": 90,
            },
            "records": [
                {"equivalent_cycles": float(5 * k + 1), "capacity_ah": 1.0 - rate * k, "condition_id": "c"}
                for k in range(n)
            ],
        }
    )  # fmt: skip


def indicators(h: BatteryRequest, scale: float = 1.0) -> dict[int, dict[str, float]]:
    return {
        int(r.equivalent_cycles): {
            n: scale * (i + j) for j, n in enumerate(hust_curves.INDICATORS)
        }
        for i, r in enumerate(h.records)
    }


def test_windows_use_nothing_recorded_after_their_last_point() -> None:
    h = history()
    base = cell_windows(h, indicators(h), hust_curves.INDICATORS)
    # Corrupt everything after record 60: windows ending earlier must not change.
    changed = h.model_copy(deep=True)
    for r in changed.records[60:]:
        r.capacity_ah *= 0.5
    altered = indicators(h)
    for cycle in list(altered)[60:]:
        altered[cycle] = {n: -1e9 for n in hust_curves.INDICATORS}
    other = cell_windows(changed, altered, hust_curves.INDICATORS)
    early = base.position <= h.records[59].equivalent_cycles
    n = int(early.sum())
    assert n > 10
    np.testing.assert_array_equal(base.capacity[:n], other.capacity[:n])
    for name in hust_curves.INDICATORS:
        np.testing.assert_array_equal(
            base.indicators[name][:n], other.indicators[name][:n]
        )
    assert np.all(base.position < base.event_cycle) and np.all(base.target > 0)
    np.testing.assert_allclose(base.target, base.event_cycle - base.position)


def test_censored_cells_produce_no_windows_instead_of_fake_failures() -> None:
    flat = history(rate=0.0)
    w = cell_windows(flat, indicators(flat), hust_curves.INDICATORS)
    assert len(w) == 0 and w.censored and w.event_cycle is None


def test_the_scaler_sees_training_cells_only() -> None:
    cells = [
        cell_windows(
            history(rate=0.002 + 0.0005 * i),
            indicators(history(), scale=1 + i),
            hust_curves.INDICATORS,
        )
        for i in range(6)
    ]
    for c, i in zip(cells, range(6)):
        object.__setattr__(c, "cell_id", f"C{i}")
    train, test = cells[:4], cells[4:]
    scaler, _ = indicator_experiment.fit_model(train, hust_curves.INDICATORS)
    x_train, _, _ = stack(train, hust_curves.INDICATORS, with_offset=False)
    x_all, _, _ = stack(cells, hust_curves.INDICATORS, with_offset=False)
    np.testing.assert_allclose(scaler.mean_, x_train.mean(axis=0))
    assert not np.allclose(scaler.mean_, x_all.mean(axis=0))
    assert len(test) == 2


def test_group_splits_are_reproducible_disjoint_and_seed_dependent() -> None:
    cells = [history(rate=0.003 + 0.0001 * i) for i in range(20)]
    for i, c in enumerate(cells):
        c.profile.battery_id = f"HUST-{i}"
    a, b = asset_split(cells, 41), asset_split(cells, 41)
    ids = lambda s: {k: [h.profile.battery_id for h in v] for k, v in s.items()}  # noqa: E731
    assert ids(a) == ids(b)
    members = [m for group in ids(a).values() for m in group]
    assert len(members) == len(set(members)) == 20
    assert ids(asset_split(cells, 42)) != ids(a)


def test_caches_describe_their_sampling_and_diagnostic_ones_are_refused(
    tmp_path: Path,
) -> None:
    h = history()
    legacy = tmp_path / "legacy.json"
    legacy.write_text(json.dumps([h.model_dump(mode="json")]))
    meta, _ = sampling.read_cache(legacy)
    assert meta["diagnostic_only"] is True
    with pytest.raises(ValueError, match="length-dependent"):
        second_opinion.train(legacy, tmp_path / "model")
    fixed = tmp_path / "fixed.json"
    sampling.write_cache(
        fixed,
        {"sampling": sampling.FIXED, "stride": 5, "diagnostic_only": False},
        [h.model_dump(mode="json")],
    )
    assert sampling.read_cache(fixed)[0]["stride"] == 5
    mismatched = tmp_path / "ind.json"
    sampling.write_cache(mismatched, {"sampling": sampling.FIXED, "stride": 3}, {})
    with pytest.raises(ValueError, match="thinned differently"):
        indicator_experiment.run(fixed, mismatched)
    with pytest.raises(ValueError, match="length-dependent"):
        indicator_experiment.run(legacy, legacy)


def test_calb_keeps_physical_cycle_numbers_when_a_zero_row_is_dropped(
    tmp_path: Path,
) -> None:
    n = 40
    capacity = [60.0 - 0.01 * k for k in range(n)]
    capacity[10] = (
        0.0  # a failed measurement: dropped, but later cycles keep their numbers
    )
    frame = pd.DataFrame(
        {
            "B100": [None] * n,
            "圈数": list(
                range(2, n + 2)
            ),  # the counter starts at 2, like the CALB sheets
            "放电容量(Ah)": capacity,
        }
    )
    path = tmp_path / "w.xlsx"
    with pd.ExcelWriter(path) as writer:
        frame.to_excel(writer, sheet_name="35℃ 循环", index=False)
    series = calb.discharge_series(path)["B100"]
    assert series["cycle_id_source"] == "xlsx_counter_column"
    assert series["nonpositive_dropped"] == 1
    assert (
        series["cycle_ids"][0] == 2 and 12 not in series["cycle_ids"]
    )  # row 10 carried cycle 12
    history = calb.to_history(
        "B100", 35.0, series["capacity_ah"], cycle_ids=series["cycle_ids"], stride=5
    )
    assert [r.equivalent_cycles for r in history.records][:3] == [6.0, 11.0, 16.0]
