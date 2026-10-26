"""Rolling-origin backtest of remaining-life intervals on measured laboratory cells.

Every forecast sees only the observed prefix. The truth is the first observation at
or below the service threshold; cells that never get there are censored and are
excluded from the error metrics rather than treated as failures. Interval
calibration is evaluated leave-one-cell-out, so a cell never calibrates itself.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np

from argus.battery.assessment import assess_battery
from argus.battery.calb import load_cache
from argus.battery.config import DEFAULT_CONFIG, ProjectionConfig
from argus.battery.public_data import CELLS, DATA_DIR, load_public_history
from argus.battery.schema import BatteryRequest

NASA_THRESHOLDS = (80.0, 70.0)
CALB_THRESHOLDS = (90.0, 85.0, 80.0)
MIN_FIRST_PREFIX = 24
PREFIXES_PER_CELL = 12
COVERAGE = 0.9


def histories() -> list[tuple[str, BatteryRequest, tuple[float, ...]]]:
    found: list[tuple[str, BatteryRequest, tuple[float, ...]]] = []
    for cell in sorted(CELLS):
        if (DATA_DIR / f"{cell}.json").exists():
            request, _ = load_public_history(f"nasa-{cell}", 2000)
            found.append((cell, request, NASA_THRESHOLDS))
    found += [(h.profile.battery_id, h, CALB_THRESHOLDS) for h in load_cache()]
    return found


def event_index(request: BatteryRequest, threshold: float) -> int | None:
    p = request.profile
    for index, row in enumerate(request.records):
        if row.capacity_ah / p.reference_capacity_ah * 100 <= threshold:
            return index
    return None


def cell_cases(
    cell: str, request: BatteryRequest, threshold: float, config: ProjectionConfig
) -> list[dict[str, Any]]:
    event = event_index(request, threshold)
    if event is None or event < MIN_FIRST_PREFIX:
        return []
    profile = request.profile.model_copy(update={"service_threshold_pct": threshold})
    request = request.model_copy(update={"profile": profile})
    step = max(1, (event - MIN_FIRST_PREFIX) // PREFIXES_PER_CELL)
    cases = []
    for n in range(MIN_FIRST_PREFIX, event, step):
        rows = request.records
        prefix = request.model_copy(update={"records": rows[:n]})
        report = assess_battery(prefix, config)
        rul = report["rul"]
        truth = rows[event].equivalent_cycles - rows[n - 1].equivalent_cycles
        spacing = float(np.median(np.diff([r.equivalent_cycles for r in rows[:n]])))
        row: dict[str, Any] = {
            "cell": cell,
            "threshold": threshold,
            "observed": n,
            "truth": truth,
            "unit": 5 * spacing,
            "status": rul["status"],
            "model": report["trend"].get("model"),
        }
        if rul["status"] == "conditional_estimate":
            low, high = rul["equivalent_cycles"]
            row |= {"low": low, "high": high, "mid": (low + high) / 2}
        cases.append(row)
    return cases


def relative_score(case: dict[str, Any]) -> float:
    return abs(case["mid"] - case["truth"]) / max(case["mid"], case["unit"])


def conformal_radius(scores: list[float], coverage: float = COVERAGE) -> float | None:
    """Finite-sample split-conformal quantile of relative midpoint errors."""
    n = len(scores)
    rank = math.ceil((n + 1) * coverage)
    return float(sorted(scores)[rank - 1]) if n and rank <= n else None


def widen(case: dict[str, Any], radius: float) -> tuple[float, float]:
    half = radius * max(case["mid"], case["unit"])
    return max(0.0, case["mid"] - half), case["mid"] + half


def summarize(
    cases: list[dict[str, Any]], leave_one_out: bool = True
) -> dict[str, Any]:
    made = [c for c in cases if "mid" in c]
    cells = sorted({c["cell"] for c in made})
    summary: dict[str, Any] = {
        "forecast_points": len(cases),
        "numeric_forecasts": len(made),
        "cells_with_forecast": len(cells),
        "abstention_rate": round(1 - len(made) / len(cases), 3) if cases else None,
        "raw_interval_coverage": round(
            float(np.mean([c["low"] <= c["truth"] <= c["high"] for c in made])), 3
        )
        if made
        else None,
        "midpoint_mae_cycles": round(
            float(np.mean([abs(c["mid"] - c["truth"]) for c in made])), 2
        )
        if made
        else None,
        "median_relative_midpoint_error": round(
            float(np.median([relative_score(c) for c in made])), 3
        )
        if made
        else None,
        "models_used": {
            m: sum(1 for c in cases if c["model"] == m)
            for m in sorted({c["model"] for c in cases if c["model"]})
        },
    }
    if leave_one_out and len(cells) >= 5:
        covered, widths = [], []
        for cell in cells:
            radius = conformal_radius(
                [relative_score(c) for c in made if c["cell"] != cell]
            )
            for case in (c for c in made if c["cell"] == cell):
                if radius is None:
                    continue
                low, high = widen(case, radius)
                covered.append(low <= case["truth"] <= high)
                widths.append((high - low) / max(case["truth"], case["unit"]))
        summary["calibrated_coverage_leave_one_cell_out"] = (
            round(float(np.mean(covered)), 3) if covered else None
        )
        summary["calibrated_median_relative_width"] = (
            round(float(np.median(widths)), 3) if widths else None
        )
    summary["full_sample_conformal_radius"] = conformal_radius(
        [relative_score(c) for c in made]
    )
    return summary


def run() -> dict[str, Any]:
    # Calibration stays off: the backtest measures the raw intervals it calibrates.
    raw = replace(DEFAULT_CONFIG, calibrate_cells=False)
    variants = {
        "linear_only": replace(raw, model="linear"),
        "validated_selection": replace(raw, model="auto"),
    }
    data = histories()
    out: dict[str, Any] = {
        "cells": [name for name, _, _ in data],
        "coverage_target": COVERAGE,
        "variants": {},
        "detail": {},
    }
    for name, config in variants.items():
        cases = [
            case
            for cell, request, thresholds in data
            for threshold in thresholds
            for case in cell_cases(cell, request, threshold, config)
        ]
        out["variants"][name] = summarize(cases)
        out["detail"][name] = cases
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=Path("docs/assets/backtest.json")
    )
    args = parser.parse_args()
    result = run()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(result["variants"], indent=1))


if __name__ == "__main__":
    main()
