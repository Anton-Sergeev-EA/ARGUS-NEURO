"""How histories are thinned, decided without looking at how long a cell lives.

An earlier pipeline kept ``ceil(N / 600)``-th cycle, so the spacing of a window told a
model how long the whole history was, and with it how soon the cell would fail. The
rule here depends only on the physical cycle number: cycle ``c`` is kept when
``(c - 1) % stride == 0``. Truncating a history therefore never changes which of the
remaining cycles are kept. The old rule survives only as ``legacy_adaptive_stride``
for diagnostic comparison and is labelled as such in every cache and report.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

DEFAULT_STRIDE = 5
LEGACY_MAX_POINTS = 600
FIXED = "fixed_physical_stride"
ADAPTIVE = "adaptive_stride_ceil_N_over_600"


def legacy_adaptive_stride(length: int, max_points: int = LEGACY_MAX_POINTS) -> int:
    """Diagnostic only: this stride depends on the full history length."""
    return max(1, int(np.ceil(length / max_points)))


def keep_mask(cycle_ids: np.ndarray, stride: int) -> np.ndarray:
    """Cycles kept at a fixed physical stride; independent of everything else."""
    if stride < 1:
        raise ValueError("stride must be a positive number of cycles")
    return (np.asarray(cycle_ids) - 1) % stride == 0


def thin(
    cycle_ids: np.ndarray, values: np.ndarray, stride: int | str
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """Return thinned ids and values plus the sampling description for the cache."""
    ids = np.asarray(cycle_ids)
    if stride == "adaptive":
        step = legacy_adaptive_stride(len(ids))
        selected = np.arange(len(ids))[::step]
        info = {"sampling": ADAPTIVE, "stride": step, "diagnostic_only": True}
        return ids[selected], np.asarray(values)[selected], info
    mask = keep_mask(ids, int(stride))
    info = {"sampling": FIXED, "stride": int(stride), "diagnostic_only": False}
    return ids[mask], np.asarray(values)[mask], info


def write_cache(path: Path, meta: dict[str, Any], cells: Any) -> None:
    """Caches carry their own sampling description next to the data."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"meta": meta, "cells": cells}) + "\n", encoding="utf-8")


def read_cache(path: Path) -> tuple[dict[str, Any], Any]:
    """Read a cache in the new wrapped format or the legacy bare format."""
    document = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(document, dict) and "cells" in document:
        return document["meta"], document["cells"]
    return {"sampling": ADAPTIVE, "stride": None, "diagnostic_only": True}, document
