"""Research tooling: conformal calibration, CALB parsing and the training benchmark."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from argus.battery import backtest, calb
from argus.battery.schema import BatteryRequest
from argus.battery.training import run_benchmark


def test_conformal_radius_uses_the_finite_sample_rank() -> None:
    scores = [
        0.1 * k for k in range(1, 20)
    ]  # 19 scores, 90% rank = ceil(20 * 0.9) = 18
    assert backtest.conformal_radius(scores) == pytest.approx(1.8)
    assert backtest.conformal_radius(scores[:5]) is None  # too few for 90% coverage
    assert backtest.conformal_radius([]) is None


def test_widening_never_goes_below_zero_and_grows_with_the_radius() -> None:
    case = {"mid": 10.0, "unit": 5.0}
    assert backtest.widen(case, 0.5) == (5.0, 15.0)
    assert backtest.widen(case, 2.0)[0] == 0.0
    # Near the threshold the midpoint shrinks; the unit keeps the band from collapsing.
    assert backtest.widen({"mid": 0.0, "unit": 5.0}, 0.5) == (0.0, 2.5)


def synthetic_cases(cells: int = 6) -> list[dict]:
    rows = []
    for c in range(cells):
        for k in range(8):
            truth = 100.0 - 10 * k
            mid = truth * (1 + 0.1 * ((c + k) % 3 - 1))
            rows.append(
                {
                    "cell": f"c{c}", "threshold": 80.0, "observed": 24 + k, "truth": truth,
                    "unit": 5.0, "status": "conditional_estimate", "model": "linear",
                    "low": mid * 0.95, "high": mid * 1.05, "mid": mid,
                }
            )  # fmt: skip
    rows.append({"cell": "c0", "threshold": 80.0, "observed": 40, "truth": 5.0, "unit": 5.0,
                 "status": "insufficient_history", "model": None})  # fmt: skip
    return rows


def test_summary_reports_abstention_and_leave_one_cell_out_coverage() -> None:
    summary = backtest.summarize(synthetic_cases())
    assert summary["forecast_points"] == 49 and summary["numeric_forecasts"] == 48
    assert summary["abstention_rate"] == pytest.approx(1 / 49, abs=1e-3)
    assert (
        summary["raw_interval_coverage"]
        < summary["calibrated_coverage_leave_one_cell_out"]
    )
    assert summary["calibrated_coverage_leave_one_cell_out"] >= 0.85
    assert summary["models_used"] == {"linear": 48}


def test_calb_workbook_blocks_are_split_by_cell(tmp_path: Path) -> None:
    def sheet(names: list[str], length: int) -> pd.DataFrame:
        columns: dict[str, list[float]] = {}
        for i, name in enumerate(names):
            columns[name] = [float(k) for k in range(length)]
            columns[f"放电容量(Ah){'.' + str(i) if i else ''}"] = [
                60.0 - 0.01 * k - 0.1 * i for k in range(length)
            ]
        return pd.DataFrame(columns)

    path = tmp_path / "calb.xlsx"
    with pd.ExcelWriter(path) as writer:
        sheet(["B173", "B174"], 40).to_excel(writer, sheet_name="35℃ 循环", index=False)
        sheet(["T25-1"], 30).to_excel(writer, sheet_name="25℃ 循环", index=False)
        sheet(["B999"], 5).to_excel(
            writer, sheet_name="45℃循环", index=False
        )  # too short
    cells = calb.discharge_capacities(path)
    assert set(cells) == {"B173", "B174", "T25-1"}
    assert cells["B173"][0] == 35 and cells["T25-1"][0] == 25
    history = calb.to_history("B173", *cells["B173"])
    assert (
        history.profile.measurement_scope == "cell"
        and history.data_origin == "laboratory"
    )
    assert history.profile.reference_capacity_ah == pytest.approx(
        np.median(cells["B173"][1][:3])
    )
    output = tmp_path / "cells.json"
    assert calb.build_cache(path, output) == 3
    assert len(calb.load_cache(output)) == 3
    assert calb.load_cache(tmp_path / "missing.json") == []


def synthetic_history(i: int, length: int = 90) -> dict:
    rng = np.random.default_rng(i)
    rate = 0.30 + 0.03 * (i % 5)
    soh = 100 - rate * np.arange(length) + rng.normal(0, 0.15, length)
    return BatteryRequest.model_validate(
        {
            "data_origin": "laboratory",
            "profile": {
                "battery_id": f"SYN-{i}", "application": "ev", "chemistry": "nmc",
                "measurement_scope": "cell", "cycle_axis": "equivalent_cycles",
                "reference_capacity_ah": 50, "reference_condition_id": "c",
                "service_threshold_pct": 85,
            },
            "records": [
                {"equivalent_cycles": float(k + 1), "capacity_ah": float(s / 2), "condition_id": "c"}
                for k, s in enumerate(soh)
            ],
        }
    ).model_dump(mode="json")  # fmt: skip


def test_benchmark_smoke_run_is_split_by_cell_and_reproducible(tmp_path: Path) -> None:
    dataset = tmp_path / "cells.json"
    dataset.write_text(json.dumps([synthetic_history(i) for i in range(12)]))
    report = run_benchmark(dataset, tmp_path / "out", seeds=[1], epochs=2)
    groups = report["split"]
    members = [b for group in groups.values() for b in group]
    assert len(members) == len(set(members)) == 12  # no cell on both sides of a split
    test = report["runs"][0]["test"]
    assert {
        "median",
        "ridge",
        "gradient_boosting",
        "gru",
        "tcn",
        "linear_window",
    } <= set(test)
    # A clean straight fade is exactly what the straight-line baseline should solve.
    assert (
        test["linear_window"]["macro_mae_cycles"] < test["median"]["macro_mae_cycles"]
    )
    again = run_benchmark(dataset, tmp_path / "out2", seeds=[1], epochs=2)
    assert again["runs"][0]["test"]["ridge"] == report["runs"][0]["test"]["ridge"]
    with pytest.raises(ValueError):
        run_benchmark(dataset, tmp_path / "out3", seeds=[], epochs=2)
