from __future__ import annotations

import pytest

from argus.battery.backtest_paired import paired


def row(cell: str, observed: int, mid: float | None, truth: float = 100.0) -> dict:
    out = {"cell": cell, "threshold": 90.0, "observed": observed, "truth": truth}
    if mid is not None:
        out["mid"] = mid
    return out


def test_pairs_only_forecasts_that_both_variants_made() -> None:
    detail = {
        "linear_only": [
            row("HUST-1-1", 1, 150.0),
            row("HUST-1-1", 2, 150.0),
            row("B0005", 1, 90.0),
            row("B0005", 2, None),
        ],
        "validated_selection": [
            row("HUST-1-1", 1, 110.0),
            row("HUST-1-1", 2, None),
            row("B0005", 1, 90.0),
            row("B0005", 2, 95.0),
        ],
    }
    out = paired(detail)
    assert out["shared_forecast_points"] == 2 and out["cells"] == 2
    assert out["linear_mae"] == 30.0 and out["curved_mae"] == 10.0
    assert out["by_source"]["HUST"] == {
        "cells": 1,
        "gain_cycles": 40.0,
        "cells_better": 1,
    }
    assert out["by_source"]["NASA"]["gain_cycles"] == 0.0
    assert out["gain_ci95"][0] <= out["gain_cycles"] <= out["gain_ci95"][1]


def test_rejects_data_without_shared_forecasts() -> None:
    detail = {
        "linear_only": [row("A-1", 1, 5.0)],
        "validated_selection": [row("A-1", 1, None)],
    }
    with pytest.raises(ValueError):
        paired(detail)
