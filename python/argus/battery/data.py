"""Measured capacity history import; physical battery IDs define evaluation groups."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

from argus.battery.schema import BatteryRequest, CapacityRecord

MAX_CSV_BYTES = 2_000_000


def csv_origin(text: str) -> str:
    """Preserve an explicit synthetic marker in the downloadable example."""
    rows = list(csv.DictReader(io.StringIO(text)))
    if rows and all(row.get("data_origin") == "synthetic" for row in rows):
        return "synthetic"
    return "user_supplied"


def records_from_csv(text: str) -> list[CapacityRecord]:
    if len(text.encode()) > MAX_CSV_BYTES:
        raise ValueError("CSV exceeds 2 MB")
    reader = csv.DictReader(io.StringIO(text))
    required = {"equivalent_cycles", "capacity_ah", "condition_id"}
    if not required.issubset(reader.fieldnames or []):
        raise ValueError("CSV needs equivalent_cycles, capacity_ah, condition_id")
    records = []
    for row in reader:
        if len(records) >= 2000:
            raise ValueError("CSV exceeds 2000 records")
        if (
            None in row
            or any(value is None for value in row.values())
            or any(row.get(key) in (None, "") for key in required)
        ):
            raise ValueError("CSV row has missing or extra fields")
        records.append(
            CapacityRecord(
                equivalent_cycles=float(row["equivalent_cycles"]),
                capacity_ah=float(row["capacity_ah"]),
                condition_id=row["condition_id"],
                temperature_c=float(row["temperature_c"])
                if row.get("temperature_c")
                else None,
                timestamp=row.get("timestamp") or None,
            )
        )
    return records


def load_histories_with_meta(
    path: Path, threshold_pct: float | None = None
) -> tuple[dict[str, Any], list[BatteryRequest]]:
    """Histories plus the sampling description stored with the cache.

    A bare list (the legacy format) is reported as diagnostic adaptive sampling. A
    ``threshold_pct`` rewrites the service threshold of every history.
    """
    document = json.loads(path.read_text())
    if isinstance(document, dict) and "cells" in document:
        meta, raw = document["meta"], document["cells"]
    else:
        meta = {
            "sampling": "adaptive_stride_ceil_N_over_600",
            "stride": None,
            "diagnostic_only": True,
        }
        raw = document
    if not isinstance(raw, list) or not raw:
        raise ValueError("dataset must contain a nonempty list of battery histories")
    histories = [BatteryRequest.model_validate(item) for item in raw]
    ids = [h.profile.battery_id for h in histories]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate physical battery IDs")
    if threshold_pct is not None:
        histories = [
            h.model_copy(
                update={
                    "profile": h.profile.model_copy(
                        update={"service_threshold_pct": float(threshold_pct)}
                    )
                }
            )
            for h in histories
        ]
    return meta, histories


def load_histories(
    path: Path, threshold_pct: float | None = None
) -> list[BatteryRequest]:
    return load_histories_with_meta(path, threshold_pct)[1]


def import_nasa_mat(path: Path, reference_capacity_ah: float = 2.0) -> dict[str, Any]:
    """NASA discharge Capacity is a measured full-test Ah value, not partial throughput.

    The sequence number is a discharge-test index, NOT measured EFC. Preserve this
    distinction in the dataset and never present it as calendar age or pack data.
    """
    from scipy.io import loadmat

    raw = loadmat(path, simplify_cells=True)
    candidates = [k for k in raw if not k.startswith("_")]
    if len(candidates) != 1:
        raise ValueError("NASA file must contain one battery structure")
    battery_id = candidates[0]
    cycles = raw[battery_id]["cycle"]
    if isinstance(cycles, dict):
        cycles = [cycles]
    records = []
    temperatures = []
    for cycle in cycles:
        if cycle["type"] != "discharge":
            continue
        capacity = float(cycle["data"]["Capacity"])
        temperature = float(cycle["ambient_temperature"])
        temperatures.append(temperature)
        records.append(
            {
                "cycle_index": len(records) + 1,
                "capacity_ah": capacity,
                "temperature_c": temperature,
            }
        )
    if not records:
        raise ValueError("NASA file has no discharge capacity measurements")
    return {
        "data_origin": "laboratory",
        "profile": {
            "battery_id": battery_id,
            "application": "equipment",
            "chemistry": "li-ion",
            "measurement_scope": "cell",
            "cycle_axis": "discharge_test_index",
            "reference_capacity_ah": reference_capacity_ah,
            "reference_condition_id": "nasa-discharge-protocol-" + battery_id,
            "service_threshold_pct": 70.0,
        },
        "records": [
            {
                "equivalent_cycles": r["cycle_index"],
                "capacity_ah": r["capacity_ah"],
                "temperature_c": r["temperature_c"],
                "condition_id": "nasa-discharge-protocol-" + battery_id,
            }
            for r in records
        ],
    }
