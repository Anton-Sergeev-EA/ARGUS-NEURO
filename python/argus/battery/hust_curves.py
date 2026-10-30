"""Charge-curve indicators for HUST cells, aligned with the thinned capacity histories.

HUST cells charge at about 5C from 2.7 V to 3.6 V (constant current) and the cell
voltage of LFP is flat over most of that range, so the indicators use the window
where it moves: the time to climb from ``RISE_WINDOW_V[0]`` to ``RISE_WINDOW_V[1]``
and the dQ/dV peak of the constant-current charge.
"""

from __future__ import annotations

import argparse
import io
import json
import zipfile
from pathlib import Path
from typing import Any

import numpy as np

from argus.battery.curves import incremental_capacity, time_between_voltages
from argus.battery.hust import ARCHIVE, ROOT, DataOnlyUnpickler

OUTPUT = ROOT / "hust/indicators.json"
RISE_WINDOW_V = (3.0, 3.45)
CC_STATUS = "Constant current charge"
MAX_POINTS = 600  # must equal argus.battery.calb.MAX_POINTS so cycles line up
INDICATORS = ("rise_time_s", "ica_peak_v", "ica_peak_height", "ica_peak_width_v")


def cycle_indicators(frame: Any) -> dict[str, float] | None:
    """Indicators of one cycle's constant-current charge, or ``None`` if unusable."""
    charge = frame[frame["Status"] == CC_STATUS]
    if len(charge) < 20:
        return None
    voltage = charge["Voltage (V)"].to_numpy(dtype=float)
    time = charge["Time (s)"].to_numpy(dtype=float)
    capacity = charge["Capacity (mAh)"].to_numpy(dtype=float) / 1000.0
    if np.any(np.diff(time) <= 0):
        return None
    rise = time_between_voltages(time, voltage, *RISE_WINDOW_V)
    try:
        ica = incremental_capacity(voltage, capacity, bins=40, smooth_window=5)
    except ValueError:
        return None
    if rise is None:
        return None
    return {
        "rise_time_s": rise,
        "ica_peak_v": ica.peak_voltage_v,
        "ica_peak_height": ica.peak_height_ah_per_v,
        "ica_peak_width_v": ica.peak_width_v,
    }


def cell_indicators(raw: bytes) -> tuple[str, dict[int, dict[str, float]]]:
    document = DataOnlyUnpickler(io.BytesIO(raw)).load()
    ((name, cell),) = document.items()
    cycles = sorted(cell["dq"])
    stride = max(1, int(np.ceil(len(cycles) / MAX_POINTS)))
    found: dict[int, dict[str, float]] = {}
    for cycle in cycles[::stride]:
        values = cycle_indicators(cell["data"][cycle])
        if values is not None:
            found[int(cycle)] = values
    return str(name), found


def build(archive: Path = ARCHIVE, output: Path = OUTPUT) -> int:
    series: dict[str, dict[int, dict[str, float]]] = {}
    with zipfile.ZipFile(archive) as bundle:
        for member in sorted(n for n in bundle.namelist() if n.endswith(".pkl")):
            name, found = cell_indicators(bundle.read(member))
            series[f"HUST-{name}"] = found
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(series) + "\n", encoding="utf-8")
    return len(series)


def load(path: Path = OUTPUT) -> dict[str, dict[int, dict[str, float]]]:
    if not path.exists():
        return {}
    raw = json.loads(path.read_text())
    return {cell: {int(k): v for k, v in rows.items()} for cell, rows in raw.items()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=ARCHIVE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    print(f"{build(args.archive, args.output)} cells written to {args.output}")


if __name__ == "__main__":
    main()
