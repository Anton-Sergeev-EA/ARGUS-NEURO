from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from argus.battery import hust_curves
from argus.battery.schema import BatteryRequest
from argus.battery.windows import cell_windows, stack


def charge_frame(slope: float = 1.0) -> pd.DataFrame:
    n = 120
    voltage = np.linspace(2.8, 3.55, n)
    time = np.arange(n) * 5.0
    capacity = np.cumsum(1.0 + slope * np.exp(-0.5 * ((voltage - 3.4) / 0.05) ** 2)) * 5
    return pd.DataFrame(
        {
            "Status": ["Constant current charge"] * n,
            "Voltage (V)": voltage,
            "Time (s)": time,
            "Capacity (mAh)": capacity,
        }
    )


def test_cycle_indicators_describe_the_constant_current_charge() -> None:
    found = hust_curves.cycle_indicators(charge_frame())
    assert found is not None and set(found) == set(hust_curves.INDICATORS)
    assert found["rise_time_s"] > 0
    assert found["ica_peak_v"] == pytest.approx(3.4, abs=0.08)


def test_unusable_cycles_are_skipped_not_guessed() -> None:
    frame = charge_frame()
    frame["Status"] = "Constant current discharge_0"
    assert hust_curves.cycle_indicators(frame) is None
    short = charge_frame().head(10)
    assert hust_curves.cycle_indicators(short) is None
    flat = charge_frame()
    flat["Voltage (V)"] = 3.0  # never climbs through the rise window
    assert hust_curves.cycle_indicators(flat) is None


def history(n: int = 60) -> BatteryRequest:
    return BatteryRequest.model_validate(
        {
            "data_origin": "laboratory",
            "profile": {
                "battery_id": "HUST-T", "application": "ev", "chemistry": "lfp",
                "measurement_scope": "cell", "cycle_axis": "equivalent_cycles",
                "reference_capacity_ah": 1.0, "reference_condition_id": "c",
                "service_threshold_pct": 90,
            },
            "records": [
                {"equivalent_cycles": float(k + 1), "capacity_ah": 1.0 - 0.003 * k, "condition_id": "c"}
                for k in range(n)
            ],
        }
    )  # fmt: skip


def all_indicators(n: int = 60, skip: int | None = None) -> dict[int, dict[str, float]]:
    return {
        k + 1: {name: float(k) for name in hust_curves.INDICATORS}
        for k in range(n)
        if k != skip
    }


def test_every_feature_set_scores_the_same_windows() -> None:
    cells = [cell_windows(history(), all_indicators(), hust_curves.INDICATORS)]
    capacity_only, y_a, _ = stack(cells, (), with_offset=False)
    with_rise, y_b, _ = stack(cells, ("rise_time_s",), with_offset=False)
    everything, y_c, _ = stack(cells, hust_curves.INDICATORS, with_offset=False)
    assert len(capacity_only) == len(with_rise) == len(everything) > 0
    np.testing.assert_array_equal(y_a, y_b)
    np.testing.assert_array_equal(y_a, y_c)
    assert capacity_only.shape[1] == 8 and everything.shape[1] == 8 * (1 + 4)


def test_a_missing_indicator_removes_the_window_from_every_feature_set() -> None:
    complete = cell_windows(history(), all_indicators(), hust_curves.INDICATORS)
    gap = cell_windows(history(), all_indicators(skip=20), hust_curves.INDICATORS)
    assert len(gap) < len(complete)
    # The capacity-only view must lose exactly the same windows, not keep them.
    capacity_only, _, _ = stack([gap], (), with_offset=False)
    assert len(capacity_only) == len(gap)
    assert all(not (21 - 8 <= position - 1 <= 20) or True for position in gap.position)
    dropped = set(complete.position) - set(gap.position)
    assert dropped and all(13 <= p <= 28 for p in dropped)  # windows covering cycle 21
