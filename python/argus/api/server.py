"""FastAPI service for an explicitly labelled synthetic fleet demonstration."""

from __future__ import annotations

import asyncio
import contextlib
import datetime as dt
import json
import logging
import time
from collections.abc import AsyncIterator
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from argus.inference import HealthInferenceEngine
from argus.simulator import AssetSimulator, AssetType, FaultType
from argus.simulator.telemetry_simulator import SENSOR_COLUMNS

REPO_ROOT = Path(__file__).resolve().parents[3]
DASHBOARD_DIR = REPO_ROOT / "web" / "dashboard"
TICK_SECONDS = 1.5
RUN_STEPS = 400
WAVEFORM_SAMPLE_RATE_HZ = 2000.0
SEND_TIMEOUT_SECONDS = 3.0
STALE_AFTER_SECONDS = 10.0
logger = logging.getLogger(__name__)

_SCENARIOS: list[tuple[str, AssetType, FaultType, float]] = [
    ("SHIP-CONV-01", AssetType.MARINE_CONVERTER, FaultType.NONE, 0.0),
    ("SHIP-CONV-02", AssetType.MARINE_CONVERTER, FaultType.VOLTAGE_SAG, 0.5),
    ("SHIP-THRUST-01", AssetType.MARINE_CONVERTER, FaultType.BEARING_WEAR, 0.45),
    ("UAV-PDU-07", AssetType.UAV_PDU, FaultType.NONE, 0.0),
    ("UAV-PDU-11", AssetType.UAV_PDU, FaultType.OVERHEATING, 0.4),
    ("UAV-PDU-14", AssetType.UAV_PDU, FaultType.FREQUENCY_DRIFT, 0.55),
]


class LiveFleet:
    """Advance synthetic runs; only the producer thread may mutate the engine."""

    def __init__(self) -> None:
        self._sim = AssetSimulator(seed=123)
        self._engine = HealthInferenceEngine()
        self._runs = {}
        self._cursors = {aid: 0 for aid, *_ in _SCENARIOS}
        self._latest_snapshot: dict[str, Any] = {}
        self._alerts: list[dict[str, Any]] = []
        self._was_anomalous: dict[str, bool] = {}
        for asset_id, asset_type, fault_type, onset in _SCENARIOS:
            self._runs[asset_id] = self._sim.generate_run(
                asset_id=asset_id,
                asset_type=asset_type,
                n_steps=RUN_STEPS,
                dt_seconds=5.0,
                fault_type=fault_type,
                fault_onset_frac=onset,
            )

    @property
    def model_backed(self) -> bool:
        return self._engine.model_backed

    def tick(self) -> dict[str, Any]:
        assets_payload = []
        now = dt.datetime.now(dt.timezone.utc).isoformat()
        for asset_id, asset_type, _fault_type, _onset in _SCENARIOS:
            run = self._runs[asset_id]
            cursor = self._cursors[asset_id]
            row = run.iloc[cursor]
            sensor_row = {c: float(row[c]) for c in SENSOR_COLUMNS}
            self._engine.push_sample(
                asset_id, sensor_row, sample_time_s=float(row["t_s"])
            )
            waveform = self._sim.generate_waveform(
                asset_type,
                FaultType(row["fault_type"]),
                severity=float(row["fault_severity"]),
                sample_rate_hz=WAVEFORM_SAMPLE_RATE_HZ,
            )
            assessment = self._engine.assess(
                asset_id, asset_type.value, waveform, WAVEFORM_SAMPLE_RATE_HZ
            )
            was_anomalous = self._was_anomalous.get(asset_id, False)
            if assessment.is_anomaly is True and not was_anomalous:
                self._alerts.insert(
                    0,
                    {
                        "timestamp": now,
                        "asset_id": asset_id,
                        "message": f"Anomaly detected on {asset_id}",
                    },
                )
                self._alerts = self._alerts[:30]
            self._was_anomalous[asset_id] = assessment.is_anomaly is True
            assets_payload.append(
                {
                    "asset_id": asset_id,
                    "asset_type": asset_type.value,
                    "sensors": sensor_row,
                    "assessment": asdict(assessment),
                }
            )
            self._cursors[asset_id] = (cursor + 1) % len(run)
            if self._cursors[asset_id] == 0:
                # A new synthetic life is not a continuation of the failed asset.
                self._engine.reset_asset(asset_id)
                self._was_anomalous[asset_id] = False

        self._latest_snapshot = {
            "type": "tick",
            "timestamp": now,
            "source": "simulation",
            "model_backed": self._engine.model_backed,
            "assets": assets_payload,
            "alerts": self._alerts[:10],
        }
        return self._latest_snapshot

    def snapshot(self) -> dict[str, Any]:
        """Return the last completed tick without advancing or running inference."""
        return self._latest_snapshot


