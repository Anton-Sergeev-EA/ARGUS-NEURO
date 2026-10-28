"""Asset-separated CPU ML/DL benchmark with explicit censoring and calibration limits."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import torch
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from argus.battery.data import load_histories
from argus.battery.models import BatteryGRU, BatteryTCN
from argus.battery.schema import BatteryRequest
from argus.training.reproducibility import package_versions, seed_training

WINDOW = 8


def threshold_event(history: BatteryRequest) -> float | None:
    p = history.profile
    for row in history.records:
        if (
            row.condition_id == p.reference_condition_id
            and row.capacity_ah / p.reference_capacity_ah * 100
            <= p.service_threshold_pct
        ):
            return row.equivalent_cycles
    return None


def samples(history: BatteryRequest) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    p = history.profile
    event = threshold_event(history)
    rows = [r for r in history.records if r.condition_id == p.reference_condition_id]
    x, y, positions = [], [], []
    if event is not None:
        for end in range(WINDOW, len(rows) + 1):
            window = rows[end - WINDOW : end]
            position = window[-1].equivalent_cycles
            if position >= event:
                break
            capacities = np.array(
                [r.capacity_ah / p.reference_capacity_ah for r in window]
            )
            axis = np.array([r.equivalent_cycles for r in window])
            temperatures = np.array(
                [
                    r.temperature_c / 50 if r.temperature_c is not None else 0
                    for r in window
                ]
            )
            present = np.array(
                [r.temperature_c is not None for r in window], dtype=float
            )
            # Inputs only include the observed prefix. No total lifetime feature.
            x.append(
                np.stack(
                    [capacities, (axis - axis[0]) / 100, temperatures, present], axis=1
                )
            )
            y.append((event - position) / 100)
            positions.append(position)
    return (
        np.array(x, dtype=np.float32).reshape(-1, WINDOW, 4),
        np.array(y, dtype=np.float32),
        np.array(positions),
    )


def asset_split(
    histories: list[BatteryRequest], seed: int
) -> dict[str, list[BatteryRequest]]:
    if len(histories) < 8:
        raise ValueError("benchmark requires at least 8 independent batteries")
    ids = [h.profile.battery_id for h in histories]
    if len(ids) != len(set(ids)):
        raise ValueError("physical battery IDs must be unique")
    order = np.random.default_rng(seed).permutation(len(histories))
    n = len(order)
    nv = max(1, n // 5)
    nc = max(1, n // 5)
    nt = max(2, n // 5)
    groups = {
        "train": order[: n - nv - nc - nt],
        "validation": order[n - nv - nc - nt : n - nc - nt],
        "calibration": order[n - nc - nt : n - nt],
        "test": order[n - nt :],
    }
    return {
        key: [histories[int(i)] for i in indices] for key, indices in groups.items()
    }


def stack_group(histories: list[BatteryRequest]) -> tuple[np.ndarray, np.ndarray]:
    sets = [samples(h) for h in histories]
    x = np.concatenate([s[0] for s in sets])
    y = np.concatenate([s[1] for s in sets])
    if len(y) < 1:
        raise ValueError(
            "a split has no observed threshold-crossing training targets; censored histories are not failures"
        )
    return x, y


def calibrate(scores: list[float], coverage: float = 0.9) -> dict[str, Any]:
    # One predeclared first eligible prefix per physical calibration battery.
    n = len(scores)
    rank = math.ceil((n + 1) * coverage)
    if not n or rank > n:
        return {
            "status": "insufficient_independent_batteries",
            "battery_count": n,
            "nominal_coverage": coverage,
            "radius_cycles": None,
        }
    radius = float(sorted(scores)[rank - 1])
    return {
        "status": "finite_sample_cell_level",
        "battery_count": n,
        "nominal_coverage": coverage,
        "radius_cycles": radius,
        "assumption": "exchangeable_cells_at_first_eligible_prefix_only",
    }


def run_benchmark(
    path: Path, output: Path, seeds: list[int], epochs: int = 60
) -> dict[str, Any]:
    if epochs < 1 or not seeds:
        raise ValueError("positive epochs and at least one seed required")
    histories = load_histories(path)
    semantics = {
        (
            h.profile.chemistry,
            h.profile.measurement_scope,
            h.profile.cycle_axis,
            h.profile.service_threshold_pct,
        )
        for h in histories
    }
    if len(semantics) != 1:
        raise ValueError(
            "benchmark must use one chemistry, measurement scope, cycle axis and threshold definition"
        )
    split = asset_split(histories, 41)
    xtrain, ytrain = stack_group(split["train"])
    xval, yval = stack_group(split["validation"])
    scaler = StandardScaler().fit(xtrain.reshape(-1, 4))

    def transform(x: np.ndarray) -> np.ndarray:
        return scaler.transform(x.reshape(-1, 4)).reshape(x.shape).astype(np.float32)

    trainx, valx = transform(xtrain), transform(xval)
    output.mkdir(parents=True, exist_ok=True)
    runs = []
    for seed in seeds:
        seed_training(seed)
        models: dict[str, Any] = {
            "median": float(np.median(ytrain)),
            "ridge": Ridge(alpha=10).fit(trainx.reshape(len(trainx), -1), ytrain),
            "gradient_boosting": HistGradientBoostingRegressor(
                max_iter=100,
                max_leaf_nodes=10,
                l2_regularization=1.0,
                random_state=seed,
            ).fit(trainx.reshape(len(trainx), -1), ytrain),
        }
        training_notes = {}
        for name, factory in [("gru", BatteryGRU), ("tcn", BatteryTCN)]:
            seed_training(seed)
            model = factory()
            optimizer = torch.optim.AdamW(
                model.parameters(), lr=0.002, weight_decay=0.001
            )
            generator = seed_training(seed)
            loader = DataLoader(
                TensorDataset(torch.from_numpy(trainx), torch.from_numpy(ytrain)),
                batch_size=64,
                shuffle=True,
                generator=generator,
            )
            best, stale, best_state = float("inf"), 0, None
            history = []
            for epoch in range(epochs):
                model.train()
                for xb, yb in loader:
                    optimizer.zero_grad()
                    loss = nn.functional.smooth_l1_loss(model(xb), yb)
                    loss.backward()
                    nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                    optimizer.step()
                model.eval()
                with torch.inference_mode():
                    mae = float(
                        torch.abs(
                            model(torch.from_numpy(valx)) - torch.from_numpy(yval)
                        ).mean()
                    )
                history.append(mae * 100)
                if mae < best - 1e-5:
                    best = mae
                    stale = 0
                    best_state = copy.deepcopy(model.state_dict())
                else:
                    stale += 1
                if stale >= 10:
                    break
            if best_state is None:
                raise RuntimeError("nonfinite validation loss")
            model.load_state_dict(best_state)
            model.eval()
            models[name] = model
            training_notes[name] = {
                "epochs_run": epoch + 1,
                "validation_mae_cycles": history,
                "best_validation_mae_cycles": best * 100,
            }
            # Local weights only. No model is deployed automatically from a benchmark.
            torch.save(best_state, output / f"{name}-seed-{seed}.pt")

        def predict(name: str, x: np.ndarray) -> np.ndarray:
            z = transform(x)
            model = models[name]
            if name == "median":
                return np.full(len(z), model * 100)
            if isinstance(model, nn.Module):
                with torch.inference_mode():
                    return model(torch.from_numpy(z)).numpy() * 100
            return np.maximum(0, model.predict(z.reshape(len(z), -1))) * 100

        # Select by macro per-battery validation MAE, before seeing test outcomes.
        def evaluate(name: str, group: list[BatteryRequest]) -> dict[str, Any]:
            metrics = []
            for h in group:
                x, y, _ = samples(h)
                if not len(y):
                    continue
                error = predict(name, x) - y * 100
                metrics.append(
                    {
                        "battery_id": h.profile.battery_id,
                        "windows": len(y),
                        "mae_cycles": float(np.abs(error).mean()),
                        "rmse_cycles": float(np.sqrt(np.mean(error**2))),
                    }
                )
            return {
                "battery_count": len(metrics),
                "per_battery": metrics,
                "macro_mae_cycles": float(np.mean([m["mae_cycles"] for m in metrics]))
                if metrics
                else None,
            }

        validations = {name: evaluate(name, split["validation"]) for name in models}
        winner = min(
            models,
            key=lambda name: (
                validations[name]["macro_mae_cycles"]
                if validations[name]["macro_mae_cycles"] is not None
                else float("inf")
            ),
        )
        scores = []
        for h in split["calibration"]:
            x, y, _ = samples(h)
            if len(y):
                scores.append(float(abs(predict(winner, x[:1])[0] - y[0] * 100)))
        calibration = calibrate(scores)
        tests = {name: evaluate(name, split["test"]) for name in models}
        covered, widths = [], []
        radius = calibration["radius_cycles"]
        if radius is not None:
            for h in split["test"]:
                x, y, _ = samples(h)
                if len(y):
                    pred = float(predict(winner, x[:1])[0])
                    target = float(y[0] * 100)
                    lower, upper = max(0, pred - radius), pred + radius
                    covered.append(lower <= target <= upper)
                    widths.append(upper - lower)
        calibration["test_first_prefix_coverage"] = (
            float(np.mean(covered)) if covered else None
        )
        calibration["test_mean_width_cycles"] = (
            float(np.mean(widths)) if widths else None
        )
        runs.append(
            {
                "seed": seed,
                "selected_by_validation": winner,
                "validation": validations,
                "test": tests,
                "calibration": calibration,
                "training": training_notes,
            }
        )
    report = {
        "schema_version": 1,
        "dataset_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "versions": package_versions(),
        "split_seed": 41,
        "window_length": WINDOW,
        "split": {k: [h.profile.battery_id for h in v] for k, v in split.items()},
        "censored_batteries": [
            h.profile.battery_id for h in histories if threshold_event(h) is None
        ],
        "target": {
            "threshold_pct": histories[0].profile.service_threshold_pct,
            "axis": histories[0].profile.cycle_axis,
            "scope": histories[0].profile.measurement_scope,
            "chemistry": histories[0].profile.chemistry,
        },
        "scaler": {
            "mean": scaler.mean_.tolist(),
            "scale": scaler.scale_.tolist(),
            "fit_partition": "train_only",
        },
        "runs": runs,
        "limitations": [
            "laboratory_cells_not_ev_packs",
            "censored_histories_excluded_from_supervised_rul_not_marked_as_failures",
            "operating_protocol_shift_not_validated",
            "intervals_only_at_first_eligible_prefix",
            "no_automatic_deployment",
            "fixed_test_set_shared_across_seeds_not_independent_replications",
        ],
    }
    (output / "report.json").write_text(json.dumps(report, indent=2, allow_nan=False))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Battery ML/DL benchmark; grouped physical assets"
    )
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=60)
    parser.add_argument("--seeds", type=int, nargs="+", default=[3, 5, 11])
    args = parser.parse_args()
    report = run_benchmark(args.dataset, args.output, args.seeds, args.epochs)
    print(
        json.dumps(
            {
                "seeds": len(report["runs"]),
                "censored": len(report["censored_batteries"]),
            }
        )
    )


if __name__ == "__main__":
    main()
