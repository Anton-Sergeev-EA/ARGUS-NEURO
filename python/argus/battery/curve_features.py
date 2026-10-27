"""Per-test voltage-curve indicators for NASA PCoE cells.

Each discharge test is paired with the charge that precedes it. Indicators:

* ``ica_peak_v`` / ``ica_peak_height`` / ``ica_peak_width_v``: dQ/dV peak of the charge
* ``rise_time_s``: time for the charge voltage to climb between two fixed levels
* ``dcir_ohm``: screening internal resistance from the discharge current step

They are computed from raw measurements only; no capacity value enters them.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
from scipy.io import loadmat
from scipy.stats import spearmanr

from argus.battery.curves import (
    estimate_dcir,
    incremental_capacity,
    time_between_voltages,
)

RAW_DIR = Path(__file__).resolve().parents[3] / "artifacts/battery-local/nasa-raw"
OUTPUT = (
    Path(__file__).resolve().parents[3] / "artifacts/battery-local/curve-features.json"
)
REFERENCE_AH = 2.0
RISE_WINDOW_V = (3.9, 4.15)
INDICATORS = (
    "ica_peak_v",
    "ica_peak_height",
    "ica_peak_width_v",
    "rise_time_s",
    "dcir_ohm",
)


def charge_features(data: dict[str, Any]) -> dict[str, float | None]:
    time = np.asarray(data["Time"], dtype=float)
    voltage = np.asarray(data["Voltage_measured"], dtype=float)
    current = np.asarray(data["Current_measured"], dtype=float)
    # Constant-current phase only; the first samples are start-up transients.
    mask = (current > 1.0) & (np.arange(len(current)) > 2)
    if mask.sum() < 20:
        return {
            k: None
            for k in (
                "ica_peak_v",
                "ica_peak_height",
                "ica_peak_width_v",
                "rise_time_s",
            )
        }
    t, v, i = time[mask], voltage[mask], current[mask]
    charge_ah = np.concatenate([[0.0], np.cumsum(i[1:] * np.diff(t))]) / 3600.0
    curve = incremental_capacity(v, charge_ah, bins=60, smooth_window=5)
    return {
        "ica_peak_v": curve.peak_voltage_v,
        "ica_peak_height": curve.peak_height_ah_per_v,
        "ica_peak_width_v": curve.peak_width_v,
        "rise_time_s": time_between_voltages(t, v, *RISE_WINDOW_V),
    }


def cell_table(path: Path) -> list[dict[str, Any]]:
    name = path.stem
    cycles = loadmat(path, simplify_cells=True)[name]["cycle"]
    rows: list[dict[str, Any]] = []
    last_charge: dict[str, Any] | None = None
    for cycle in cycles:
        if cycle["type"] == "charge":
            last_charge = charge_features(cycle["data"])
        elif cycle["type"] == "discharge":
            d = cycle["data"]
            dcir = estimate_dcir(d["Current_measured"], d["Voltage_measured"], 1.0)
            rows.append(
                {
                    "test_index": len(rows) + 1,
                    "soh_pct": 100 * float(d["Capacity"]) / REFERENCE_AH,
                    "dcir_ohm": dcir,
                    **(last_charge or {}),
                }
            )
    return rows


def correlations(rows: list[dict[str, Any]]) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    for key in INDICATORS:
        pairs = [(r["soh_pct"], r[key]) for r in rows if r.get(key) is not None]
        if len(pairs) < 10:
            out[key] = None
            continue
        rho = spearmanr(*zip(*pairs)).statistic
        out[key] = None if np.isnan(rho) else round(float(rho), 3)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cells", nargs="+", default=["B0005", "B0006", "B0007", "B0018"]
    )
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    tables = {c: cell_table(RAW_DIR / f"{c}.mat") for c in args.cells}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(tables) + "\n", encoding="utf-8")
    for cell, rows in tables.items():
        print(cell, len(rows), correlations(rows))


if __name__ == "__main__":
    main()
