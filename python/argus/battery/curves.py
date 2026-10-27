"""Voltage-curve health indicators with a NumPy fallback for the C++ core.

Both implementations follow the same algorithm (running-maximum clamp, linear
interpolation of Q(V) on a uniform grid, truncated moving average), so a machine
without the compiled extension gets the same numbers.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

try:
    import argus_core as _native  # type: ignore

    _HAVE_NATIVE = hasattr(_native, "incremental_capacity")
except ImportError:  # pragma: no cover - depends on the local build
    _native = None
    _HAVE_NATIVE = False


def using_native_curves() -> bool:
    return _HAVE_NATIVE


@dataclass(frozen=True)
class IncrementalCapacity:
    voltage_v: np.ndarray
    dq_dv_ah_per_v: np.ndarray
    peak_voltage_v: float
    peak_height_ah_per_v: float
    peak_width_v: float
    area_ah: float


def _finite(name: str, values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=np.float64)
    if values.ndim != 1:
        raise ValueError(f"{name} must be one-dimensional")
    if not np.isfinite(values).all():
        raise ValueError(f"{name} must be finite")
    return values


def _incremental_numpy(
    voltage: np.ndarray, capacity: np.ndarray, bins: int, window: int
) -> IncrementalCapacity:
    if len(voltage) != len(capacity):
        raise ValueError("voltage and capacity must have the same length")
    if len(voltage) < 3:
        raise ValueError("at least three samples required")
    if bins < 8:
        raise ValueError("at least eight bins required")
    if window < 1 or window % 2 == 0 or window > bins:
        raise ValueError("smooth_window must be odd and not exceed bins")
    running = np.maximum.accumulate(voltage)
    # Equal voltages merge; the latest capacity wins.
    last = np.r_[running[1:] > running[:-1], True]
    v, q = running[last], capacity[last]
    if len(v) < 3 or not v[-1] > v[0]:
        raise ValueError("voltage range is degenerate")
    dv = (v[-1] - v[0]) / bins
    edges = v[0] + dv * np.arange(bins + 1)
    edges[-1] = v[-1]
    q_edge = np.interp(edges, v, q)
    raw = np.diff(q_edge) / dv
    half = window // 2
    smooth = np.empty(bins)
    for k in range(bins):
        smooth[k] = raw[max(0, k - half) : min(bins - 1, k + half) + 1].mean()
    centres = v[0] + dv * (np.arange(bins) + 0.5)
    p = int(np.argmax(smooth))
    peak = smooth[p]
    half_height = peak / 2
    left = centres[0]
    for k in range(p, 0, -1):
        if smooth[k - 1] < half_height:
            a, b = smooth[k - 1], smooth[k]
            left = centres[k - 1] + (half_height - a) / (b - a) * dv
            break
    right = centres[-1]
    for k in range(p, bins - 1):
        if smooth[k + 1] < half_height:
            a, b = smooth[k], smooth[k + 1]
            right = centres[k] + (a - half_height) / (a - b) * dv
            break
    return IncrementalCapacity(
        centres, smooth, float(centres[p]), float(peak), float(right - left),
        float(q_edge[-1] - q_edge[0]),
    )  # fmt: skip


def incremental_capacity(
    voltage_v: np.ndarray,
    capacity_ah: np.ndarray,
    bins: int = 160,
    smooth_window: int = 5,
    *,
    native: bool | None = None,
) -> IncrementalCapacity:
    """dQ/dV curve and dominant-peak features of a monotonic charge record."""
    v, q = _finite("voltage_v", voltage_v), _finite("capacity_ah", capacity_ah)
    if (_HAVE_NATIVE if native is None else native) and _HAVE_NATIVE:
        r = _native.incremental_capacity(v, q, bins, smooth_window)
        return IncrementalCapacity(
            np.array(r.voltage_v), np.array(r.dq_dv_ah_per_v), r.peak_voltage_v,
            r.peak_height_ah_per_v, r.peak_width_v, r.area_ah,
        )  # fmt: skip
    return _incremental_numpy(v, q, bins, smooth_window)


def time_between_voltages(
    time_s: np.ndarray,
    voltage_v: np.ndarray,
    v_low: float,
    v_high: float,
    *,
    native: bool | None = None,
) -> float | None:
    t, v = _finite("time_s", time_s), _finite("voltage_v", voltage_v)
    if (_HAVE_NATIVE if native is None else native) and _HAVE_NATIVE:
        return _native.time_between_voltages(t, v, v_low, v_high)
    if len(t) != len(v) or len(t) < 2:
        raise ValueError("time and voltage need the same length of at least two")
    if not (np.isfinite(v_low) and np.isfinite(v_high) and v_high > v_low):
        raise ValueError("voltage window must be finite and ordered")
    if np.any(np.diff(t) <= 0):
        raise ValueError("time must be strictly increasing")
    running = np.maximum.accumulate(v)

    def reach(level: float) -> float | None:
        hits = np.nonzero(running >= level)[0]
        if not len(hits):
            return None
        i = int(hits[0])
        if i == 0:
            return float(t[0])
        before = running[i - 1]
        fraction = (level - before) / (running[i] - before)
        return float(t[i - 1] + fraction * (t[i] - t[i - 1]))

    start, stop = reach(v_low), reach(v_high)
    return None if start is None or stop is None else stop - start


def estimate_dcir(
    current_a: np.ndarray,
    voltage_v: np.ndarray,
    min_step_a: float = 0.5,
    *,
    native: bool | None = None,
) -> float | None:
    i, v = _finite("current_a", current_a), _finite("voltage_v", voltage_v)
    if (_HAVE_NATIVE if native is None else native) and _HAVE_NATIVE:
        return _native.estimate_dcir(i, v, min_step_a)
    if len(i) != len(v) or len(i) < 2:
        raise ValueError("current and voltage need the same length of at least two")
    if not np.isfinite(min_step_a) or min_step_a <= 0:
        raise ValueError("min_step_a must be finite and positive")
    steps = np.abs(np.diff(i))
    at = int(np.argmax(steps))
    if steps[at] < min_step_a:
        return None
    return float(abs(v[at + 1] - v[at]) / steps[at])
