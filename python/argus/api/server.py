"""ARGUS-NEURO backend: FastAPI REST + WebSocket service that runs the
live fleet simulation through the two-tier ML/DL inference engine and
streams the result to the web dashboard in real time.

Run with::

    uvicorn argus.api.server:app --reload --port 8000

then open http://localhost:8000/ in a browser.
"""

from __future__ import annotations

import asyncio
import contextlib
import datetime as dt
import json
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from argus.inference import HealthInferenceEngine
from argus.simulator import AssetSimulator, AssetType, FaultType
from argus.simulator.telemetry_simulator import SENSOR_COLUMNS

REPO_ROOT = Path(__file__).resolve().parents[3]
DASHBOARD_DIR = REPO_ROOT / "web" / "dashboard"

TICK_SECONDS = 1.5
RUN_STEPS = 400
WAVEFORM_SAMPLE_RATE_HZ = 2000.0

# A representative mixed fleet with a deliberate mix of healthy and
# degrading assets, so the dashboard demonstrates the full range of the
# health index without needing the user to inject anything by hand.
_SCENARIOS: list[tuple[str, AssetType, FaultType, float]] = [
    ("SHIP-CONV-01", AssetType.MARINE_CONVERTER, FaultType.NONE, 0.0),
    ("SHIP-CONV-02", AssetType.MARINE_CONVERTER, FaultType.VOLTAGE_SAG, 0.5),
    ("SHIP-THRUST-01", AssetType.MARINE_CONVERTER, FaultType.BEARING_WEAR, 0.45),
    ("UAV-PDU-07", AssetType.UAV_PDU, FaultType.NONE, 0.0),
    ("UAV-PDU-11", AssetType.UAV_PDU, FaultType.OVERHEATING, 0.4),
    ("UAV-PDU-14", AssetType.UAV_PDU, FaultType.FREQUENCY_DRIFT, 0.55),
]


class LiveFleet:
    """Owns the precomputed demo runs and steps them forward each tick,
    feeding both tiers of the inference engine and keeping the latest
    snapshot + a rolling alert log for clients that connect mid-stream."""

    def __init__(self) -> None:
        self._sim = AssetSimulator(seed=123)
        self._engine = HealthInferenceEngine()
        self._runs = {}
        self._cursors = {aid: 0 for aid, *_ in _SCENARIOS}
        self._latest_snapshot: dict = {}
        self._alerts: list[dict] = []
        self._was_anomalous: dict[str, bool] = {}

        for asset_id, asset_type, fault_type, onset in _SCENARIOS:
            self._runs[asset_id] = self._sim.generate_run(
                asset_id=asset_id, asset_type=asset_type,
                n_steps=RUN_STEPS, dt_seconds=5.0,
                fault_type=fault_type, fault_onset_frac=onset,
            )

    @property
    def model_backed(self) -> bool:
        return self._engine.model_backed

    def tick(self) -> dict:
        assets_payload = []
        now = dt.datetime.now(dt.timezone.utc).isoformat()

        for asset_id, asset_type, _fault_type, _onset in _SCENARIOS:
            run = self._runs[asset_id]
            cursor = self._cursors[asset_id]
            row = run.iloc[cursor]

            sensor_row = {c: float(row[c]) for c in SENSOR_COLUMNS}
            self._engine.push_sample(asset_id, sensor_row)

            waveform = self._sim.generate_waveform(
                asset_type,
                FaultType(row["fault_type"]),
                severity=float(row["fault_severity"]),
                sample_rate_hz=WAVEFORM_SAMPLE_RATE_HZ,
            )
            assessment = self._engine.assess(
                asset_id, asset_type.value, waveform, WAVEFORM_SAMPLE_RATE_HZ,
            )

            was_anomalous = self._was_anomalous.get(asset_id, False)
            if assessment.is_anomaly and not was_anomalous:
                self._alerts.insert(0, {
                    "timestamp": now,
                    "asset_id": asset_id,
                    "message": f"Anomaly detected on {asset_id} "
                               f"(health index {assessment.health_index:.0f})",
                })
                self._alerts = self._alerts[:30]
            self._was_anomalous[asset_id] = assessment.is_anomaly

            assets_payload.append({
                "asset_id": asset_id,
                "asset_type": asset_type.value,
                "sensors": sensor_row,
                "assessment": asdict(assessment),
            })

            self._cursors[asset_id] = (cursor + 1) % len(run)

        self._latest_snapshot = {
            "type": "tick",
            "timestamp": now,
            "model_backed": self._engine.model_backed,
            "assets": assets_payload,
            "alerts": self._alerts[:10],
        }
        return self._latest_snapshot

    def snapshot(self) -> dict:
        return self._latest_snapshot or self.tick()


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self._connections.discard(ws)

    async def broadcast(self, payload: dict) -> None:
        message = json.dumps(payload)
        dead = []
        for ws in self._connections:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


fleet = LiveFleet()
manager = ConnectionManager()


async def _broadcast_loop() -> None:
    while True:
        await asyncio.sleep(TICK_SECONDS)
        payload = fleet.tick()
        await manager.broadcast(payload)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_broadcast_loop())
    yield
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


app = FastAPI(
    title="ARGUS-NEURO",
    description="Predictive health intelligence for marine and unmanned-system power electronics.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok", "model_backed": fleet.model_backed}


@app.get("/api/fleet")
async def get_fleet() -> dict:
    return fleet.snapshot()


@app.websocket("/ws/telemetry")
async def ws_telemetry(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        await websocket.send_text(json.dumps(fleet.snapshot()))
        while True:
            # Dashboard is read-only; we just keep the connection alive
            # and ignore any client messages.
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


if DASHBOARD_DIR.exists():
    app.mount("/", StaticFiles(directory=str(DASHBOARD_DIR), html=True), name="dashboard")
