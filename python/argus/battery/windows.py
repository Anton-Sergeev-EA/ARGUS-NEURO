"""One window constructor shared by every configuration that is compared.

Comparisons between feature sets are only meaningful when every set sees the same
windows. A window here is ``size`` consecutive comparable records that end strictly
before the threshold event; it uses nothing recorded after its last point. Which
windows exist depends on the *common* requirement (every indicator present), never on
which channels a particular model happens to use.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from argus.battery.schema import BatteryRequest
from argus.battery.training import threshold_event

WINDOW = 8


@dataclass(frozen=True)
class CellWindows:
    """All windows of one cell. Rows of every array line up."""

    cell_id: str
    capacity: np.ndarray  # (n, size) SOH fraction of the reference capacity
    cycle_offset: np.ndarray  # (n, size) cycles since the window start, in units of 100
    indicators: dict[str, np.ndarray]  # name -> (n, size)
    position: np.ndarray  # (n,) physical cycle of the last point
    target: np.ndarray  # (n,) cycles from the last point to the event
    event_cycle: float | None
    censored: bool

    def __len__(self) -> int:
        return len(self.position)


def cell_windows(
    history: BatteryRequest,
    indicator_series: dict[int, dict[str, float]],
    required: tuple[str, ...],
    size: int = WINDOW,
) -> CellWindows:
    """Windows of one cell; those lacking any ``required`` indicator are dropped for all."""
    p = history.profile
    event = threshold_event(history)
    rows = [r for r in history.records if r.condition_id == p.reference_condition_id]
    capacity, offset, position, target = [], [], [], []
    indicators: dict[str, list[list[float]]] = {name: [] for name in required}
    for end in range(size, len(rows) + 1):
        window = rows[end - size : end]
        last = window[-1].equivalent_cycles
        if event is None or last >= event:
            break
        extra = [indicator_series.get(int(r.equivalent_cycles)) for r in window]
        if required and any(
            e is None or any(n not in e for n in required) for e in extra
        ):
            continue
        axis = np.array([r.equivalent_cycles for r in window])
        capacity.append([r.capacity_ah / p.reference_capacity_ah for r in window])
        offset.append((axis - axis[0]) / 100)
        position.append(last)
        target.append(event - last)
        for name in required:
            indicators[name].append([e[name] for e in extra])  # type: ignore[index]
    shape = (len(position), size)
    return CellWindows(
        cell_id=p.battery_id,
        capacity=np.array(capacity, dtype=float).reshape(shape),
        cycle_offset=np.array(offset, dtype=float).reshape(shape),
        indicators={
            n: np.array(v, dtype=float).reshape(shape) for n, v in indicators.items()
        },
        position=np.array(position, dtype=float),
        target=np.array(target, dtype=float),
        event_cycle=None if event is None else float(event),
        censored=event is None,
    )


def stack(
    cells: list[CellWindows], channels: tuple[str, ...], with_offset: bool
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Flatten selected channels: ``(x, y, cell_index)``.

    ``channels`` names indicator channels to include in addition to capacity.
    """
    xs, ys, owners = [], [], []
    for index, cell in enumerate(cells):
        if not len(cell):
            continue
        parts = [cell.capacity]
        if with_offset:
            parts.append(cell.cycle_offset)
        parts += [cell.indicators[name] for name in channels]
        xs.append(np.concatenate(parts, axis=1))
        ys.append(cell.target)
        owners.append(np.full(len(cell), index))
    if not xs:
        return np.empty((0, 0)), np.empty(0), np.empty(0, dtype=int)
    return np.concatenate(xs), np.concatenate(ys), np.concatenate(owners)


def window_report(cells: list[CellWindows]) -> dict[str, int]:
    """Counts printed into every report so a reader can see what was compared."""
    return {
        "cells": len(cells),
        "cells_with_windows": sum(1 for c in cells if len(c)),
        "windows": sum(len(c) for c in cells),
        "censored_cells": sum(1 for c in cells if c.censored),
    }
