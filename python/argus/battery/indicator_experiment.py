"""Do charge-curve indicators improve remaining-life prediction beyond capacity alone?

Same cells, same eight-point windows, same asset-grouped splits and the same model
(gradient boosting); only the input channels differ. Several split seeds show how
much of a difference is just a lucky split.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.preprocessing import StandardScaler

from argus.battery import hust_curves
from argus.battery.data import load_histories
from argus.battery.schema import BatteryRequest
from argus.battery.training import WINDOW, asset_split, threshold_event

SPLIT_SEEDS = (41, 42, 43, 44, 45)
FEATURE_SETS = {
    "capacity_only": (),
    "plus_rise_time": ("rise_time_s",),
    "plus_ica": ("ica_peak_v", "ica_peak_height", "ica_peak_width_v"),
    "plus_all_indicators": hust_curves.INDICATORS,
}


def windows(
    history: BatteryRequest,
    indicators: dict[int, dict[str, float]],
    names: tuple[str, ...],
) -> tuple[np.ndarray, np.ndarray]:
    """Windows ending before the threshold event; indicator names add channels."""
    p = history.profile
    event = threshold_event(history)
    rows = [r for r in history.records if r.condition_id == p.reference_condition_id]
    x, y = [], []
    if event is None:
        return np.empty((0, WINDOW * (2 + len(names)))), np.empty(0)
    for end in range(WINDOW, len(rows) + 1):
        window = rows[end - WINDOW : end]
        if window[-1].equivalent_cycles >= event:
            break
        extra = [indicators.get(int(r.equivalent_cycles)) for r in window]
        if names and any(e is None for e in extra):
            continue
        axis = np.array([r.equivalent_cycles for r in window])
        channels = [
            np.array([r.capacity_ah / p.reference_capacity_ah for r in window]),
            (axis - axis[0]) / 100,
        ]
        channels += [np.array([e[n] for e in extra]) for n in names]  # type: ignore[index]
        x.append(np.stack(channels, axis=1).reshape(-1))
        y.append((event - window[-1].equivalent_cycles))
    return np.array(x, dtype=float), np.array(y, dtype=float)


def evaluate(
    histories: list[BatteryRequest],
    series: dict[str, dict[int, dict[str, float]]],
    names: tuple[str, ...],
    seed: int,
) -> float:
    split = asset_split(histories, seed)

    def stack(group: list[BatteryRequest]) -> tuple[np.ndarray, np.ndarray]:
        parts = [windows(h, series.get(h.profile.battery_id, {}), names) for h in group]
        return np.concatenate([p[0] for p in parts]), np.concatenate(
            [p[1] for p in parts]
        )

    x, y = stack(split["train"] + split["validation"])
    scaler = StandardScaler().fit(x)
    model = HistGradientBoostingRegressor(
        max_iter=100, max_leaf_nodes=10, l2_regularization=1.0, random_state=3
    ).fit(scaler.transform(x), y)
    maes = []
    for h in split["test"]:
        hx, hy = windows(h, series.get(h.profile.battery_id, {}), names)
        if len(hy):
            maes.append(
                float(
                    np.abs(
                        np.maximum(0, model.predict(scaler.transform(hx))) - hy
                    ).mean()
                )
            )
    return float(np.mean(maes))


def run(dataset: Path, indicators: Path = hust_curves.OUTPUT) -> dict[str, Any]:
    histories = load_histories(dataset)
    series = hust_curves.load(indicators)
    result: dict[str, Any] = {
        "cells": len(histories),
        "split_seeds": list(SPLIT_SEEDS),
        "sets": {},
    }
    for label, names in FEATURE_SETS.items():
        scores = [evaluate(histories, series, names, seed) for seed in SPLIT_SEEDS]
        result["sets"][label] = {
            "channels": ["capacity", "cycle_offset", *names],
            "test_macro_mae_cycles_per_split": [round(s, 2) for s in scores],
            "mean": round(float(np.mean(scores)), 2),
            "std": round(float(np.std(scores)), 2),
        }
    base = result["sets"]["capacity_only"]["test_macro_mae_cycles_per_split"]
    for label, entry in result["sets"].items():
        entry["better_than_capacity_only_in_splits"] = sum(
            a < b for a, b in zip(entry["test_macro_mae_cycles_per_split"], base)
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--indicators", type=Path, default=hust_curves.OUTPUT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run(args.dataset, args.indicators)
    text = json.dumps(result, indent=1)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
