"""Authenticated entry for equipment samples collected outside the simulator.

Disabled until ``ARGUS_INGEST_TOKEN`` is set. A full assessment also needs a vibration
waveform; without one the response reports the buffer state only.
"""

from __future__ import annotations

import hmac
import os
import re
import threading
from dataclasses import asdict
from typing import Annotated, Any

import numpy as np
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from argus.battery.ratelimit import limit_requests
from argus.inference.engine import HealthInferenceEngine
from argus.simulator.telemetry_simulator import SENSOR_COLUMNS, AssetType

router = APIRouter(prefix="/api/ingest", tags=["Ingest"])
ASSET_ID = re.compile(r"^[\w.-]{1,64}$")
Number = Annotated[float, Field(allow_inf_nan=False)]


class SampleIn(BaseModel):
    t_s: Number
    voltage_v: Number
    current_a: Number
    temperature_c: Number
    vibration_g: Number
    frequency_hz: Number
    load_factor: Number


class WaveformIn(BaseModel):
    sample_rate_hz: float = Field(gt=0, le=1_000_000, allow_inf_nan=False)
    values: list[Number] = Field(min_length=2, max_length=65_536)


class EquipmentIn(BaseModel):
    asset_id: str = Field(pattern=ASSET_ID.pattern)
    asset_type: AssetType
    samples: list[SampleIn] = Field(min_length=1, max_length=600)
    waveform: WaveformIn | None = None


class IngestService:
    """One engine for external assets; a lock serializes its buffers."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._engine: HealthInferenceEngine | None = None

    def process(self, body: EquipmentIn) -> dict[str, Any]:
        with self._lock:
            if self._engine is None:
                self._engine = HealthInferenceEngine(source="ingest")
            engine = self._engine
            for sample in body.samples:
                row = {c: getattr(sample, c) for c in SENSOR_COLUMNS}
                engine.push_sample(body.asset_id, row, sample_time_s=sample.t_s)
            result: dict[str, Any] = {
                "asset_id": body.asset_id,
                "samples_accepted": len(body.samples),
                "ready": engine.ready(body.asset_id),
                "data_quality": engine.data_quality(body.asset_id),
                "assessment": None,
            }
            if body.waveform is None:
                result["reason"] = "waveform_required_for_assessment"
            else:
                assessment = engine.assess(
                    body.asset_id,
                    body.asset_type.value,
                    np.asarray(body.waveform.values, dtype=float),
                    body.waveform.sample_rate_hz,
                )
                result["assessment"] = asdict(assessment)
            return result


_SERVICE = IngestService()


def get_service() -> IngestService:
    return _SERVICE


def require_token(authorization: str | None = Header(default=None)) -> None:
    token = os.environ.get("ARGUS_INGEST_TOKEN", "")
    if not token:
        raise HTTPException(503, detail="ingest_disabled")
    given = (authorization or "").removeprefix("Bearer ")
    if not authorization or not hmac.compare_digest(given.encode(), token.encode()):
        raise HTTPException(401, detail="unauthorized")


@router.post(
    "/equipment", dependencies=[Depends(require_token), Depends(limit_requests)]
)
def ingest_equipment(
    body: EquipmentIn, service: IngestService = Depends(get_service)
) -> dict[str, Any]:
    return service.process(body)
