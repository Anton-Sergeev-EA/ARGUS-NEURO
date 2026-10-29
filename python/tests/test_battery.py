from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import numpy as np
import pytest
from fastapi import FastAPI
from pydantic import ValidationError

from argus.battery.api import example, router
from argus.battery.assessment import assess_battery
from argus.battery.data import csv_origin, records_from_csv
from argus.battery.schema import BatteryRequest
from argus.battery.storage import BatteryStore


def history() -> dict:
    return asyncio.run(example())


def test_ev_capacity_and_conditional_life_are_not_soc() -> None:
    report = assess_battery(BatteryRequest.model_validate(history()))
    assert report["soh_pct"] == 88.0
    assert report["soc_pct"] == 60
    assert report["safety_state"] == "not_assessed"
    assert report["rul"]["status"] == "conditional_estimate"
    np.testing.assert_allclose(report["rul"]["equivalent_cycles"], [200, 200])
    np.testing.assert_allclose(report["rul"]["months"], [10, 10])
    assert report["source"] == "synthetic"


def test_threshold_is_configurable_and_not_a_safety_verdict() -> None:
    data = history()
    data["profile"]["service_threshold_pct"] = 90
    report = assess_battery(BatteryRequest.model_validate(data))
    assert report["capacity_state"] == "below_service_threshold"
    assert report["rul"]["status"] == "threshold_reached"
    assert report["safety_state"] == "not_assessed"
    assert any(r["code"] == "capacity_service" for r in report["recommendations"])


@pytest.mark.parametrize("size", [0, 1, 7])
def test_short_history_abstains(size: int) -> None:
    data = history()
    data["records"] = data["records"][:size]
    report = assess_battery(BatteryRequest.model_validate(data))
    assert report["rul"]["equivalent_cycles"] is None
    assert report["rul"]["status"] == "insufficient_history"


def test_conditions_are_filtered_and_reference_errors_stop_forecast() -> None:
    data = history()
    data["records"][-1]["condition_id"] = "cold-test"
    report = assess_battery(BatteryRequest.model_validate(data))
    assert report["data_quality"]["excluded_records"] == 1
    assert report["soh_pct"] == 88.4
    assert report["rul"]["equivalent_cycles"] is None
    data = history()
    data["profile"]["reference_capacity_ah"] = 50
    report = assess_battery(BatteryRequest.model_validate(data))
    assert "check_reference_capacity" in report["data_quality"]["warnings"]
    assert report["rul"]["equivalent_cycles"] is None


def test_flat_or_accelerating_history_has_no_lifetime_number() -> None:
    data = history()
    for row in data["records"]:
        row["capacity_ah"] = 95
    assert (
        assess_battery(BatteryRequest.model_validate(data))["rul"]["status"]
        == "no_reliable_decline"
    )
    for i, row in enumerate(data["records"]):
        row["capacity_ah"] = 100 - 0.1 * i - 0.01 * i**2
    report = assess_battery(BatteryRequest.model_validate(data))
    assert report["rul"]["status"] == "changing_trend"
    assert report["rul"]["equivalent_cycles"] is None


def test_distant_projection_is_suppressed() -> None:
    data = history()
    for i, row in enumerate(data["records"]):
        row["capacity_ah"] = 100 - i * 0.02
    report = assess_battery(BatteryRequest.model_validate(data))
    assert report["rul"]["status"] == "beyond_observed_horizon"


def test_bms_alert_blocks_life_and_model_limits_drive_recommendations() -> None:
    data = history()
    data["profile"]["limits"] = {
        "source": "Manufacturer manual section 4",
        "charge_min_c": 0,
        "charge_max_c": 45,
        "cell_spread_limit_mv": 100,
    }
    data["bms"].update(temperature_c=50, charging=True, cell_spread_mv=150)
    report = assess_battery(BatteryRequest.model_validate(data))
    assert report["rul"]["status"] == "operating_alert"
    assert report["rul"]["equivalent_cycles"] is None
    assert report["safety_state"] == "attention"
    codes = {r["code"] for r in report["recommendations"]}
    assert {"charge_too_hot", "cell_imbalance"} <= codes
    data["bms"]["temperature_c"] = -5
    report = assess_battery(BatteryRequest.model_validate(data))
    assert any(r["code"] == "charge_too_cold" for r in report["recommendations"])


