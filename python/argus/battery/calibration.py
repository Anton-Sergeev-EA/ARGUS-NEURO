"""Empirical widening of cell-level remaining-life intervals.

The bootstrap interval only reflects scatter around the fitted line, so it covered
the true remaining life far less often than its nominal 90% in the multi-cell
backtest. The relative radius stored in ``calibration.json`` comes from that
backtest (split-conformal quantile of the relative midpoint error). It is applied
only to laboratory-cell reports; pack reports keep the uncalibrated interval and say
so.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

PATH = Path(__file__).with_name("calibration.json")


@lru_cache(maxsize=1)
def load() -> dict[str, Any]:
    return json.loads(PATH.read_text(encoding="utf-8"))


def calibrate_interval(
    interval: list[float], cycles: np.ndarray
) -> tuple[list[float], dict[str, Any]]:
    """Return the widened interval and the calibration evidence behind it."""
    meta = load()
    low, high = interval
    mid = (low + high) / 2
    spacing = float(np.median(np.diff(cycles))) if len(cycles) > 1 else 1.0
    half = meta["relative_radius"] * max(mid, meta["unit_spacings"] * spacing)
    widened = [round(max(0.0, mid - half), 1), round(mid + half, 1)]
    return widened, {
        "method": meta["method"],
        "nominal_coverage": meta["nominal_coverage"],
        "leave_one_cell_out_coverage": meta["leave_one_cell_out_coverage"],
        "cells": meta["cells"],
        "uncalibrated_interval": interval,
    }
