"""CALB prismatic NCM cell cycling histories (BatteryLife raw data, CC BY 4.0).

Source: Zenodo record 17960956, ``overall_CALB_cycling_data.xlsx``. The reference
capacity of each cell is the median of its first three discharges because the
nominal rating understates the measured start capacity of several cells. Cells are
laboratory cells, never EV packs.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from argus.battery.schema import BatteryRequest

SOURCE = "https://zenodo.org/records/17960956"
LICENSE = "CC-BY-4.0"
DEFAULT_WORKBOOK = (
    Path(__file__).resolve().parents[3]
    / "artifacts/battery-local/calb-raw/overall_CALB_cycling_data.xlsx"
)
DEFAULT_OUTPUT = (
    Path(__file__).resolve().parents[3] / "artifacts/battery-local/calb/cells.json"
)
CELL_NAME = re.compile(r"^(?:[A-Z]\d{2,3}|T25-\d)$")
TEMPERATURE = re.compile(r"(-?\d+)")
MAX_POINTS = 600


def discharge_capacities(workbook: Path) -> dict[str, tuple[float, np.ndarray]]:
    """Return ``{cell: (ambient_c, discharge capacity in Ah per cycle)}``."""
    sheets = pd.ExcelFile(workbook)
    found: dict[str, tuple[float, np.ndarray]] = {}
    for sheet in sheets.sheet_names:
        match = TEMPERATURE.search(sheet)
        if match is None:
            continue
        frame = sheets.parse(sheet)
        current = None
        for index, column in enumerate(frame.columns):
            label = str(column)
            if CELL_NAME.match(label):
                current = label
            if "放电容量" in label and current:
                values = pd.to_numeric(frame.iloc[:, index], errors="coerce")
                values = values.dropna().to_numpy(dtype=float)
                if len(values) >= 20 and current not in found:
                    found[current] = (float(match.group(1)), values)
    return found


def to_history(
    cell: str, ambient_c: float, capacity: np.ndarray, threshold_pct: float = 80.0
) -> BatteryRequest:
    capacity = capacity[capacity > 0]
    reference = float(np.median(capacity[:3]))
    stride = max(1, int(np.ceil(len(capacity) / MAX_POINTS)))
    cycles = np.arange(1, len(capacity) + 1)[::stride]
    values = capacity[::stride]
    condition = f"calb-1c-full-depth-{ambient_c:g}c"
    return BatteryRequest.model_validate(
        {
            "data_origin": "laboratory",
            "profile": {
                "battery_id": f"CALB-{cell}",
                "application": "ev",
                "chemistry": "nmc",
                "measurement_scope": "cell",
                "cycle_axis": "equivalent_cycles",
                "reference_capacity_ah": reference,
                "reference_condition_id": condition,
                "service_threshold_pct": threshold_pct,
            },
            "records": [
                {
                    "equivalent_cycles": float(c),
                    "capacity_ah": float(v),
                    "condition_id": condition,
                    "temperature_c": ambient_c,
                }
                for c, v in zip(cycles, values)
            ],
        }
    )


def build_cache(
    workbook: Path = DEFAULT_WORKBOOK, output: Path = DEFAULT_OUTPUT
) -> int:
    cells = discharge_capacities(workbook)
    histories: list[dict[str, Any]] = [
        to_history(name, ambient, values).model_dump(mode="json")
        for name, (ambient, values) in sorted(cells.items())
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(histories) + "\n", encoding="utf-8")
    return len(histories)


def load_cache(path: Path = DEFAULT_OUTPUT) -> list[BatteryRequest]:
    if not path.exists():
        return []
    return [
        BatteryRequest.model_validate(item) for item in json.loads(path.read_text())
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook", type=Path, default=DEFAULT_WORKBOOK)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(f"{build_cache(args.workbook, args.output)} cells written to {args.output}")


if __name__ == "__main__":
    main()