class ConnectionManager:
    """Each client has one sender and at most one pending, latest snapshot."""

    def __init__(self, send_timeout: float = SEND_TIMEOUT_SECONDS) -> None:
        self._queues: dict[WebSocket, asyncio.Queue[str]] = {}
        self._senders: dict[WebSocket, asyncio.Task[None]] = {}
        self._send_timeout = send_timeout

    @property
    def connected_count(self) -> int:
        return len(self._queues)

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        queue: asyncio.Queue[str] = asyncio.Queue(maxsize=1)
        self._queues[ws] = queue
        self._senders[ws] = asyncio.create_task(self._send_loop(ws, queue))

    async def _send_loop(self, ws: WebSocket, queue: asyncio.Queue[str]) -> None:
        try:
            while True:
                message = await queue.get()
                await asyncio.wait_for(ws.send_text(message), self._send_timeout)
        except Exception:
            # CancelledError inherits BaseException and propagates normally.
            logger.debug("Telemetry client send failed", exc_info=True)
        finally:
            self._queues.pop(ws, None)
            self._senders.pop(ws, None)
            with contextlib.suppress(Exception):
                await asyncio.wait_for(ws.close(), self._send_timeout)

    @staticmethod
    def _enqueue(queue: asyncio.Queue[str], message: str) -> None:
        if queue.full():
            queue.get_nowait()
        queue.put_nowait(message)

    def send_snapshot(self, ws: WebSocket, payload: dict[str, Any]) -> None:
        queue = self._queues.get(ws)
        if queue is not None:
            self._enqueue(queue, json.dumps(payload, allow_nan=False))

    async def broadcast(self, payload: dict[str, Any]) -> None:
        message = json.dumps(payload, allow_nan=False)
        # There are no awaits while iterating. Connect/disconnect cannot mutate
        # the dictionary until all latest-value queues have been updated.
        for queue in self._queues.values():
            self._enqueue(queue, message)

    async def disconnect(self, ws: WebSocket) -> None:
        self._queues.pop(ws, None)
        task = self._senders.pop(ws, None)
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def close(self) -> None:
        await asyncio.gather(*(self.disconnect(ws) for ws in tuple(self._senders)))


@dataclass
class ServiceState:
    fleet: LiveFleet
    manager: ConnectionManager
    stop: asyncio.Event
    snapshot: dict[str, Any] | None = None
    last_tick: float | None = None
    error: str | None = None
    task: asyncio.Task[None] | None = None


async def _broadcast_loop(state: ServiceState) -> None:
    try:
        while not state.stop.is_set():
            # Inference never runs on the ASGI event loop; REST and clients stay
            # responsive. One producer prevents concurrent engine mutations.
            payload = await asyncio.to_thread(state.fleet.tick)
            await state.manager.broadcast(payload)
            state.snapshot = payload
            state.last_tick = time.monotonic()
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(state.stop.wait(), TICK_SECONDS)
    except Exception as exc:
        state.error = type(exc).__name__
        logger.exception("Telemetry producer stopped")


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    state = ServiceState(
        fleet=await asyncio.to_thread(LiveFleet),
        manager=ConnectionManager(),
        stop=asyncio.Event(),
    )
    app.state.telemetry = state
    state.task = asyncio.create_task(_broadcast_loop(state))
    try:
        yield
    finally:
        state.stop.set()
        # Do not cancel a to_thread tick and abandon its still-running worker.
        await state.task
        await state.manager.close()


app = FastAPI(
    title="ARGUS-NEURO",
    description="Evidence-driven diagnostics: synthetic fleet demonstration.",
    version="1.1.0",
    lifespan=lifespan,
)


@app.get("/api/health")
async def health() -> JSONResponse:
    state: ServiceState | None = getattr(app.state, "telemetry", None)
    if state is None:
        return JSONResponse({"status": "starting", "source": "simulation"}, 503)
    age = None if state.last_tick is None else time.monotonic() - state.last_tick
    running = state.task is not None and not state.task.done()
    healthy = running and age is not None and age <= STALE_AFTER_SECONDS
    status = "ok" if healthy else "starting" if age is None and running else "degraded"
    return JSONResponse(
        {
            "status": status,
            "source": "simulation",
            "model_backed": state.fleet.model_backed,
            "last_tick_age_seconds": age,
            "producer_running": running,
            "connected_clients": state.manager.connected_count,
            "error": state.error,
        },
        200 if healthy else 503,
    )


@app.get("/api/fleet")
async def get_fleet() -> JSONResponse:
    state: ServiceState | None = getattr(app.state, "telemetry", None)
    if state is None or state.snapshot is None:
        return JSONResponse({"status": "starting", "source": "simulation"}, 503)
    return JSONResponse(state.snapshot)


@app.websocket("/ws/telemetry")
async def ws_telemetry(websocket: WebSocket) -> None:
    state: ServiceState = app.state.telemetry
    await state.manager.connect(websocket)
    try:
        if state.snapshot is not None:
            state.manager.send_snapshot(websocket, state.snapshot)
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await state.manager.disconnect(websocket)


if DASHBOARD_DIR.exists():
    app.mount(
        "/", StaticFiles(directory=str(DASHBOARD_DIR), html=True), name="dashboard"
    )
