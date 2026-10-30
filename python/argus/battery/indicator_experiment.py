"""Do charge-curve indicators improve remaining-life prediction beyond capacity alone?

Same cells, same eight-point windows, same asset-grouped splits and the same model
(gradient boosting); only the input channels differ. Windows come from one shared
constructor with a common requirement (every indicator present), so every feature
set is scored on identical windows. Sampling is a fixed physical stride read from the
cache metadata; a cache thinned with a length-dependent stride is refused unless the
diagnostic flag is given.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.preprocessing import StandardScaler

from argus.battery import hust, hust_curves
from argus.battery.data import load_histories_with_meta
from argus.battery.schema import BatteryRequest
from argus.battery.training import asset_split
from argus.battery.windows import CellWindows, cell_windows, stack, window_report

SPLIT_SEEDS = (41, 42, 43, 44, 45)
FEATURE_SETS = {
    "capacity_only": (),
    "plus_rise_time": ("rise_time_s",),
    "plus_ica": ("ica_peak_v", "ica_peak_height", "ica_peak_width_v"),
    "plus_all_indicators": hust_curves.INDICATORS,
}
REQUIRED = hust_curves.INDICATORS


def fit_model(
    train: list[CellWindows], channels: tuple[str, ...]
) -> tuple[StandardScaler, HistGradientBoostingRegressor]:
    """Scaler and model are fitted on the training cells only."""
    x, y, _ = stack(train, channels, with_offset=False)
    scaler = StandardScaler().fit(x)
    model = HistGradientBoostingRegressor(
        max_iter=100, max_leaf_nodes=10, l2_regularization=1.0, random_state=3
    ).fit(scaler.transform(x), y)
    return scaler, model


def evaluate(
    cells: dict[str, CellWindows],
    split: dict[str, list[BatteryRequest]],
    channels: tuple[str, ...],
) -> float:
    pick = lambda group: [cells[h.profile.battery_id] for h in group]  # noqa: E731
    scaler, model = fit_model(pick(split["train"] + split["validation"]), channels)
    maes = []
    for cell in pick(split["test"]):
        if not len(cell):
            continue
        x, y, _ = stack([cell], channels, with_offset=False)
        maes.append(
            float(np.abs(np.maximum(0, model.predict(scaler.transform(x))) - y).mean())
        )
    return float(np.mean(maes))


def run(
    cells_path: Path = hust.OUTPUT,
    indicators_path: Path = hust_curves.OUTPUT,
    threshold_pct: float = 90.0,
    allow_diagnostic: bool = False,
) -> dict[str, Any]:
    meta, histories = load_histories_with_meta(cells_path, threshold_pct)
    if meta.get("diagnostic_only") and not allow_diagnostic:
        raise ValueError(
            "cache uses a length-dependent stride; pass allow_diagnostic to use it"
        )
    indicator_meta, series = hust_curves.load_with_meta(indicators_path)
    if meta.get("stride") != indicator_meta.get("stride") or meta.get(
        "sampling"
    ) != indicator_meta.get("sampling"):
        raise ValueError("capacity and indicator caches were thinned differently")
    cells = {
        h.profile.battery_id: cell_windows(
            h, series.get(h.profile.battery_id, {}), REQUIRED
        )
        for h in histories
    }
    result: dict[str, Any] = {
        "sampling": {k: meta.get(k) for k in ("sampling", "stride", "diagnostic_only")},
        "threshold_pct": threshold_pct,
        "common_windows": window_report(list(cells.values())),
        "split_seeds": list(SPLIT_SEEDS),
        "sets": {},
    }
    splits = {seed: asset_split(histories, seed) for seed in SPLIT_SEEDS}
    for label, channels in FEATURE_SETS.items():
        scores = [evaluate(cells, splits[seed], channels) for seed in SPLIT_SEEDS]
        result["sets"][label] = {
            "channels": ["capacity", *channels],
            "test_macro_mae_cycles_per_split": [round(s, 2) for s in scores],
            "mean": round(float(np.mean(scores)), 2),
            "std": round(float(np.std(scores)), 2),
        }
    base = result["sets"]["capacity_only"]["test_macro_mae_cycles_per_split"]
    for entry in result["sets"].values():
        entry["better_than_capacity_only_in_splits"] = sum(
            a < b for a, b in zip(entry["test_macro_mae_cycles_per_split"], base)
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cells", type=Path, default=hust.OUTPUT)
    parser.add_argument("--indicators", type=Path, default=hust_curves.OUTPUT)
    parser.add_argument("--threshold", type=float, default=90.0)
    parser.add_argument("--allow-diagnostic", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run(args.cells, args.indicators, args.threshold, args.allow_diagnostic)
    text = json.dumps(result, indent=1)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