def test_optimization_uses_reported_behavior_not_invented_life_gain() -> None:
    data = history()
    data["bms"].update(
        high_soc_hot_storage_reported=True, frequent_fast_charging_reported=True
    )
    report = assess_battery(BatteryRequest.model_validate(data))
    codes = {r["code"] for r in report["recommendations"]}
    assert {"hot_storage", "charging_plan", "manufacturer_profile"} <= codes
    assert not any("gain_months" in r for r in report["recommendations"])


def test_cell_test_index_is_never_converted_to_calendar_months() -> None:
    data = history()
    data["profile"].update(
        measurement_scope="cell",
        cycle_axis="discharge_test_index",
        equivalent_cycles_per_month=None,
    )
    report = assess_battery(BatteryRequest.model_validate(data))
    assert report["measurement_scope"] == "cell"
    assert report["rul"]["months"] is None
    data["profile"]["equivalent_cycles_per_month"] = 20
    with pytest.raises(ValidationError):
        BatteryRequest.model_validate(data)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -1, 0])
def test_invalid_capacities_are_rejected(bad: float) -> None:
    data = history()
    data["records"][0]["capacity_ah"] = bad
    with pytest.raises(ValidationError):
        BatteryRequest.model_validate(data)


def test_duplicate_or_reversed_cycles_are_rejected() -> None:
    data = history()
    data["records"][1]["equivalent_cycles"] = 0
    with pytest.raises(ValidationError):
        BatteryRequest.model_validate(data)


def test_csv_validation_and_example_provenance() -> None:
    text = "equivalent_cycles,capacity_ah,condition_id,data_origin\n0,100,normal,synthetic\n"
    assert len(records_from_csv(text)) == 1
    assert csv_origin(text) == "synthetic"
    assert csv_origin(text.replace("synthetic", "laboratory")) == "user_supplied"
    for bad in (
        "x,y\n1,2",
        text.replace("100", "nan"),
        text.replace("100,normal", "100"),
    ):
        with pytest.raises(ValueError):
            records_from_csv(bad)


def test_local_store_is_opt_in_and_isolates_batteries(tmp_path: Path) -> None:
    path = tmp_path / "local" / "history.sqlite3"
    store = BatteryStore(path)
    assert store.list("missing") == []
    assert not path.exists()
    report = assess_battery(BatteryRequest.model_validate(history()))
    store.save(report)
    store.save(report)
    assert len(store.list(report["battery_id"])) == 1
    assert store.list("' OR 1=1 --") == []


def test_http_analysis_import_and_errors() -> None:
    app = FastAPI()
    app.include_router(router)

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            data = (await client.get("/api/battery/example")).json()
            response = await client.post("/api/battery/analyze", json=data)
            assert response.status_code == 200
            assert response.json()["soh_pct"] == 88
            response = await client.post("/api/battery/analyze", json={"records": []})
            assert response.status_code == 422
            assert "fields" in response.json()["detail"]
            response = await client.post(
                "/api/battery/import-csv", content="bad,csv\n1,2"
            )
            assert response.status_code == 422
            response = await client.post(
                "/api/battery/analyze", content=b"x" * 2_000_001
            )
            assert response.status_code == 413

    asyncio.run(scenario())


def test_linear_window_baseline_recovers_a_straight_fade() -> None:
    from argus.battery.training import MAX_LINEAR_CYCLES, linear_window_prediction

    axis = np.arange(8) * 10.0
    soh = 100 - 0.05 * axis  # 0.05 points per cycle
    window = np.stack([soh / 100, axis / 100, np.zeros(8), np.zeros(8)], axis=1)
    predicted = linear_window_prediction(window[None], 90.0)
    last_soh = soh[-1]
    assert predicted[0] == pytest.approx((last_soh - 90.0) / 0.05)
    flat = window.copy()
    flat[:, 0] = 0.95
    assert linear_window_prediction(flat[None], 90.0)[0] == MAX_LINEAR_CYCLES
