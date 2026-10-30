"""Bounded local battery analysis API. No live hardware writes or implicit storage."""

from __future__ import annotations
import asyncio
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import ValidationError
from argus.battery.assessment import assess_battery
from argus.battery.changes import compare_reports
from argus.battery.fleet import requests_from_csv, triage
from argus.battery.profiles import USE_CASES, catalogue as use_case_catalogue
from argus.battery.ratelimit import limit_requests
from argus.battery.data import csv_origin, records_from_csv
from argus.battery.schema import BatteryRequest
from argus.battery.second_opinion import second_opinion
from argus.battery.public_data import (
    catalogue,
    load_public_history,
    validate_public_request,
)
from argus.battery.storage import BatteryStore

router = APIRouter(prefix="/api/battery", tags=["Battery health"])
STORE_PATH = (
    Path(__file__).resolve().parents[3]
    / "artifacts"
    / "battery-local"
    / "history.sqlite3"
)
MAX_BODY = 2_000_000


def assess_request(model: BatteryRequest) -> dict:
    try:
        source = validate_public_request(model)
    except FileNotFoundError as exc:
        raise HTTPException(503, detail="public_dataset_unavailable") from exc
    except ValueError as exc:
        raise HTTPException(422, detail="public_measurements_modified") from exc
    report = assess_battery(model)
    # A learned estimate is an extra, clearly labelled field; it never replaces the rest.
    report["second_opinion"] = second_opinion(model)
    if source is not None:
        report["dataset"] = source
    return report


@router.get("/datasets")
async def datasets() -> list[dict]:
    return catalogue()


@router.get("/datasets/{dataset_id}")
async def dataset(
    dataset_id: str, observations: int = Query(default=40, ge=8, le=2000)
) -> dict:
    try:
        model, source = await asyncio.to_thread(
            load_public_history, dataset_id, observations
        )
        return {"request": model.model_dump(mode="json"), "dataset": source}
    except FileNotFoundError as exc:
        raise HTTPException(503, detail="public_dataset_unavailable") from exc
    except ValueError as exc:
        raise HTTPException(422, detail="invalid_public_dataset") from exc


async def bounded_body(request: Request) -> bytes:
    content = bytearray()
    async for chunk in request.stream():
        content.extend(chunk)
        if len(content) > MAX_BODY:
            raise HTTPException(413, detail="input_too_large")
    return bytes(content)


async def parse_request(request: Request) -> BatteryRequest:
    try:
        return BatteryRequest.model_validate_json(await bounded_body(request))
    except ValidationError as exc:
        # Do not echo a user's full uploaded measurement history in errors.
        raise HTTPException(
            422,
            detail={
                "code": "invalid_battery_data",
                "fields": [".".join(map(str, e["loc"])) for e in exc.errors()],
            },
        ) from exc


@router.post("/analyze", dependencies=[Depends(limit_requests)])
async def analyze(request: Request) -> dict:
    model = await parse_request(request)
    return await asyncio.to_thread(assess_request, model)


@router.post("/save", dependencies=[Depends(limit_requests)])
async def save(request: Request) -> dict:
    model = await parse_request(request)
    report = await asyncio.to_thread(assess_request, model)
    report_id = await asyncio.to_thread(BatteryStore(STORE_PATH).save, report)
    return {"assessment_id": report_id, "storage": "local_only"}


@router.get("/history/{battery_id}")
async def history(battery_id: str) -> list[dict]:
    if len(battery_id) > 80:
        raise HTTPException(422, detail="invalid_battery_id")
    return await asyncio.to_thread(BatteryStore(STORE_PATH).list, battery_id)


@router.get("/history/{battery_id}/changes")
async def changes(battery_id: str) -> dict:
    """Compare the two newest saved reports of one battery."""
    if len(battery_id) > 80:
        raise HTTPException(422, detail="invalid_battery_id")
    saved = await asyncio.to_thread(BatteryStore(STORE_PATH).list, battery_id)
    if len(saved) < 2:
        raise HTTPException(404, detail="need_two_saved_reports")
    try:
        result = compare_reports(saved[1]["assessment"], saved[0]["assessment"])
    except ValueError as exc:
        raise HTTPException(422, detail="reports_not_comparable") from exc
    return {**result, "from": saved[1]["saved_at"], "to": saved[0]["saved_at"]}


@router.get("/use-cases")
async def use_cases() -> dict:
    """Editable starting values per use case, with an honest validation statement."""
    return use_case_catalogue()


@router.post("/fleet-csv", dependencies=[Depends(limit_requests)])
async def fleet_csv(
    request: Request,
    use_case: str = Query(default="ev"),
    plan_within_cycles: float | None = Query(default=None, gt=0, le=100000),
) -> dict:
    """Rank a fleet from a long-format CSV (one row per capacity test)."""
    if use_case not in USE_CASES:
        raise HTTPException(422, detail="unknown_use_case")
    try:
        text = (await bounded_body(request)).decode("utf-8-sig")
        requests = await asyncio.to_thread(requests_from_csv, text, use_case)
        return await asyncio.to_thread(triage, requests, plan_within_cycles)
    except (ValueError, UnicodeError, ValidationError) as exc:
        raise HTTPException(422, detail="invalid_fleet_csv") from exc


@router.post("/import-csv", dependencies=[Depends(limit_requests)])
async def import_csv(request: Request) -> dict:
    try:
        text = (await bounded_body(request)).decode("utf-8-sig")
        records = await asyncio.to_thread(records_from_csv, text)
        return {
            "records": [r.model_dump() for r in records],
            "data_origin": csv_origin(text),
        }
    except (ValueError, UnicodeError) as exc:
        raise HTTPException(422, detail="invalid_capacity_csv") from exc


@router.get("/example")
async def example() -> dict:
    # Explicit opt-in illustration, not a reading from a real EV.
    return {
        "profile": {
            "battery_id": "EXAMPLE-EV",
            "application": "ev",
            "chemistry": "unknown",
            "measurement_scope": "pack",
            "reference_capacity_ah": 100,
            "reference_condition_id": "same-control-test",
            "service_threshold_pct": 80,
            "equivalent_cycles_per_month": 20,
        },
        "records": [
            {
                "equivalent_cycles": float(i * 10),
                "capacity_ah": 100 - i * 0.4,
                "condition_id": "same-control-test",
                "temperature_c": 25,
            }
            for i in range(31)
        ],
        "bms": {"soc_pct": 60},
        "data_origin": "synthetic",
    }
