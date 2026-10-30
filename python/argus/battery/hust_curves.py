"""Charge-curve indicators for HUST cells, aligned with the thinned capacity histories.

HUST cells charge at about 5C from 2.7 V to 3.6 V (constant current) and the cell
voltage of LFP is flat over most of that range, so the indicators use the window
where it moves: the time to climb from ``RISE_WINDOW_V[0]`` to ``RISE_WINDOW_V[1]``
and the dQ/dV peak of the constant-current charge.
"""

from __future__ import annotations

import argparse
import io
import zipfile
from pathlib import Path
from typing import Any

import numpy as np

from argus.battery import sampling
from argus.battery.curves import incremental_capacity, time_between_voltages
from argus.battery.hust import ARCHIVE, ROOT, DataOnlyUnpickler

# Legacy cache written with the length-dependent stride; diagnostic use only.
LEGACY_OUTPUT = ROOT / "hust/indicators.json"
OUTPUT = ROOT / f"hust/indicators-fixed-stride{sampling.DEFAULT_STRIDE}.json"
RISE_WINDOW_V = (3.0, 3.45)
CC_STATUS = "Constant current charge"
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


def cell_indicators(
    raw: bytes, stride: int | str = sampling.DEFAULT_STRIDE
) -> tuple[str, dict[int, dict[str, float]]]:
    """Indicators at the same physical cycles the capacity history keeps."""
    document = DataOnlyUnpickler(io.BytesIO(raw)).load()
    ((name, cell),) = document.items()
    cycles = np.array(sorted(cell["dq"]), dtype=float)
    kept, _, _ = sampling.thin(cycles, cycles, stride)
    found: dict[int, dict[str, float]] = {}
    for cycle in kept:
        values = cycle_indicators(cell["data"][int(cycle)])
        if values is not None:
            found[int(cycle)] = values
    return str(name), found


def build(
    archive: Path = ARCHIVE,
    output: Path = OUTPUT,
    stride: int | str = sampling.DEFAULT_STRIDE,
) -> int:
    series: dict[str, dict[int, dict[str, float]]] = {}
    with zipfile.ZipFile(archive) as bundle:
        for member in sorted(n for n in bundle.namelist() if n.endswith(".pkl")):
            name, found = cell_indicators(bundle.read(member), stride)
            series[f"HUST-{name}"] = found
    _, _, info = sampling.thin(np.arange(1.0, 3.0), np.zeros(2), stride)
    meta = {
        **info,
        "rise_window_v": list(RISE_WINDOW_V),
        "indicators": list(INDICATORS),
        "cycle_id_source": "raw_pickle_keys",
    }
    sampling.write_cache(output, meta, series)
    return len(series)


def load_with_meta(
    path: Path = OUTPUT,
) -> tuple[dict[str, object], dict[str, dict[int, dict[str, float]]]]:
    if not path.exists():
        return {}, {}
    meta, raw = sampling.read_cache(path)
    cells = {cell: {int(k): v for k, v in rows.items()} for cell, rows in raw.items()}
    return meta, cells


def load(path: Path = OUTPUT) -> dict[str, dict[int, dict[str, float]]]:
    return load_with_meta(path)[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=ARCHIVE)
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
        else ROOT / f"hust/indicators-fixed-stride{stride}.json"
    )
    print(f"{build(args.archive, output, stride)} cells written to {output}")


if __name__ == "__main__":
    main()
