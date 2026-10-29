"""Explainable capacity trends; never claim calibrated ML or safety from SOH."""

from __future__ import annotations
import hashlib
import json
from typing import Any
import numpy as np
from argus.battery.config import DEFAULT_CONFIG, ProjectionConfig
from argus.battery.schema import BatteryRequest

AGING_SOURCE = "https://afdc.energy.gov/fuels/electricity-benefits"


def recommendations(request: BatteryRequest) -> list[dict[str, Any]]:
    bms, limits = request.bms, request.profile.limits
    advice: list[dict[str, Any]] = []

    def add(code: str, priority: str, evidence: dict[str, Any], source: str) -> None:
        advice.append(
            {"code": code, "priority": priority, "evidence": evidence, "source": source}
        )

    if bms.safety_alarm:
        add(
            "bms_alarm",
            "urgent",
            {"reported_by_bms": True},
            "vehicle_or_battery_manual",
        )
    if bms.charging and bms.temperature_c is not None and limits is not None:
        if limits.charge_max_c is not None and bms.temperature_c > limits.charge_max_c:
            add(
                "charge_too_hot",
                "urgent",
                {"observed_c": bms.temperature_c, "limit_c": limits.charge_max_c},
                limits.source,
            )
        if limits.charge_min_c is not None and bms.temperature_c < limits.charge_min_c:
            add(
                "charge_too_cold",
                "urgent",
                {"observed_c": bms.temperature_c, "limit_c": limits.charge_min_c},
                limits.source,
            )
    if (
        bms.cell_spread_mv is not None
        and limits is not None
        and limits.cell_spread_limit_mv is not None
        and bms.cell_spread_mv > limits.cell_spread_limit_mv
    ):
        add(
            "cell_imbalance",
            "check",
            {
                "observed_mv": bms.cell_spread_mv,
                "limit_mv": limits.cell_spread_limit_mv,
            },
            limits.source,
        )
    if bms.high_soc_hot_storage_reported:
        add(
            "hot_storage",
            "care",
            {"user_reported": True, "chemistry": request.profile.chemistry},
            AGING_SOURCE,
        )
    if bms.frequent_fast_charging_reported:
        add(
            "charging_plan",
            "care",
            {"user_reported": True, "chemistry": request.profile.chemistry},
            "vehicle_or_battery_manual",
        )
    if limits is None:
        add(
            "manufacturer_profile",
            "information",
            {"limits_available": False},
            "vehicle_or_battery_manual",
        )
    return advice


