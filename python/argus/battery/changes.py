"""What changed between two saved assessments of the same battery."""

from __future__ import annotations

from typing import Any

SOH_TOLERANCE_POINTS = 0.5


def midpoint(report: dict[str, Any]) -> float | None:
    cycles = report.get("rul", {}).get("equivalent_cycles")
    return None if not cycles else (cycles[0] + cycles[1]) / 2


def compare_reports(older: dict[str, Any], newer: dict[str, Any]) -> dict[str, Any]:
    """Direction of capacity and remaining life; never a safety verdict."""
    if older["battery_id"] != newer["battery_id"]:
        raise ValueError("reports belong to different batteries")
    if older.get("cycle_axis") != newer.get("cycle_axis"):
        raise ValueError("reports use different cycle axes")
    change: dict[str, Any] = {
        "battery_id": newer["battery_id"],
        "soh_change_points": None,
        "capacity_direction": "unknown",
        "remaining_life_change_cycles": None,
        "remaining_life_direction": "unknown",
        "new_alerts": sorted(
            {a["code"] for a in newer["recommendations"] if a["priority"] == "urgent"}
            - {a["code"] for a in older["recommendations"] if a["priority"] == "urgent"}
        ),
    }
    if older["soh_pct"] is not None and newer["soh_pct"] is not None:
        delta = round(newer["soh_pct"] - older["soh_pct"], 3)
        change["soh_change_points"] = delta
        change["capacity_direction"] = (
            "unchanged"
            if abs(delta) <= SOH_TOLERANCE_POINTS
            else "improved"
            if delta > 0
            else "declined"
        )
    before, after = midpoint(older), midpoint(newer)
    if before is not None and after is not None:
        delta = round(after - before, 1)
        change["remaining_life_change_cycles"] = delta
        change["remaining_life_direction"] = (
            "unchanged" if delta == 0 else "longer" if delta > 0 else "shorter"
        )
    return change
