"""Put irregular readings on the 5-second grid the equipment models require.

The last reading is held for at most ``max_age_s``; nothing is interpolated. A grid
point is usable only when every channel is present and fresh.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np

from argus.ingest.ocpp_mapping import MappedSample
from argus.simulator.telemetry_simulator import SENSOR_COLUMNS

CHANNELS = tuple(SENSOR_COLUMNS)
MAX_GRID_POINTS = 200_000


@dataclass(frozen=True)
class GridRow:
    time_s: float
    values: dict[str, float | None]
    stale: tuple[str, ...]
    missing: tuple[str, ...]

    @property
    def complete(self) -> bool:
        return not self.stale and not self.missing


def resample(
    samples: Sequence[MappedSample],
    extra: Mapping[str, Sequence[tuple[float, float]]] | None = None,
    *,
    step_s: float = 5.0,
    max_age_s: float | None = None,
) -> list[GridRow]:
    """``extra`` carries channels from another source, e.g. a vibration sensor."""
    if step_s <= 0 or not math.isfinite(step_s):
        raise ValueError("step_s must be finite and positive")
    max_age = step_s if max_age_s is None else max_age_s
    series: dict[str, dict[float, float]] = {c: {} for c in CHANNELS}
    for sample in samples:
        for name, value in sample.channels.items():
            if name in series:
                series[name][sample.time_s] = value
    for name, points in (extra or {}).items():
        if name in series:
            for t, v in points:
                series[name][float(t)] = float(v)
    firsts = [min(s) for s in series.values() if s]
    lasts = [max(s) for s in series.values() if s]
    if not firsts:
        return []
    start = math.ceil(min(firsts) / step_s) * step_s
    end = max(lasts)
    if (end - start) / step_s > MAX_GRID_POINTS:
        raise ValueError("time span is too long for one grid")
    times = {c: np.array(sorted(s)) for c, s in series.items()}
    data = {c: np.array([series[c][t] for t in times[c]]) for c in series}
    rows = []
    count = int(math.floor((end - start) / step_s + 1e-9)) + 1
    for k in range(max(count, 0)):
        t = start + k * step_s
        values: dict[str, float | None] = {}
        stale, missing = [], []
        for c in CHANNELS:
            idx = int(np.searchsorted(times[c], t, side="right")) - 1
            if idx < 0:
                values[c] = None
                missing.append(c)
            elif t - times[c][idx] > max_age:
                values[c] = None
                stale.append(c)
            else:
                values[c] = float(data[c][idx])
        rows.append(GridRow(float(t), values, tuple(stale), tuple(missing)))
    return rows


def engine_rows(rows: Sequence[GridRow]) -> list[tuple[float, dict[str, float]]]:
    """Complete rows only, as ``(time_s, sensor_row)`` for ``push_sample``."""
    return [
        (r.time_s, {c: float(v) for c, v in r.values.items() if v is not None})
        for r in rows
        if r.complete
    ]


def summary(rows: Sequence[GridRow]) -> dict[str, object]:
    n = len(rows)
    return {
        "grid_points": n,
        "complete_points": sum(r.complete for r in rows),
        "never_reported": sorted(
            c for c in CHANNELS if n and all(c in r.missing for r in rows)
        ),
        "stale_share": {
            c: round(sum(c in r.stale for r in rows) / n, 3) if n else 0.0
            for c in CHANNELS
        },
    }
