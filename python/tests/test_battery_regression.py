"""Fixed-number regression baselines and invariants of the capacity projection."""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from argus.battery.assessment import assess_battery
from argus.battery.public_data import DATA_DIR, load_public_history
from argus.battery.schema import BatteryRequest

GOLDEN = Path(__file__).parent / "golden" / "nasa_assessment.json"
CELLS = ["nasa-B0005", "nasa-B0006", "nasa-B0007", "nasa-B0018"]
PREFIXES = [40, 80, 120]
KEYS = ("soh_pct", "capacity_state")


def digest(report: dict) -> dict:
    return {
        **{k: report[k] for k in KEYS},
        "trend": report["trend"],
        "rul": {k: report["rul"].get(k) for k in ("status", "equivalent_cycles")},
    }


def cache_present() -> bool:
    return all((DATA_DIR / f"{c.removeprefix('nasa-')}.json").exists() for c in CELLS)


@pytest.mark.skipif(not cache_present(), reason="NASA cache is not installed")
def test_nasa_assessments_match_recorded_baseline() -> None:
    current = {}
    for cell in CELLS:
        for n in PREFIXES:
            request, _ = load_public_history(cell, n)
            current[f"{cell}:{n}"] = digest(assess_battery(request))
    if os.environ.get("ARGUS_UPDATE_GOLDEN") == "1":
        GOLDEN.write_text(json.dumps(current, indent=1, sort_keys=True) + "\n")
    recorded = json.loads(GOLDEN.read_text())
    assert current.keys() == recorded.keys()
    for key, value in current.items():
        assert json.loads(json.dumps(value)) == recorded[key], key


def build(
    cycles: np.ndarray, soh: np.ndarray, threshold: float = 80.0
) -> BatteryRequest:
    return BatteryRequest.model_validate(
        {
            "profile": {
                "battery_id": "prop",
                "reference_capacity_ah": 100,
                "reference_condition_id": "c",
                "service_threshold_pct": threshold,
            },
            "records": [
                {
                    "equivalent_cycles": float(c),
                    "capacity_ah": float(s),
                    "condition_id": "c",
                }
                for c, s in zip(cycles, soh)
            ],
        }
    )


@st.composite
def aging_curves(draw):
    n = draw(st.integers(10, 60))
    step = draw(st.floats(5, 50))
    total_loss = draw(st.floats(0.5, 45))
    noise = draw(st.floats(0, 0.3))
    seed = draw(st.integers(0, 10_000))
    x = np.arange(n) * step
    slope = total_loss / x[-1]
    rng = np.random.default_rng(seed)
    return x, 100 - slope * x + rng.normal(0, noise, n)


FAST = settings(
    max_examples=40, deadline=None, suppress_health_check=[HealthCheck.too_slow]
)


@FAST
@given(aging_curves())
def test_report_is_deterministic_and_json_safe(curve) -> None:
    request = build(*curve)
    first, second = assess_battery(request), assess_battery(request)
    assert first == second
    json.dumps(first, allow_nan=False)


@FAST
@given(aging_curves(), st.floats(0, 5000))
def test_shifting_the_cycle_axis_does_not_change_the_projection(curve, shift) -> None:
    x, y = curve
    a = assess_battery(build(x, y))
    b = assess_battery(build(x + shift, y))
    assert a["soh_pct"] == b["soh_pct"]
    assert a["rul"]["status"] == b["rul"]["status"]
    if a["rul"]["equivalent_cycles"]:
        np.testing.assert_allclose(
            a["rul"]["equivalent_cycles"], b["rul"]["equivalent_cycles"], atol=0.2
        )


@FAST
@given(aging_curves())
def test_interval_is_ordered_and_non_negative(curve) -> None:
    rul = assess_battery(build(*curve))["rul"]
    if rul["status"] == "conditional_estimate":
        low, high = rul["equivalent_cycles"]
        assert 0 <= low <= high


@FAST
@given(aging_curves())
def test_a_lower_threshold_never_shortens_remaining_life(curve) -> None:
    near = assess_battery(build(*curve, threshold=85))["rul"]
    far = assess_battery(build(*curve, threshold=70))["rul"]
    if near["status"] == far["status"] == "conditional_estimate":
        assert far["equivalent_cycles"][0] >= near["equivalent_cycles"][0] - 0.2
        assert far["equivalent_cycles"][1] >= near["equivalent_cycles"][1] - 0.2


@FAST
@given(aging_curves(), st.floats(0.5, 20))
def test_soh_is_invariant_to_units_of_capacity(curve, factor) -> None:
    x, y = curve
    base = build(x, y)
    scaled = base.model_copy(deep=True)
    scaled.profile.reference_capacity_ah *= factor
    for record in scaled.records:
        record.capacity_ah *= factor
    assert assess_battery(base)["soh_pct"] == pytest.approx(
        assess_battery(scaled)["soh_pct"], abs=0.011
    )
