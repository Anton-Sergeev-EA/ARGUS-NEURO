from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from argus.battery import hust_curves, indicator_experiment
from argus.battery.schema import BatteryRequest


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


def test_windows_end_before_the_event_and_carry_the_extra_channels() -> None:
    h = history()
    indicators = {
        k + 1: {n: float(k) for n in hust_curves.INDICATORS} for k in range(60)
    }
    plain_x, plain_y = indicator_experiment.windows(h, indicators, ())
    full_x, full_y = indicator_experiment.windows(h, indicators, hust_curves.INDICATORS)
    assert plain_x.shape[1] == 8 * 2 and full_x.shape[1] == 8 * (2 + 4)
    np.testing.assert_array_equal(plain_y, full_y)  # identical windows and targets
    assert plain_y.min() > 0  # every window ends strictly before the threshold


def test_windows_with_missing_indicators_are_dropped_for_every_set_equally() -> None:
    h = history()
    indicators = {
        k + 1: {n: 1.0 for n in hust_curves.INDICATORS} for k in range(60) if k != 20
    }
    with_gap, _ = indicator_experiment.windows(h, indicators, ("rise_time_s",))
    without, _ = indicator_experiment.windows(h, indicators, ())
    assert len(with_gap) < len(without)