def assess_battery(
    request: BatteryRequest, config: ProjectionConfig = DEFAULT_CONFIG
) -> dict[str, Any]:
    p = request.profile
    records = [r for r in request.records if r.condition_id == p.reference_condition_id]
    excluded = len(request.records) - len(records)
    x = np.array([r.equivalent_cycles for r in records], dtype=float)
    y = np.array(
        [100 * r.capacity_ah / p.reference_capacity_ah for r in records], dtype=float
    )
    warnings = []
    if excluded:
        warnings.append("incomparable_measurements_excluded")
    if len(y) and float(y.max()) > config.reference_error_soh_pct:
        warnings.append("check_reference_capacity")
    advice = recommendations(request)
    result: dict[str, Any] = {
        "schema_version": 1,
        "battery_id": p.battery_id,
        "application": p.application,
        "cycle_axis": p.cycle_axis,
        "measurement_scope": p.measurement_scope,
        "source": request.data_origin,
        "soc_pct": request.bms.soc_pct,
        "bms_observed_at": request.bms.observed_at,
        "soh_pct": round(float(y[-1]), 2) if len(y) else None,
        "service_threshold_pct": p.service_threshold_pct,
        "capacity_state": "no_data",
        "safety_state": "attention"
        if any(a["priority"] == "urgent" for a in advice)
        else "not_assessed",
        "trend": {"status": "insufficient_history"},
        "rul": {
            "status": "insufficient_history",
            "equivalent_cycles": None,
            "months": None,
        },
        "history": [
            {"equivalent_cycles": r.equivalent_cycles, "soh_pct": round(float(v), 3)}
            for r, v in zip(records, y)
        ],
        "data_quality": {
            "usable_records": len(records),
            "excluded_records": excluded,
            "warnings": warnings,
        },
        "recommendations": advice,
        "limits": [
            "capacity_is_not_a_safety_assessment",
            "forecast_depends_on_future_usage",
            "no_vehicle_range_prediction",
        ],
        "assessment_id": hashlib.sha256(request.model_dump_json().encode()).hexdigest()[
            :20
        ],
    }
    if not len(y):
        return result
    result["capacity_state"] = (
        "below_service_threshold"
        if y[-1] <= p.service_threshold_pct
        else "above_service_threshold"
    )
    if y[-1] <= p.service_threshold_pct:
        result["rul"] = {
            "status": "threshold_reached",
            "equivalent_cycles": [0.0, 0.0],
            "months": None,
        }
        advice.append(
            {
                "code": "capacity_service",
                "priority": "check",
                "evidence": {
                    "soh_pct": result["soh_pct"],
                    "threshold_pct": p.service_threshold_pct,
                },
                "source": "configured_service_threshold",
            }
        )
        return result
    if result["safety_state"] == "attention":
        result["rul"]["status"] = "operating_alert"
        return result
    if len(y) < config.min_records or x[-1] - x[0] < config.min_span_cycles or warnings:
        return result
    tx, ty = x[-config.window :], y[-config.window :]
    centered = tx - tx[-1]
    slope, intercept = np.polyfit(centered, ty, 1)
    residual = ty - (intercept + slope * centered)
    rng = np.random.default_rng(config.seed)
    block = max(2, int(np.sqrt(len(ty))))
    fits = []
    for _ in range(config.bootstrap_replicates):
        starts = rng.integers(
            0, len(ty) - block + 1, size=int(np.ceil(len(ty) / block))
        )
        noise = np.concatenate([residual[s : s + block] for s in starts])[: len(ty)]
        fits.append(np.polyfit(centered, intercept + slope * centered + noise, 1))
    high_slope = np.quantile([f[0] for f in fits], config.interval_high)
    acceleration = None
    if len(ty) >= config.acceleration_min_records:
        half = len(ty) // 2
        early = np.polyfit(tx[:half], ty[:half], 1)[0]
        recent = np.polyfit(tx[half:], ty[half:], 1)[0]
        if early < config.decline_slope and recent < early * config.acceleration_ratio:
            acceleration = "possible_acceleration"
    result["trend"] = {
        "status": "declining" if high_slope < config.decline_slope else "unclear",
        "loss_pct_points_per_100_cycles": round(float(-slope * 100), 3),
        "change_pct_points": round(float(ty[-1] - ty[0]), 3),
        "from_equivalent_cycles": float(tx[0]),
        "to_equivalent_cycles": float(tx[-1]),
        "acceleration": acceleration,
        "method": "recent_linear_trend_with_moving_block_residual_bootstrap",
    }
    if high_slope >= config.decline_slope or acceleration:
        result["rul"]["status"] = (
            "changing_trend" if acceleration else "no_reliable_decline"
        )
        return result
    predictions = [
        (p.service_threshold_pct - f[1]) / f[0]
        for f in fits
        if f[0] < config.decline_slope
    ]
    lo, hi = np.quantile(predictions, [config.interval_low, config.interval_high])
    if lo < 0 or hi > config.horizon_spans * (tx[-1] - tx[0]):
        result["rul"]["status"] = "beyond_observed_horizon"
        return result
    cycles = [round(float(lo), 1), round(float(hi), 1)]
    result["rul"] = {
        "status": "conditional_estimate",
        "equivalent_cycles": cycles,
        "months": [round(v / p.equivalent_cycles_per_month, 1) for v in cycles]
        if p.equivalent_cycles_per_month
        else None,
        "method": "capacity_trend_projection",
        "interval_kind": "descriptive_5_to_95_percentile_not_guaranteed_coverage",
        "assumptions": [
            "same_future_usage",
            "comparable_capacity_tests",
            "no_new_failure_mode",
        ],
    }
    json.dumps(result, allow_nan=False)
    return result
