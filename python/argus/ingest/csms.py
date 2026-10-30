"""Passive OCPP 1.6J collector: stores meter values, never controls charging.

Cards are refused unless ``allow_all_tags`` is set (only for emulator tests), so a real
station that points here cannot start a session. Outside the loopback interface the
collector requires HTTP Basic credentials (OCPP security profile 1; use TLS in front).
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import datetime as dt
import hmac
import ipaddress
import itertools
import os
import re
import time
from http import HTTPStatus
from pathlib import Path
from typing import Any

import websockets
from ocpp.routing import on
from ocpp.v16 import ChargePoint, call_result
from ocpp.v16.enums import Action, AuthorizationStatus, RegistrationStatus
from websockets.asyncio.server import ServerConnection, serve
from websockets.http11 import Request, Response

from argus.ingest.store import OcppStore

STATION_ID = re.compile(r"^[\w.-]{1,64}$")
SUBPROTOCOL = "ocpp1.6"
HEARTBEAT_SECONDS = 300
DEFAULT_DB = Path(__file__).resolve().parents[3] / "artifacts" / "ocpp" / "ocpp.sqlite3"


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


class StationSession(ChargePoint):
    def __init__(
        self,
        station_id: str,
        connection: Any,
        store: OcppStore,
        counter: Any,
        allow_all_tags: bool,
    ) -> None:
        super().__init__(station_id, connection)
        self._store = store
        self._counter = counter
        self._tag_status = (
            AuthorizationStatus.accepted
            if allow_all_tags
            else AuthorizationStatus.invalid
        )

    @on(Action.boot_notification)
    def on_boot(
        self, charge_point_model: str, charge_point_vendor: str, **_: Any
    ) -> call_result.BootNotification:
        self._store.upsert_station(
            self.id, charge_point_vendor, charge_point_model, time.time()
        )
        return call_result.BootNotification(
            current_time=_now(),
            interval=HEARTBEAT_SECONDS,
            status=RegistrationStatus.accepted,
        )

    @on(Action.heartbeat)
    def on_heartbeat(self) -> call_result.Heartbeat:
        return call_result.Heartbeat(current_time=_now())

    @on(Action.status_notification)
    def on_status(self, **_: Any) -> call_result.StatusNotification:
        return call_result.StatusNotification()

    @on(Action.authorize)
    def on_authorize(self, **_: Any) -> call_result.Authorize:
        return call_result.Authorize(id_tag_info={"status": self._tag_status})

    @on(Action.start_transaction)
    def on_start(self, **_: Any) -> call_result.StartTransaction:
        return call_result.StartTransaction(
            transaction_id=next(self._counter),
            id_tag_info={"status": self._tag_status},
        )

    @on(Action.stop_transaction)
    def on_stop(self, **_: Any) -> call_result.StopTransaction:
        return call_result.StopTransaction()

    @on(Action.meter_values)
    def on_meter_values(
        self, connector_id: int, meter_value: list[dict[str, Any]], **_: Any
    ) -> call_result.MeterValues:
        self._store.add_meter_values(self.id, connector_id, meter_value, time.time())
        return call_result.MeterValues()


def _is_loopback(host: str) -> bool:
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return host == "localhost"


def _authorized(headers: Any, station: str, credentials: dict[str, str]) -> bool:
    value = headers.get("Authorization", "")
    if not value.startswith("Basic "):
        return False
    try:
        user, _, password = (
            base64.b64decode(value[6:], validate=True).decode().partition(":")
        )
    except (ValueError, UnicodeDecodeError):
        return False
    expected = credentials.get(station)
    if expected is None or user != station:
        return False
    return hmac.compare_digest(password.encode(), expected.encode())


def serve_collector(
    store: OcppStore,
    host: str = "127.0.0.1",
    port: int = 9000,
    *,
    credentials: dict[str, str] | None = None,
    allow_all_tags: bool = False,
) -> Any:
    """Return the websockets server context manager (``async with``)."""
    if not credentials and not _is_loopback(host):
        raise ValueError("credentials are required outside the loopback interface")
    counter = itertools.count(1)

    def check(connection: ServerConnection, request: Request) -> Response | None:
        station = request.path.split("?")[0].rstrip("/").split("/")[-1]
        if not STATION_ID.match(station):
            return connection.respond(HTTPStatus.BAD_REQUEST, "invalid station id\n")
        if credentials is not None and not _authorized(
            request.headers, station, credentials
        ):
            return connection.respond(HTTPStatus.UNAUTHORIZED, "unauthorized\n")
        return None

    async def handler(connection: ServerConnection) -> None:
        if connection.subprotocol != SUBPROTOCOL:
            await connection.close(1002, "ocpp1.6 required")
            return
        station = connection.request.path.split("?")[0].rstrip("/").split("/")[-1]
        session = StationSession(station, connection, store, counter, allow_all_tags)
        try:
            await session.start()
        except websockets.ConnectionClosed:
            pass

    return serve(
        handler,
        host,
        port,
        subprotocols=[SUBPROTOCOL],  # type: ignore[list-item]
        process_request=check,
    )


def _credentials_from_env() -> dict[str, str] | None:
    raw = os.environ.get("ARGUS_OCPP_PASSWORDS", "")
    pairs = [p.partition(":") for p in raw.split(",") if p]
    return {s: pw for s, _, pw in pairs} or None


async def _run(args: argparse.Namespace) -> None:
    store = OcppStore(args.db)
    async with serve_collector(
        store, args.host, args.port, credentials=_credentials_from_env()
    ):
        await asyncio.get_running_loop().create_future()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9000)
    asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    main()
