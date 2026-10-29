"""Learned second opinion on remaining life, only inside its validated domain.

The explainable calibrated estimate stays the reported result. This model is an
extra, clearly labelled number that is produced only when the request looks like
the cells it was trained on: same chemistry, measurement scope, cycle axis,
service threshold and sampling spacing. Anything else gets ``out_of_domain`` instead
of an extrapolated guess. Weights are trained locally and never committed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.preprocessing import StandardScaler

from argus.battery.data import load_histories
from argus.battery.schema import BatteryRequest
from argus.battery.training import WINDOW, asset_split, calibrate, samples, stack_group

DEFAULT_DIR = (
    Path(__file__).resolve().parents[3] / "artifacts/battery-local/second-opinion"
)
MODEL_FILE = "model.joblib"
META_FILE = "metadata.json"
SEED = 3


def last_window(history: BatteryRequest) -> tuple[np.ndarray, float] | None:
    """Newest ``WINDOW`` comparable records as model input plus their median spacing."""
    p = history.profile
    rows = [r for r in history.records if r.condition_id == p.reference_condition_id]
    if len(rows) < WINDOW:
        return None
    window = rows[-WINDOW:]
    capacities = np.array([r.capacity_ah / p.reference_capacity_ah for r in window])
    axis = np.array([r.equivalent_cycles for r in window])
    temperatures = np.array(
        [r.temperature_c / 50 if r.temperature_c is not None else 0 for r in window]
    )
    present = np.array([r.temperature_c is not None for r in window], dtype=float)
    x = np.stack([capacities, (axis - axis[0]) / 100, temperatures, present], axis=1)
    return x.astype(np.float32), float(np.median(np.diff(axis)))


def spacing_of(histories: list[BatteryRequest]) -> tuple[float, float]:
    found = []
    for h in histories:
        window = last_window(h)
        if window is not None:
            found.append(window[1])
    return float(min(found)), float(max(found))


def train(dataset: Path, output: Path = DEFAULT_DIR) -> dict[str, Any]:
    histories = load_histories(dataset)
    first = histories[0].profile
    split = asset_split(histories, 41)
    x, y = stack_group(split["train"] + split["validation"])
    scaler = StandardScaler().fit(x.reshape(-1, 4))
    model = HistGradientBoostingRegressor(
        max_iter=100, max_leaf_nodes=10, l2_regularization=1.0, random_state=SEED
    ).fit(scaler.transform(x.reshape(-1, 4)).reshape(len(x), -1), y)

    def predict(windows: np.ndarray) -> np.ndarray:
        flat = scaler.transform(windows.reshape(-1, 4)).reshape(len(windows), -1)
        return np.maximum(0, model.predict(flat)) * 100

    scores = []
    for h in split["calibration"]:
        wx, wy, _ = samples(h)
        if len(wy):
            scores.append(float(abs(predict(wx[:1])[0] - wy[0] * 100)))
    interval = calibrate(scores)
    maes = []
    for h in split["test"]:
        wx, wy, _ = samples(h)
        if len(wy):
            maes.append(float(np.abs(predict(wx) - wy * 100).mean()))
    output.mkdir(parents=True, exist_ok=True)
    joblib.dump({"scaler": scaler, "model": model}, output / MODEL_FILE)
    low, high = spacing_of(split["train"] + split["validation"])
    meta = {
        "domain": {
            "chemistry": first.chemistry,
            "measurement_scope": first.measurement_scope,
            "cycle_axis": first.cycle_axis,
            "service_threshold_pct": first.service_threshold_pct,
            "window_spacing_cycles": [low, high],
        },
        "model_sha256": hashlib.sha256((output / MODEL_FILE).read_bytes()).hexdigest(),
        "dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(),
        "cells": {k: len(v) for k, v in split.items()},
        "test_macro_mae_cycles": float(np.mean(maes)),
        "interval": interval,
        "limitations": [
            "laboratory_cells_of_one_chemistry_and_protocol",
            "interval_from_first_eligible_prefix_of_calibration_cells",
            "research_result_not_a_guarantee",
        ],
    }
    (output / META_FILE).write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def _load(directory: Path) -> tuple[dict[str, Any], Any] | None:
    meta_path, model_path = directory / META_FILE, directory / MODEL_FILE
    if not (meta_path.exists() and model_path.exists()):
        return None
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if hashlib.sha256(model_path.read_bytes()).hexdigest() != meta["model_sha256"]:
        raise ValueError("second_opinion_model_checksum_mismatch")
    return meta, joblib.load(model_path)


def second_opinion(
    history: BatteryRequest, directory: Path = DEFAULT_DIR
) -> dict[str, Any]:
    """Estimate or an explicit refusal; never raises for unusual input."""
    try:
        bundle = _load(directory)
    except ValueError:
        return {"status": "model_integrity_error"}
    if bundle is None:
        return {"status": "not_installed"}
    meta, parts = bundle
    p, domain = history.profile, meta["domain"]
    window = last_window(history)
    in_domain = (
        window is not None
        and p.chemistry == domain["chemistry"]
        and p.measurement_scope == domain["measurement_scope"]
        and p.cycle_axis == domain["cycle_axis"]
        and p.service_threshold_pct == domain["service_threshold_pct"]
        and domain["window_spacing_cycles"][0]
        <= window[1]
        <= domain["window_spacing_cycles"][1]
    )
    if not in_domain or window is None:
        return {"status": "out_of_domain", "trained_for": domain}
    x = parts["scaler"].transform(window[0]).reshape(1, -1)
    estimate = float(max(0.0, parts["model"].predict(x)[0]) * 100)
    radius = meta["interval"].get("radius_cycles")
    result: dict[str, Any] = {
        "status": "ok",
        "equivalent_cycles": round(estimate, 1),
        "method": "gradient_boosting_on_last_8_capacity_points",
        "test_macro_mae_cycles": round(meta["test_macro_mae_cycles"], 1),
        "trained_for": domain,
    }
    if radius is not None:
        result["interval_cycles"] = [
            round(max(0.0, estimate - radius), 1),
            round(estimate + radius, 1),
        ]
        result["interval_note"] = "finite_sample_cell_level_first_prefix"
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_DIR)
    args = parser.parse_args()
    meta = train(args.dataset, args.output)
    print(
        json.dumps(
            {k: meta[k] for k in ("cells", "test_macro_mae_cycles", "interval")},
            indent=1,
        )
    )


if __name__ == "__main__":
    main()
