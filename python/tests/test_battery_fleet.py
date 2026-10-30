from __future__ import annotations

import asyncio

import httpx
import pytest
from fastapi import FastAPI

from argus.battery import api as battery_api
from argus.battery.assessment import assess_battery
from argus.battery.fleet import MAX_BATTERIES, priority_of, requests_from_csv, triage
from argus.battery.profiles import USE_CASES
from argus.battery.schema import BatteryRequest

HEADER = "battery_id,equivalent_cycles,capacity_ah,reference_capacity_ah,condition_id\n"


def rows(
    battery_id: str, reference: float, soh_values: list[float], step: float = 20.0
) -> str:
    return "".join(
        f"{battery_id},{i * step},{reference * s / 100:.4f},{reference},swap-test\n"
        for i, s in enumerate(soh_values)
    )


def fleet_csv() -> str:
    return (
        HEADER
        + rows(
            "S-OLD", 10, [78, 76, 74, 72, 70, 68, 66, 64, 62, 60]
        )  # below the 70% scooter threshold
        + rows(
            "S-NEAR", 10, [90, 88, 86, 84, 82, 80, 78, 76, 74, 72.5]
        )  # within the 8-point margin
        + rows("S-NEW", 10, [100, 99.9, 99.8, 99.7, 99.6, 99.5, 99.4, 99.3, 99.2, 99.1])
        + rows("S-ONE", 10, [95])  # a single test: SOH is known, no forecast
    )


def test_csv_groups_rows_by_battery_and_applies_the_use_case() -> None:
    requests = requests_from_csv(fleet_csv(), "scooter")
    assert [r.profile.battery_id for r in requests] == [
        "S-OLD",
        "S-NEAR",
        "S-NEW",
        "S-ONE",
    ]
    assert all(r.profile.application == "scooter" for r in requests)
    assert (
        requests[0].profile.service_threshold_pct
        == USE_CASES["scooter"]["service_threshold_pct"]
    )
    assert len(requests[0].records) == 10 and len(requests[3].records) == 1


def test_triage_orders_by_urgency_and_explains_why() -> None:
    result = triage(requests_from_csv(fleet_csv(), "scooter"))
    order = [r["battery_id"] for r in result["rows"]]
    assert order == ["S-OLD", "S-NEAR", "S-ONE", "S-NEW"] or order[:2] == [
        "S-OLD",
        "S-NEAR",
    ]
    by_id = {r["battery_id"]: r for r in result["rows"]}
    assert by_id["S-OLD"]["priority"] == "service_now"
    assert "below_service_threshold" in by_id["S-OLD"]["reasons"]
    assert by_id["S-NEAR"]["priority"] == "plan_service"
    assert by_id["S-NEAR"]["reasons"] == ["approaching_threshold"]
    assert by_id["S-NEW"]["priority"] == "monitor"
    assert (
        by_id["S-ONE"]["priority"] == "monitor"
        and by_id["S-ONE"]["forecast_status"] == "insufficient_history"
    )
    assert result["counts"]["service_now"] == 1 and sum(result["counts"].values()) == 4
    assert "ranking_is_decision_support_not_an_instruction" in result["limits"]


def test_forecast_inside_the_planning_horizon_moves_a_battery_up() -> None:
    requests = requests_from_csv(
        HEADER + rows("P-1", 10, [100 - 0.4 * i for i in range(30)], step=10),
        "power_bank",
    )
    relaxed = triage(requests)["rows"][0]
    strict = triage(requests, plan_within_cycles=10000)["rows"][0]
    assert relaxed["priority"] == "monitor"
    assert strict["priority"] == "plan_service"
    assert strict["reasons"] == ["forecast_within_planning_horizon"]


def test_rescue_drone_gets_an_assignment_advisory_near_its_threshold() -> None:
    requests = requests_from_csv(
        HEADER + rows("D-1", 5, [95, 93, 91, 90, 89, 88, 87.5, 87]), "rescue_uav"
    )
    report = assess_battery(requests[0])
    codes = {a["code"] for a in report["recommendations"]}
    assert {"approaching_threshold", "mission_assignment"} <= codes
    assert report["safety_state"] == "not_assessed"
    scooter = assess_battery(
        requests_from_csv(
            HEADER + rows("D-1", 5, [95, 93, 91, 90, 89, 88, 87.5, 87]), "scooter"
        )[0]
    )
    assert "mission_assignment" not in {a["code"] for a in scooter["recommendations"]}


def test_invalid_fleets_are_rejected() -> None:
    with pytest.raises(ValueError):
        requests_from_csv("a,b\n1,2\n", "ev")
    with pytest.raises(ValueError):
        requests_from_csv(fleet_csv(), "toaster")
    with pytest.raises(ValueError):
        triage([])
    one = requests_from_csv(HEADER + rows("X", 10, [90]), "ev")[0]
    with pytest.raises(ValueError):
        triage([one, one])
    many = [one.model_copy(deep=True) for _ in range(MAX_BATTERIES + 1)]
    for i, m in enumerate(many):
        m.profile.battery_id = f"B{i}"
    with pytest.raises(ValueError):
        triage(many)
    broken = HEADER + "Z,1,2,3,c\nZ,1,3,3,c\n"  # duplicate cycle index
    with pytest.raises(Exception):
        requests_from_csv(broken, "ev")


def test_priority_helper_handles_no_data() -> None:
    request = BatteryRequest.model_validate(
        {
            "profile": {
                "battery_id": "E",
                "reference_capacity_ah": 1,
                "reference_condition_id": "c",
            }
        }
    )
    assert priority_of(assess_battery(request), None)[0] == "insufficient_data"


def test_http_fleet_and_use_case_catalogue() -> None:
    app = FastAPI()
    app.include_router(battery_api.router)

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://t"
        ) as c:
            catalogue = (await c.get("/api/battery/use-cases")).json()
            assert set(catalogue["use_cases"]) == {
                "ev",
                "scooter",
                "power_bank",
                "rescue_uav",
                "uav",
            }
            assert "No data from vehicles" in catalogue["validation"]
            ok = await c.post(
                "/api/battery/fleet-csv?use_case=scooter", content=fleet_csv()
            )
            assert (
                ok.status_code == 200 and ok.json()["rows"][0]["battery_id"] == "S-OLD"
            )
            assert (
                await c.post(
                    "/api/battery/fleet-csv?use_case=nope", content=fleet_csv()
                )
            ).status_code == 422
            assert (
                await c.post("/api/battery/fleet-csv", content="bad\n1")
            ).status_code == 422
            assert (
                await c.post("/api/battery/fleet-csv", content=b"x" * 2_000_001)
            ).status_code == 413

    asyncio.run(scenario())
