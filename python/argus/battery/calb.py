"""CALB prismatic NCM cell cycling histories (BatteryLife raw data, CC BY 4.0).

Source: Zenodo record 17960956, ``overall_CALB_cycling_data.xlsx``. The reference
capacity of each cell is the median of its first three discharges because the
nominal rating understates the measured start capacity of several cells. Cells are
laboratory cells, never EV packs.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from argus.battery import sampling
from argus.battery.schema import BatteryRequest

SOURCE = "https://zenodo.org/records/17960956"
LICENSE = "CC-BY-4.0"
DEFAULT_WORKBOOK = (
    Path(__file__).resolve().parents[3]
    / "artifacts/battery-local/calb-raw/overall_CALB_cycling_data.xlsx"
)
ROOT = Path(__file__).resolve().parents[3] / "artifacts/battery-local"
# Legacy cache written with the length-dependent stride; diagnostic use only.
LEGACY_OUTPUT = ROOT / "calb/cells.json"
DEFAULT_OUTPUT = ROOT / f"calb/cells-fixed-stride{sampling.DEFAULT_STRIDE}.json"
CELL_NAME = re.compile(r"^(?:[A-Z]\d{2,3}|T25-\d)$")
TEMPERATURE = re.compile(r"(-?\d+)")


def block_cycle_ids(
    frame: pd.DataFrame, start: int, stop: int, rows: int
) -> tuple[np.ndarray, str]:
    """Cycle numbers of one cell block: the integer counter column, else the row order."""
    for index in range(start + 1, stop):
        label = str(frame.columns[index])
        if "圈" not in label and not label.startswith("Unnamed"):
            continue
        values = pd.to_numeric(frame.iloc[:, index], errors="coerce").to_numpy(
            dtype=float
        )
        valid = values[np.isfinite(values)]
        if (
            len(valid) >= rows // 2
            and np.all(valid == np.round(valid))
            and np.all(np.diff(valid) >= 1)
        ):
            return values, "xlsx_counter_column"
    return np.arange(1, rows + 1, dtype=float), "row_order"


def discharge_series(workbook: Path) -> dict[str, dict[str, Any]]:
    """Per cell: ambient temperature, physical cycle ids, discharge capacity in Ah."""
    sheets = pd.ExcelFile(workbook)
    found: dict[str, dict[str, Any]] = {}
    for sheet in sheets.sheet_names:
        match = TEMPERATURE.search(sheet)
        if match is None:
            continue
        frame = sheets.parse(sheet)
        labels = [str(c) for c in frame.columns]
        starts = [i for i, label in enumerate(labels) if CELL_NAME.match(label)]
        for number, start in enumerate(starts):
            stop = starts[number + 1] if number + 1 < len(starts) else len(labels)
            name = labels[start]
            column = next(
                (i for i in range(start, stop) if "放电容量" in labels[i]), None
            )
            if column is None or name in found:
                continue
            capacity = pd.to_numeric(frame.iloc[:, column], errors="coerce").to_numpy(
                dtype=float
            )
            ids, source = block_cycle_ids(frame, start, stop, len(capacity))
            usable = np.isfinite(capacity) & np.isfinite(ids)
            dropped = int(np.sum(usable & (capacity <= 0)))
            usable &= capacity > 0
            if usable.sum() >= 20:
                found[name] = {
                    "ambient_c": float(match.group(1)),
                    "cycle_ids": ids[usable],
                    "capacity_ah": capacity[usable],
                    "cycle_id_source": source,
                    "nonpositive_dropped": dropped,
                }
    return found


def discharge_capacities(workbook: Path) -> dict[str, tuple[float, np.ndarray]]:
    """Compatibility view: ``{cell: (ambient_c, capacity per usable cycle)}``."""
    return {
        k: (v["ambient_c"], v["capacity_ah"])
        for k, v in discharge_series(workbook).items()
    }


def to_history(
    cell: str,
    ambient_c: float,
    capacity: np.ndarray,
    threshold_pct: float = 80.0,
    prefix: str = "CALB",
    chemistry: str = "nmc",
    cycle_ids: np.ndarray | None = None,
    stride: int | str = sampling.DEFAULT_STRIDE,
) -> BatteryRequest:
    """History at a fixed physical stride; ``stride="adaptive"`` is the legacy diagnostic."""
    capacity = np.asarray(capacity, dtype=float)
    ids = (
        np.arange(1, len(capacity) + 1, dtype=float)
        if cycle_ids is None
        else np.asarray(cycle_ids, dtype=float)
    )
    keep = capacity > 0
    capacity, ids = capacity[keep], ids[keep]
    reference = float(np.median(capacity[:3]))
    cycles, values, _ = sampling.thin(ids, capacity, stride)
    condition = f"{prefix.lower()}-full-depth-{ambient_c:g}c"
    return BatteryRequest.model_validate(
        {
            "data_origin": "laboratory",
            "profile": {
                "battery_id": f"{prefix}-{cell}",
                "application": "ev",
                "chemistry": chemistry,
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
    workbook: Path = DEFAULT_WORKBOOK,
    output: Path = DEFAULT_OUTPUT,
    stride: int | str = sampling.DEFAULT_STRIDE,
) -> int:
    series = discharge_series(workbook)
    histories = [
        to_history(
            name,
            v["ambient_c"],
            v["capacity_ah"],
            cycle_ids=v["cycle_ids"],
            stride=stride,
        ).model_dump(mode="json")
        for name, v in sorted(series.items())
    ]
    _, _, info = sampling.thin(np.arange(1.0, 3.0), np.zeros(2), stride)
    meta = {
        **info,
        "source": SOURCE,
        "cycle_id_source": {k: v["cycle_id_source"] for k, v in sorted(series.items())},
        "nonpositive_dropped": {
            k: v["nonpositive_dropped"]
            for k, v in sorted(series.items())
            if v["nonpositive_dropped"]
        },
        "reference": "median of the first three positive discharges",
    }
    sampling.write_cache(output, meta, histories)
    return len(histories)


def load_cache_with_meta(
    path: Path = DEFAULT_OUTPUT,
) -> tuple[dict[str, Any], list[BatteryRequest]]:
    if not path.exists():
        return {}, []
    meta, cells = sampling.read_cache(path)
    return meta, [BatteryRequest.model_validate(item) for item in cells]


def load_cache(path: Path = DEFAULT_OUTPUT) -> list[BatteryRequest]:
    return load_cache_with_meta(path)[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook", type=Path, default=DEFAULT_WORKBOOK)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument(
        "--stride",
        default=str(sampling.DEFAULT_STRIDE),
        help='fixed physical stride in cycles, or "adaptive" for the legacy diagnostic mode',
    )
    args = parser.parse_args()
    stride: int | str = "adaptive" if args.stride == "adaptive" else int(args.stride)
    output = args.output or (
        LEGACY_OUTPUT
        if stride == "adaptive"
        else ROOT / f"calb/cells-fixed-stride{stride}.json"
    )
    print(f"{build_cache(args.workbook, output, stride)} cells written to {output}")


if __name__ == "__main__":
    main()
