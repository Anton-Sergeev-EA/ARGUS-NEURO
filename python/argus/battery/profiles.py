"""Starting points for the supported battery use cases.

These are editable examples, not standards: a service threshold is a decision of the
operator, and none of the numbers below has been validated for the use case. They
only pre-fill a form so that a scooter, a rental power bank and a rescue drone do not
all start from an electric-car default.
"""

from __future__ import annotations

from typing import Any

USE_CASES: dict[str, dict[str, Any]] = {
    "ev": {
        "application": "ev",
        "service_threshold_pct": 80,
        "service_margin_pct": 5,
        "measurement_scope": "pack",
        "cycles_per_month_hint": 20,
        "advice_focus": ["charging_plan", "hot_storage", "cell_imbalance"],
    },
    "scooter": {
        "application": "scooter",
        "service_threshold_pct": 70,
        "service_margin_pct": 8,
        "measurement_scope": "pack",
        "cycles_per_month_hint": 30,
        "advice_focus": ["capacity_service", "approaching_threshold", "cell_imbalance"],
    },
    "power_bank": {
        "application": "power_bank",
        "service_threshold_pct": 80,
        "service_margin_pct": 5,
        "measurement_scope": "pack",
        "cycles_per_month_hint": 40,
        "advice_focus": ["capacity_service", "approaching_threshold", "hot_storage"],
    },
    "rescue_uav": {
        "application": "rescue_uav",
        "service_threshold_pct": 85,
        "service_margin_pct": 8,
        "measurement_scope": "pack",
        "cycles_per_month_hint": 12,
        "advice_focus": ["mission_assignment", "bms_alarm", "cell_imbalance"],
    },
    "uav": {
        "application": "uav",
        "service_threshold_pct": 80,
        "service_margin_pct": 5,
        "measurement_scope": "pack",
        "cycles_per_month_hint": 16,
        "advice_focus": ["approaching_threshold", "cell_imbalance"],
    },
}

VALIDATION_STATUS = (
    "The capacity and trend arithmetic is tested on laboratory cells (NASA, CALB, HUST). "
    "No data from vehicles, scooters, rental power banks or rescue drones were used; "
    "thresholds and margins are operator choices."
)


def catalogue() -> dict[str, Any]:
    return {"use_cases": USE_CASES, "validation": VALIDATION_STATUS}
