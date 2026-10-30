"""Deterministic OCPP 1.6J charge-point emulator for tests and demonstrations.

Time is virtual: samples carry synthetic timestamps and are sent without waiting.
Values are synthetic and illustrate message shape, not any real charger.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import datetime as dt
from dataclasses import dataclass
from typing import Any

import numpy as np
import websockets
from ocpp.v16 import ChargePoint, call

SCENARIOS = (
    "healthy",
    "overheating",
    "missing_channels",
    "duplicates",
    "clock_drift",
    "dropout",
)
OFFERED_W = 22_000.0
DRIFT_SECONDS = 3600.0


@dataclass(frozen=True)
class Message:
    time_s: float
    readings: dict[str, float]  # OCPP measurand -> value in its default unit
    repeat: int = 1


def generate(
    scenario: str, n: int, step_s: float, seed: int, t0: float
) -> list[Message]:
    if scenario not in SCENARIOS:
        raise ValueError(f"unknown scenario: {scenario}")
    rng = np.random.default_rng(seed)
    out: list[Message] = []
    for i in range(n):
        if scenario == "dropout" and 0.4 * n <= i < 0.6 * n:
            continue
        volt = 400.0 + rng.normal(0, 1.0)
        amps = 32.0 + rng.normal(0, 0.5)
        temp = 35.0 + rng.normal(0, 0.3)
        if scenario == "overheating" and i >= n // 2:
            temp += 50.0 * (i - n // 2) / max(n - n // 2, 1)
        readings = {
            "Voltage": volt,
            "Current.Import": amps,
            "Temperature": temp,
            "Frequency": 50.0 + rng.normal(0, 0.02),
            "Power.Active.Import": volt * amps,
            "Power.Offered": OFFERED_W,
        }
        if scenario == "missing_channels":
            del readings["Frequency"], readings["Temperature"]
        stamp = t0 + i * step_s + (DRIFT_SECONDS if scenario == "clock_drift" else 0.0)
        repeat = 2 if scenario == "duplicates" and i % 10 == 9 else 1
        out.append(Message(stamp, readings, repeat))
    return out


UNITS = {
    "Voltage": "V",
    "Current.Import": "A",
    "Temperature": "Celsius",
    "Power.Active.Import": "W",
    "Power.Offered": "W",
}


def payload(message: Message) -> list[dict[str, Any]]:
    stamp = dt.datetime.fromtimestamp(message.time_s, dt.timezone.utc).isoformat()
    sampled = []
    for measurand, value in message.readings.items():
        item = {"value": f"{value:.3f}", "measurand": measurand}
        if measurand in UNITS:
            item["unit"] = UNITS[measurand]
        sampled.append(item)
    return [{"timestamp": stamp, "sampled_value": sampled}]


async def run(
    url: str,
    scenario: str = "healthy",
    *,
    n: int = 120,
    step_s: float = 5.0,
    seed: int = 1,
    t0: float | None = None,
    password: str | None = None,
    station_id: str | None = None,
) -> int:
    """Send one session to ``url`` (``ws://host:port``); return messages sent."""
    station = station_id or f"EMU-{scenario.upper().replace('_', '-')}"
    start = t0 if t0 is not None else float(int(dt.datetime.now().timestamp()))
    headers = None
    if password is not None:
        token = base64.b64encode(f"{station}:{password}".encode()).decode()
        headers = {"Authorization": f"Basic {token}"}
    sent = 0
    async with websockets.connect(
        f"{url.rstrip('/')}/{station}",
        subprotocols=["ocpp1.6"],  # type: ignore[list-item]
        additional_headers=headers,
    ) as connection:
        point = ChargePoint(station, connection)
        reader = asyncio.create_task(point.start())
        try:
            await point.call(
                call.BootNotification(
                    charge_point_model="Emulator", charge_point_vendor="ARGUS"
                )
            )
            for message in generate(scenario, n, step_s, seed, start):
                for _ in range(message.repeat):
                    await point.call(
                        call.MeterValues(connector_id=1, meter_value=payload(message))
                    )
                    sent += 1
        finally:
            reader.cancel()
    return sent


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="ws://127.0.0.1:9000")
    parser.add_argument("--scenario", choices=SCENARIOS, default="healthy")
    parser.add_argument("--count", type=int, default=120)
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args()
    sent = asyncio.run(run(args.url, args.scenario, n=args.count, seed=args.seed))
    print(f"sent {sent} MeterValues messages")


if __name__ == "__main__":
    main()
