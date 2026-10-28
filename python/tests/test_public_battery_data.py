from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from argus.battery import public_data
from argus.battery.api import router
from argus.battery.schema import BatteryRequest


@pytest.fixture
def local_catalogue(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Artificial cache fixture for offline API tests; not a redistributed dataset."""
    request = BatteryRequest.model_validate(
        {
            "data_origin": "laboratory",
            "profile": {
                "battery_id": "B0005",
                "measurement_scope": "cell",
                "cycle_axis": "discharge_test_index",
                "reference_capacity_ah": 2.0,
                "reference_condition_id": "test-fixture",
                "service_threshold_pct": 70,
            },
            "records": [
                {
                    "equivalent_cycles": i + 1,
                    "capacity_ah": 2 - i * 0.01,
                    "condition_id": "test-fixture",
                }
                for i in range(100)
            ],
        }
    )
    payload = request.model_dump(mode="json")
    document = {
        "request": payload,
        "dataset": {
            "archive_sha256": public_data.SOURCE_SHA256,
            "raw_sha256": public_data.CELLS["B0005"],
            "history_sha256": public_data.content_hash(payload),
            "license": "not_specified_in_catalogue",
        },
    }
    (tmp_path / "B0005.json").write_text(json.dumps(document))
    monkeypatch.setattr(public_data, "DATA_DIR", tmp_path)
    return tmp_path


def test_catalogue_and_observed_prefix(local_catalogue: Path) -> None:
    items = public_data.catalogue()
    assert len(items) == 4
    assert items[0]["available"]
    assert not items[1]["available"]
    model, source = public_data.load_public_history("nasa-B0005", 20)
    assert len(model.records) == 20
    assert model.records[-1].equivalent_cycles == 20
    assert model.data_origin == "laboratory"
    assert model.profile.measurement_scope == "cell"
    assert model.profile.equivalent_cycles_per_month is None
    assert source["available_records"] == 100
    assert source["observed_records"] == 20


def test_public_source_cannot_be_retained_after_editing_measurements(
    local_catalogue: Path,
) -> None:
    model, _ = public_data.load_public_history("nasa-B0005", 20)
    assert public_data.validate_public_request(model) is not None
    model.records[-1].capacity_ah += 0.1
    with pytest.raises(ValueError, match="modified"):
        public_data.validate_public_request(model)


def test_changed_cache_and_wrong_archive_are_rejected(local_catalogue: Path) -> None:
    path = local_catalogue / "B0005.json"
    document = json.loads(path.read_text())
    document["request"]["records"][0]["capacity_ah"] = 9
    path.write_text(json.dumps(document))
    with pytest.raises(ValueError, match="cache"):
        public_data.load_public_history("nasa-B0005")
    archive = local_catalogue / "wrong.zip"
    archive.write_bytes(b"not the NASA archive")
    with pytest.raises(ValueError, match="checksum"):
        public_data.install_archive(archive, local_catalogue / "output")
    assert not (local_catalogue / "output").exists()


@pytest.mark.parametrize(
    "dataset_id", ["../../private", "nasa-B9999", "https://other.example/data"]
)
def test_dataset_ids_cannot_select_arbitrary_files_or_urls(dataset_id: str) -> None:
    with pytest.raises(ValueError, match="unknown_dataset"):
        public_data.load_public_history(dataset_id)


def test_http_catalogue_load_and_verified_report(local_catalogue: Path) -> None:
    app = FastAPI()
    app.include_router(router)

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            assert len((await client.get("/api/battery/datasets")).json()) == 4
            loaded = await client.get(
                "/api/battery/datasets/nasa-B0005?observations=20"
            )
            assert loaded.status_code == 200
            payload = loaded.json()["request"]
            report = (await client.post("/api/battery/analyze", json=payload)).json()
            assert report["source"] == "laboratory"
            assert report["dataset"]["observed_records"] == 20
            assert report["rul"]["months"] is None
            payload["records"][0]["capacity_ah"] = 1.0
            assert (
                await client.post("/api/battery/analyze", json=payload)
            ).status_code == 422
            assert (
                await client.get("/api/battery/datasets/nasa-B0005?observations=1")
            ).status_code == 422
            assert (
                await client.get("/api/battery/datasets/nasa-B0006")
            ).status_code == 503

    asyncio.run(scenario())
