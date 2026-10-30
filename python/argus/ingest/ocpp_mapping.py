"""Map OCPP 1.6 ``MeterValues`` onto the sensor channels that ARGUS models use.

Only what the charge point actually reports is mapped. A missing measurand leaves its
channel out: nothing is guessed or filled in. ``vibration_g`` is never provided by OCPP.
"""

from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass
from typing import Any

TEMPERATURE_CELSIUS = {
    None: lambda v: v,
    "Celsius": lambda v: v,
    "Fahrenheit": lambda v: (v - 32.0) * 5.0 / 9.0,
    "K": lambda v: v - 273.15,
}
POWER_WATTS = {None: lambda v: v, "W": lambda v: v, "kW": lambda v: v * 1000.0}
IDENTITY = {None: lambda v: v}

# measurand -> (units accepted with their conversion, how phases are combined)
MEASURANDS: dict[str, tuple[dict[str | None, Any], str]] = {
    "Voltage": ({**IDENTITY, "V": lambda v: v}, "mean"),
    "Current.Import": ({**IDENTITY, "A": lambda v: v}, "mean"),
    "Frequency": ({**IDENTITY, "Hz": lambda v: v}, "mean"),
    "Temperature": (TEMPERATURE_CELSIUS, "max"),
    "Power.Active.Import": (POWER_WATTS, "sum"),
    "Power.Offered": (POWER_WATTS, "sum"),
}
DIRECT = {
    "Voltage": "voltage_v",
    "Current.Import": "current_a",
    "Frequency": "frequency_hz",
    "Temperature": "temperature_c",
}


@dataclass(frozen=True)
class MappedSample:
    time_s: float
    channels: dict[str, float]
    issues: tuple[str, ...] = ()


def parse_time(stamp: Any) -> float | None:
    """Seconds since the epoch of an ISO 8601 time that carries a zone, else ``None``."""
    if not isinstance(stamp, str):
        return None
    try:
        parsed = dt.datetime.fromisoformat(stamp)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.timestamp()


def _combine(values: list[float], how: str) -> float:
    if how == "sum":
        return sum(values)
    if how == "max":
        return max(values)
    return sum(values) / len(values)


def map_meter_value(entry: dict[str, Any]) -> MappedSample | None:
    """Map one element of the ``meterValue`` list; ``None`` if its time is unusable."""
    time_s = parse_time(entry.get("timestamp"))
    if time_s is None:
        return None
    issues: list[str] = []
    found: dict[str, list[tuple[str | None, float]]] = {}
    for item in entry.get("sampled_value") or []:
        measurand = item.get("measurand") or "Energy.Active.Import.Register"
        if measurand not in MEASURANDS or item.get("format") == "SignedData":
            continue
        convert = MEASURANDS[measurand][0]
        unit = item.get("unit")
        unit = getattr(unit, "value", unit)
        if unit not in convert:
            issues.append(f"unsupported_unit:{measurand}")
            continue
        try:
            value = float(item["value"])
        except (KeyError, TypeError, ValueError):
            issues.append(f"invalid_value:{measurand}")
            continue
        if not math.isfinite(value):
            issues.append(f"invalid_value:{measurand}")
            continue
        phase = item.get("phase")
        phase = getattr(phase, "value", phase)
        found.setdefault(measurand, []).append((phase, convert[unit](value)))
    combined: dict[str, float] = {}
    for measurand, readings in found.items():
        totals = [v for p, v in readings if p is None]
        pool = totals or [v for _, v in readings]
        combined[measurand] = _combine(pool, MEASURANDS[measurand][1])
    channels = {DIRECT[m]: v for m, v in combined.items() if m in DIRECT}
    power, offered = combined.get("Power.Active.Import"), combined.get("Power.Offered")
    if power is not None and offered is not None and offered > 0:
        channels["load_factor"] = power / offered
    return MappedSample(time_s, channels, tuple(issues))
