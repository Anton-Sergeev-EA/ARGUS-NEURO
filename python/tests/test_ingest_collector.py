"""Collector and emulator talking over a real local WebSocket."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import pytest

pytest.importorskip("ocpp")
import websockets  # noqa: E402
from ocpp.v16 import ChargePoint, call  # noqa: E402

from argus.ingest import emulator  # noqa: E402
from argus.ingest.csms import serve_collector  # noqa: E402
from argus.ingest.resample import engine_rows, resample, summary  # noqa: E402
from argus.ingest.store import OcppStore  # noqa: E402

T0 = 1_800_000_000.0


def drive(
    body: Callable[[OcppStore, str], Awaitable[Any]],
    **options: Any,
) -> OcppStore:
    store = OcppStore(":memory:")

    async def main() -> None:
        async with serve_collector(store, "127.0.0.1", 0, **options) as server:
            port = server.sockets[0].getsockname()[1]
            await body(store, f"ws://127.0.0.1:{port}")

    asyncio.run(main())
    return store


def session(scenario: str, **kwargs: Any) -> OcppStore:
    async def body(store: OcppStore, url: str) -> None:
        await emulator.run(url, scenario, t0=T0, n=60, **kwargs)

    return drive(body)


def station(scenario: str) -> str:
    return f"EMU-{scenario.upper().replace('_', '-')}"


def test_emulator_is_deterministic() -> None:
    a = emulator.generate("healthy", 30, 5.0, seed=4, t0=T0)
    assert a == emulator.generate("healthy", 30, 5.0, seed=4, t0=T0)
    assert a != emulator.generate("healthy", 30, 5.0, seed=5, t0=T0)
    with pytest.raises(ValueError):
        emulator.generate("nope", 1, 5.0, 1, T0)


def test_healthy_session_is_stored_but_cannot_feed_the_models_without_vibration() -> (
    None
):
    store = session("healthy")
    samples = store.samples(station("healthy"), 1)
    assert len(samples) == 60
    rows = resample(samples)
    assert summary(rows)["never_reported"] == ["vibration_g"]
    assert engine_rows(rows) == []
    vib = [(s.time_s, 0.02) for s in samples]
    done = resample(samples, {"vibration_g": vib})
    assert len(engine_rows(done)) == 60


def test_current_timestamps_raise_no_drift_flag() -> None:
    async def body(store: OcppStore, url: str) -> None:
        await emulator.run(url, "healthy", n=5)

    assert drive(body).quality("EMU-HEALTHY") == {}


def test_overheating_scenario_shows_up_in_the_temperature_channel() -> None:
    samples = session("overheating").samples(station("overheating"), 1)
    temps = [s.channels["temperature_c"] for s in samples]
    assert max(temps[:25]) < 40 and temps[-1] > 75


def test_missing_channels_are_reported_as_never_reported() -> None:
    store = session("missing_channels")
    info = summary(resample(store.samples(station("missing_channels"), 1)))
    assert {"frequency_hz", "temperature_c", "vibration_g"} <= set(
        info["never_reported"]
    )


def test_duplicate_messages_are_stored_once_and_logged() -> None:
    store = session("duplicates")
    assert len(store.samples(station("duplicates"), 1)) == 60
    assert store.quality(station("duplicates"))["repeated_values"] >= 1


def test_clock_drift_is_logged_and_dropouts_leave_a_gap() -> None:
    assert session("clock_drift").quality(station("clock_drift")) == {"clock_drift": 60}
    samples = session("dropout").samples(station("dropout"), 1)
    assert len(samples) == 60 - 12
    rows = resample(samples, {"vibration_g": [(s.time_s, 0.0) for s in samples]})
    assert len(engine_rows(rows)) < len(rows)


def test_cards_are_refused_by_default_and_accepted_only_on_request() -> None:
    async def ask(store: OcppStore, url: str) -> None:
        async with websockets.connect(
            f"{url}/ST9",
            subprotocols=["ocpp1.6"],  # type: ignore[list-item]
        ) as ws:
            point = ChargePoint("ST9", ws)
            reader = asyncio.create_task(point.start())
            reply = await point.call(call.Authorize(id_tag="CARD"))
            started = await point.call(
                call.StartTransaction(
                    connector_id=1,
                    id_tag="CARD",
                    meter_start=0,
                    timestamp="2026-10-30T12:00:00Z",
                )
            )
            assert (reply.id_tag_info["status"], started.id_tag_info["status"]) == (
                ("Invalid", "Invalid") if not options else ("Accepted", "Accepted")
            )
            reader.cancel()

    options: dict[str, Any] = {}
    drive(ask)
    options = {"allow_all_tags": True}
    drive(ask, **options)


def test_unknown_actions_get_an_error_not_a_crash() -> None:
    async def body(store: OcppStore, url: str) -> None:
        async with websockets.connect(
            f"{url}/ST8",
            subprotocols=["ocpp1.6"],  # type: ignore[list-item]
        ) as ws:
            point = ChargePoint("ST8", ws)
            reader = asyncio.create_task(point.start())
            # The collector answers with a CallError, which the client logs as None.
            assert await point.call(call.DataTransfer(vendor_id="x")) is None
            assert await point.call(call.Heartbeat()) is not None  # still alive
            reader.cancel()

    drive(body)


def test_basic_credentials_are_enforced() -> None:
    async def body(store: OcppStore, url: str) -> None:
        with pytest.raises(websockets.exceptions.InvalidStatus) as bad:
            await emulator.run(url, "healthy", n=3, password="wrong", station_id="S1")
        assert bad.value.response.status_code == 401
        with pytest.raises(websockets.exceptions.InvalidStatus):
            await emulator.run(url, "healthy", n=3, station_id="S1")  # no header
        assert (
            await emulator.run(url, "healthy", n=3, password="pw", station_id="S1") == 3
        )
        with pytest.raises(websockets.exceptions.InvalidStatus) as other:
            await emulator.run(url, "healthy", n=3, password="pw", station_id="S2")
        assert other.value.response.status_code == 401

    store = drive(body, credentials={"S1": "pw"})
    assert len(store.samples("S1", 1)) == 3


def test_bad_station_ids_and_remote_binding_are_refused() -> None:
    async def body(store: OcppStore, url: str) -> None:
        with pytest.raises(websockets.exceptions.InvalidStatus) as bad:
            async with websockets.connect(
                f"{url}/bad%20id!",
                subprotocols=["ocpp1.6"],  # type: ignore[list-item]
            ):
                pass
        assert bad.value.response.status_code == 400

    drive(body)
    with pytest.raises(ValueError):
        serve_collector(OcppStore(":memory:"), "0.0.0.0", 0)
    drive(lambda *_: asyncio.sleep(0), credentials={"S": "x"})
