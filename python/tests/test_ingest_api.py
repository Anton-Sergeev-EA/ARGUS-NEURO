"""The authenticated entry for externally collected equipment samples."""

from __future__ import annotations

import math
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from argus.ingest import api

TOKEN = "unit-test-token"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("ARGUS_INGEST_TOKEN", TOKEN)
    app = FastAPI()
    app.include_router(api.router)
    service = api.IngestService()
    app.dependency_overrides[api.get_service] = lambda: service
    return TestClient(app)


def sample(t: float) -> dict[str, float]:
    return {
        "t_s": t,
        "voltage_v": 400.0,
        "current_a": 32.0,
        "temperature_c": 35.0,
        "vibration_g": 0.02,
        "frequency_hz": 50.0,
        "load_factor": 0.5,
    }


def body(times: list[float], **extra: Any) -> dict[str, Any]:
    return {
        "asset_id": "charger-1",
        "asset_type": "EV_CHARGER",
        "samples": [sample(t) for t in times],
        **extra,
    }


def test_ingest_is_off_until_a_token_is_configured(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ARGUS_INGEST_TOKEN")
    r = client.post("/api/ingest/equipment", json=body([0.0]), headers=HEADERS)
    assert (r.status_code, r.json()["detail"]) == (503, "ingest_disabled")


def test_missing_or_wrong_token_is_refused(client: TestClient) -> None:
    payload = body([0.0])
    assert client.post("/api/ingest/equipment", json=payload).status_code == 401
    bad = {"Authorization": "Bearer nope"}
    assert (
        client.post("/api/ingest/equipment", json=payload, headers=bad).status_code
        == 401
    )
    assert (
        client.post("/api/ingest/equipment", json=payload, headers=HEADERS).status_code
        == 200
    )


def test_a_full_window_makes_the_buffer_ready_but_needs_a_waveform(
    client: TestClient,
) -> None:
    r = client.post(
        "/api/ingest/equipment",
        json=body([5.0 * i for i in range(30)]),
        headers=HEADERS,
    )
    out = r.json()
    assert r.status_code == 200
    assert out["samples_accepted"] == 30 and out["ready"] is True
    assert out["assessment"] is None
    assert out["reason"] == "waveform_required_for_assessment"
    assert out["data_quality"]["issues"] == []


def test_a_gap_resets_the_buffer_and_is_reported(client: TestClient) -> None:
    r = client.post("/api/ingest/equipment", json=body([0.0, 60.0]), headers=HEADERS)
    out = r.json()
    assert out["ready"] is False
    assert out["data_quality"]["issues"] == ["sampling_gap"]


def test_waveform_returns_an_assessment_record(client: TestClient) -> None:
    wave = [math.sin(2 * math.pi * 100 * i / 10_000) for i in range(2048)]
    payload = body(
        [5.0 * i for i in range(30)],
        waveform={"sample_rate_hz": 10_000, "values": wave},
    )
    out = client.post("/api/ingest/equipment", json=payload, headers=HEADERS).json()
    assert out["assessment"]["asset_id"] == "charger-1"
    assert out["assessment"]["status"]
    assert out["assessment"]["data_quality"]["samples_required"] == 24


def test_malformed_bodies_are_rejected(client: TestClient) -> None:
    broken = body([0.0])
    del broken["samples"][0]["vibration_g"]
    assert (
        client.post("/api/ingest/equipment", json=broken, headers=HEADERS).status_code
        == 422
    )
    odd = body([0.0])
    odd["asset_id"] = "../etc"
    assert (
        client.post("/api/ingest/equipment", json=odd, headers=HEADERS).status_code
        == 422
    )
    odd = body([0.0])
    odd["samples"][0]["voltage_v"] = "NaN"
    assert (
        client.post("/api/ingest/equipment", json=odd, headers=HEADERS).status_code
        == 422
    )
    empty = body([])
    assert (
        client.post("/api/ingest/equipment", json=empty, headers=HEADERS).status_code
        == 422
    )
