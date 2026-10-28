"""Pinned NASA measurements in an opt-in local cache, separate from EV-pack data."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import urllib.request
import zipfile
from pathlib import Path
from typing import Any
from uuid import uuid4

from argus.battery.data import import_nasa_mat
from argus.battery.schema import BatteryRequest

LANDING_URL = "https://www.nasa.gov/intelligent-systems-division/discovery-and-systems-health/pcoe/pcoe-data-set-repository/"
SOURCE_URL = "https://phm-datasets.s3.amazonaws.com/NASA/5.+Battery+Data+Set.zip"
SOURCE_SHA256 = "82302a7db4fc1b34e0b6676326610438d43b816bdf11a69d1d012a464ef2f92e"
INNER_ARCHIVE = "5. Battery Data Set/1. BatteryAgingARC-FY08Q4.zip"
CELLS = {
    "B0005": "0eae4585baf3f200c09fe24c5ab884f1889679fc75206ca1aa19da704104f0b0",
    "B0006": "fa818ab4db5db8ab21e910b6dd6c3e20d3761bb9672089e1a4de8f96074616c5",
    "B0007": "d022afa086efaf54ab5b63f05220f5be178c8027e2fa8d68589db0e85a441a3b",
    "B0018": "d1e6c923a43ea1c9666b3a90bbb521757a067fd60b4d17dbfaa49c50b179da69",
}
DATA_DIR = Path(__file__).resolve().parents[3] / "artifacts/battery-local/public-nasa"
CITATION = 'B. Saha and K. Goebel (2007), "Battery Data Set", NASA Ames PCoE.'


def content_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, allow_nan=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def catalogue(directory: Path | None = None) -> list[dict[str, Any]]:
    directory = directory or DATA_DIR
    return [
        {
            "id": "nasa-" + cell,
            "label": "NASA · " + cell,
            "available": (directory / f"{cell}.json").is_file(),
            "measurement_scope": "cell",
            "cycle_axis": "discharge_test_index",
            "source_url": LANDING_URL,
        }
        for cell in CELLS
    ]


def load_public_history(
    dataset_id: str, observations: int = 40, directory: Path | None = None
) -> tuple[BatteryRequest, dict[str, Any]]:
    if dataset_id not in {"nasa-" + cell for cell in CELLS}:
        raise ValueError("unknown_dataset")
    if not 8 <= observations <= 2000:
        raise ValueError("invalid_observation_count")
    cell = dataset_id.removeprefix("nasa-")
    directory = directory or DATA_DIR
    document = json.loads((directory / f"{cell}.json").read_text(encoding="utf-8"))
    source = document["dataset"]
    history = BatteryRequest.model_validate(document["request"])
    if (
        source["archive_sha256"] != SOURCE_SHA256
        or source["raw_sha256"] != CELLS[cell]
        or content_hash(document["request"]) != source["history_sha256"]
        or history.profile.battery_id != cell
        or history.profile.measurement_scope != "cell"
        or history.profile.cycle_axis != "discharge_test_index"
        or history.data_origin != "laboratory"
    ):
        raise ValueError("invalid_dataset_cache")
    # Only the requested observed prefix enters the assessment, not future records.
    selected = history.model_copy(
        update={"records": history.records[:observations], "dataset_id": dataset_id}
    )
    metadata = {
        **source,
        "id": dataset_id,
        "source_url": LANDING_URL,
        "citation": CITATION,
        "observed_records": len(selected.records),
        "available_records": len(history.records),
    }
    return selected, metadata


def validate_public_request(request: BatteryRequest) -> dict[str, Any] | None:
    if request.dataset_id is None:
        return None
    expected, metadata = load_public_history(
        request.dataset_id, max(8, len(request.records))
    )
    if (
        len(request.records) < 8
        or request.records != expected.records
        or request.profile.measurement_scope != "cell"
        or request.profile.cycle_axis != "discharge_test_index"
        or request.profile.reference_capacity_ah
        != expected.profile.reference_capacity_ah
        or request.profile.reference_condition_id
        != expected.profile.reference_condition_id
        or request.data_origin != "laboratory"
    ):
        raise ValueError("public_measurements_modified")
    return metadata


def install_archive(
    archive: Path, directory: Path | None = None
) -> list[dict[str, Any]]:
    directory = directory or DATA_DIR
    with archive.open("rb") as handle:
        if hashlib.file_digest(handle, "sha256").hexdigest() != SOURCE_SHA256:
            raise ValueError("archive_checksum_mismatch")
    directory.mkdir(parents=True, exist_ok=True)
    raw_dir = directory / "raw"
    raw_dir.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive) as outer:
        with zipfile.ZipFile(io.BytesIO(outer.read(INNER_ARCHIVE))) as inner:
            for cell, expected_hash in CELLS.items():
                raw = inner.read(cell + ".mat")
                if hashlib.sha256(raw).hexdigest() != expected_hash:
                    raise ValueError("cell_checksum_mismatch")
                path = raw_dir / (cell + ".mat")
                if path.exists() and path.read_bytes() != raw:
                    raise ValueError("existing_raw_file_differs")
                if not path.exists():
                    path.write_bytes(raw)
                history = BatteryRequest.model_validate(import_nasa_mat(path))
                temperatures = {record.temperature_c for record in history.records}
                if len(temperatures) != 1:
                    raise ValueError("mixed_test_temperatures")
                payload = history.model_dump(mode="json")
                document = {
                    "request": payload,
                    "dataset": {
                        "archive_sha256": SOURCE_SHA256,
                        "raw_sha256": expected_hash,
                        "history_sha256": content_hash(payload),
                        "ambient_temperature_c": next(iter(temperatures)),
                        "license": "not_specified_in_catalogue",
                        "usage": "local_research_cache_not_redistributed",
                    },
                }
                output = directory / f"{cell}.json"
                if output.exists():
                    if json.loads(output.read_text()) != document:
                        raise ValueError("existing_dataset_differs")
                else:
                    output.write_text(json.dumps(document, indent=2), encoding="utf-8")
    return catalogue(directory)


def download_archive(path: Path) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    # The archive remains local. No user input is transmitted to the source.
    temporary = path.with_suffix(f".{uuid4().hex}.download")
    with urllib.request.urlopen(SOURCE_URL, timeout=60) as response:
        with temporary.open("xb") as handle:
            total = 0
            while chunk := response.read(1024 * 1024):
                total += len(chunk)
                if total > 250_000_000:
                    raise ValueError("archive_too_large")
                handle.write(chunk)
    with temporary.open("rb") as handle:
        if hashlib.file_digest(handle, "sha256").hexdigest() != SOURCE_SHA256:
            raise ValueError("archive_checksum_mismatch")
    temporary.rename(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--archive", type=Path, default=DATA_DIR.parent / "nasa-source.zip"
    )
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=DATA_DIR)
    args = parser.parse_args()
    if args.download:
        download_archive(args.archive)
    print(json.dumps(install_archive(args.archive, args.output_dir), indent=2))


if __name__ == "__main__":
    main()
