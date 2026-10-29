from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from argus.battery import api as battery_api
from argus.battery.assessment import REPORT_SCHEMA_VERSION, assess_battery
from argus.battery.changes import compare_reports
from argus.battery.ratelimit import SlidingWindow
from argus.battery.schema import BatteryRequest
from argus.battery.storage import BatteryStore


def report(drop: float = 0.4, battery_id: str = "EXAMPLE-EV") -> dict:
    data = asyncio.run(battery_api.example())
    data["profile"]["battery_id"] = battery_id
    for i, row in enumerate(data["records"]):
        row["capacity_ah"] = 100 - i * drop
    return assess_battery(BatteryRequest.model_validate(data))


def test_reports_carry_the_current_schema_version() -> None:
    assert report()["schema_version"] == REPORT_SCHEMA_VERSION == 2


def test_store_keeps_a_timeline_and_collapses_only_immediate_repeats(
    tmp_path: Path,
) -> None:
    store = BatteryStore(tmp_path / "h.sqlite3")
    a, b = report(0.4), report(0.5)
    for item in (a, a, b, a):
        store.save(item)
    saved = store.list("EXAMPLE-EV")
    assert [s["assessment"]["assessment_id"] for s in saved] == [
        a["assessment_id"],
        b["assessment_id"],
        a["assessment_id"],
    ]


def test_store_uses_an_index_and_bounded_listing(tmp_path: Path) -> None:
    store = BatteryStore(tmp_path / "h.sqlite3")
    for i in range(60):
        store.save(report(0.1 + i * 0.001))
    assert len(store.list("EXAMPLE-EV")) == 50
    with sqlite3.connect(store.path) as db:
        plan = db.execute(
            "EXPLAIN QUERY PLAN SELECT * FROM reports WHERE battery_id=? ORDER BY seq DESC",
            ("x",),
        ).fetchall()
    assert any("reports_by_battery" in str(row) for row in plan)


def test_legacy_database_is_migrated_without_losing_reports(tmp_path: Path) -> None:
    path = tmp_path / "old.sqlite3"
    old = report()
    with sqlite3.connect(path) as db:
        db.execute(
            "CREATE TABLE assessments (id TEXT PRIMARY KEY,battery_id TEXT NOT NULL,"
            "created_at TEXT NOT NULL,report TEXT NOT NULL)"
        )
        db.execute(
            "INSERT INTO assessments VALUES (?,?,?,?)",
            (
                old["assessment_id"],
                old["battery_id"],
                "2026-01-01T00:00:00+00:00",
                json.dumps(old),
            ),
        )
    store = BatteryStore(path)
    assert store.list("EXAMPLE-EV")[0]["saved_at"] == "2026-01-01T00:00:00+00:00"
    store.save(report(0.5))
    assert len(store.list("EXAMPLE-EV")) == 2
    with sqlite3.connect(path) as db:
        names = {
            r[0]
            for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    assert "assessments" not in names


def test_comparison_reports_direction_without_a_safety_verdict() -> None:
    older, newer = report(0.3), report(0.5)
    change = compare_reports(older, newer)
    assert change["capacity_direction"] == "declined"
    assert change["soh_change_points"] < 0
    assert change["remaining_life_direction"] in {"shorter", "unknown"}
    assert compare_reports(older, older)["capacity_direction"] == "unchanged"
    other = report(battery_id="OTHER")
    with pytest.raises(ValueError):
        compare_reports(older, other)


def test_sliding_window_blocks_then_recovers() -> None:
    window = SlidingWindow(limit=2, window=10)
    assert window.check("a", now=0) is None
    assert window.check("a", now=1) is None
    wait = window.check("a", now=2)
    assert wait is not None and wait == pytest.approx(8)
    assert window.check("b", now=2) is None  # other clients are independent
    assert window.check("a", now=10.5) is None


def test_http_changes_and_rate_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(battery_api, "STORE_PATH", tmp_path / "h.sqlite3")
    from argus.battery import ratelimit

    monkeypatch.setattr(ratelimit, "LIMITER", SlidingWindow(limit=4))
    app = FastAPI()
    app.include_router(battery_api.router)

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://t"
        ) as c:
            data = (await c.get("/api/battery/example")).json()
            assert (
                await c.get("/api/battery/history/EXAMPLE-EV/changes")
            ).status_code == 404
            assert (await c.post("/api/battery/save", json=data)).status_code == 200
            data["records"][-1]["capacity_ah"] = 70  # a new, lower measurement
            assert (await c.post("/api/battery/save", json=data)).status_code == 200
            result = await c.get("/api/battery/history/EXAMPLE-EV/changes")
            assert result.status_code == 200
            assert result.json()["capacity_direction"] == "declined"
            assert (await c.post("/api/battery/analyze", json=data)).status_code == 200
            assert (await c.post("/api/battery/analyze", json=data)).status_code == 200
            blocked = await c.post("/api/battery/analyze", json=data)
            assert blocked.status_code == 429
            assert int(blocked.headers["Retry-After"]) >= 1

    asyncio.run(scenario())
