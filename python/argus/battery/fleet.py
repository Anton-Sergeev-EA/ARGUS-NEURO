"""Rank a fleet of batteries by what needs attention first.

Scooter operators, rental power-bank networks, drone services and EV fleets all ask
the same question: which of these hundred packs do I look at today? Each battery is
assessed with the same explainable routine as a single report; this module only
orders the results and states why.
"""

from __future__ import annotations

import csv
import io
from collections import Counter, defaultdict
from typing import Any

from argus.battery.assessment import assess_battery
from argus.battery.profiles import USE_CASES
from argus.battery.schema import BatteryRequest

MAX_BATTERIES = 300
PRIORITY_ORDER = ("service_now", "plan_service", "monitor", "insufficient_data")
FLEET_COLUMNS = {
    "battery_id",
    "equivalent_cycles",
    "capacity_ah",
    "reference_capacity_ah",
}
OPTIONAL_TEXT = {"condition_id", "chemistry", "application"}


def priority_of(
    report: dict[str, Any], plan_within_cycles: float | None
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    codes = {a["code"] for a in report["recommendations"]}
    if report["soh_pct"] is None:
        return "insufficient_data", ["no_comparable_measurements"]
    if report["capacity_state"] == "below_service_threshold":
        reasons.append("below_service_threshold")
    if report["safety_state"] == "attention":
        reasons.append("bms_alarm")
    if reasons:
        return "service_now", reasons
    if "approaching_threshold" in codes:
        reasons.append("approaching_threshold")
    cycles = report["rul"].get("equivalent_cycles")
    if plan_within_cycles is not None and cycles and cycles[0] <= plan_within_cycles:
        reasons.append("forecast_within_planning_horizon")
    if "cell_imbalance" in codes:
        reasons.append("cell_imbalance")
    return ("plan_service" if reasons else "monitor"), reasons


def triage(
    requests: list[BatteryRequest], plan_within_cycles: float | None = None
) -> dict[str, Any]:
    if not requests:
        raise ValueError("fleet is empty")
    if len(requests) > MAX_BATTERIES:
        raise ValueError(f"fleet exceeds {MAX_BATTERIES} batteries")
    ids = [r.profile.battery_id for r in requests]
    if len(ids) != len(set(ids)):
        raise ValueError("battery ids must be unique")
    rows = []
    for request in requests:
        report = assess_battery(request)
        priority, reasons = priority_of(report, plan_within_cycles)
        soh, threshold = report["soh_pct"], report["service_threshold_pct"]
        rows.append(
            {
                "battery_id": report["battery_id"],
                "application": report["application"],
                "priority": priority,
                "reasons": reasons,
                "soh_pct": soh,
                "service_threshold_pct": threshold,
                "margin_points": None if soh is None else round(soh - threshold, 2),
                "remaining_equivalent_cycles": report["rul"].get("equivalent_cycles"),
                "forecast_status": report["rul"]["status"],
                "usable_records": report["data_quality"]["usable_records"],
                "assessment_id": report["assessment_id"],
            }
        )
    rows.sort(
        key=lambda r: (
            PRIORITY_ORDER.index(r["priority"]),
            r["margin_points"] if r["margin_points"] is not None else 1e9,
            r["battery_id"],
        )
    )
    counts = Counter(r["priority"] for r in rows)
    return {
        "batteries": len(rows),
        "counts": {p: counts.get(p, 0) for p in PRIORITY_ORDER},
        "rows": rows,
        "limits": [
            "capacity_is_not_a_safety_assessment",
            "thresholds_are_operator_choices",
            "ranking_is_decision_support_not_an_instruction",
        ],
    }


def requests_from_csv(text: str, use_case: str = "ev") -> list[BatteryRequest]:
    """Long-format CSV: one row per capacity test; rows are grouped by ``battery_id``."""
    if use_case not in USE_CASES:
        raise ValueError("unknown use case")
    preset = USE_CASES[use_case]
    reader = csv.DictReader(io.StringIO(text))
    if not FLEET_COLUMNS.issubset(reader.fieldnames or []):
        raise ValueError("CSV needs " + ", ".join(sorted(FLEET_COLUMNS)))
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in reader:
        if None in row or any(row.get(c) in (None, "") for c in FLEET_COLUMNS):
            raise ValueError("CSV row has missing or extra fields")
        groups[row["battery_id"]].append(row)
        if len(groups) > MAX_BATTERIES:
            raise ValueError(f"fleet exceeds {MAX_BATTERIES} batteries")
    requests = []
    for battery_id, rows in groups.items():
        rows.sort(key=lambda r: float(r["equivalent_cycles"]))
        conditions = Counter(r.get("condition_id") or "fleet-test" for r in rows)
        condition = conditions.most_common(1)[0][0]
        first = rows[0]
        profile: dict[str, Any] = {
            "battery_id": battery_id,
            "application": first.get("application") or preset["application"],
            "chemistry": first.get("chemistry") or "unknown",
            "measurement_scope": preset["measurement_scope"],
            "reference_capacity_ah": float(first["reference_capacity_ah"]),
            "reference_condition_id": condition,
            "service_threshold_pct": float(
                first.get("service_threshold_pct") or preset["service_threshold_pct"]
            ),
            "service_margin_pct": preset["service_margin_pct"],
        }
        requests.append(
            BatteryRequest.model_validate(
                {
                    "data_origin": "user_supplied",
                    "profile": profile,
                    "records": [
                        {
                            "equivalent_cycles": float(r["equivalent_cycles"]),
                            "capacity_ah": float(r["capacity_ah"]),
                            "condition_id": r.get("condition_id") or "fleet-test",
                            "temperature_c": float(r["temperature_c"])
                            if r.get("temperature_c")
                            else None,
                        }
                        for r in rows
                    ],
                }
            )
        )
    return requests
