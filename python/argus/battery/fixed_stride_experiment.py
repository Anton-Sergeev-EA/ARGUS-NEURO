"""Remaining-life experiment on HUST with sampling that ignores the future length.

The earlier pipeline thins every history with ``stride = ceil(length / 600)``, so the
spacing of a window reveals how long the cell lives. Here every cell is sampled at one
fixed physical stride, physical cycle IDs come from the raw keys, all models see the
same windows, and the adaptive-stride arms are kept only as diagnostic controls. The
protocol is declared in ``experiments/2026-10-30_fixed_stride_hust/preregistration.json``.
"""

from __future__ import annotations

import argparse
import io
import json
import pickle
import time
import zipfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, ConstantKernel, WhiteKernel
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

from argus.battery.hust import ARCHIVE, ROOT, DataOnlyUnpickler
from argus.battery.hust_curves import INDICATORS, cycle_indicators

STRIDE = 5
WINDOW = 8
THRESHOLD_PCT = 90.0
FOLDS = 5
FOLD_SEED = 41
CAL_CELLS = 12
VAL_CELLS = 12
GPR_TRAIN_WINDOWS = 800
COVERAGE = 0.9
REL_FLOOR = 50.0
AGE_LIMIT = 300.0
MISSING_SHARE = 0.3
BOOTSTRAPS = 2000
CACHE = ROOT / "hust/fixed_stride.json"
ADAPTIVE_CELLS = ROOT / "hust/cells.json"
ADAPTIVE_INDICATORS = ROOT / "hust/indicators.json"

Cell = dict[str, Any]


def build_cell(raw: bytes) -> tuple[str, Cell]:
    """Capacity and charge indicators at the fixed stride, keyed by physical cycle."""
    document = DataOnlyUnpickler(io.BytesIO(raw)).load()
    ((name, cell),) = document.items()
    keys = sorted(cell["dq"])
    cycles = keys[::STRIDE]
    capacity = [float(cell["dq"][k]) / 1000.0 for k in cycles]
    reference = float(np.median([float(cell["dq"][k]) / 1000.0 for k in keys[:3]]))
    series: dict[str, list[float | None]] = {n: [] for n in INDICATORS}
    for key in cycles:
        values = cycle_indicators(cell["data"][key])
        for n in INDICATORS:
            series[n].append(None if values is None else values[n])
    return str(name), {
        "cycles": [int(k) for k in cycles],
        "capacity_ah": capacity,
        "reference_ah": reference,
        "total_cycles": len(keys),
        "indicators": series,
    }


def build_cache(archive: Path = ARCHIVE, output: Path = CACHE, workers: int = 8) -> int:
    with zipfile.ZipFile(archive) as bundle:
        members = sorted(n for n in bundle.namelist() if n.endswith(".pkl"))
        blobs = [bundle.read(m) for m in members]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        built = dict(pool.map(build_cell, blobs))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(built) + "\n", encoding="utf-8")
    return len(built)


def event_index(capacity: np.ndarray, reference: float) -> int | None:
    below = np.nonzero(capacity / reference * 100.0 <= THRESHOLD_PCT)[0]
    return int(below[0]) if len(below) else None


def windows(
    cycles: np.ndarray,
    capacity: np.ndarray,
    reference: float,
    indicators: np.ndarray | None,
) -> dict[str, np.ndarray]:
    """Windows ending before the threshold event; target = cycles until the event."""
    event = event_index(capacity, reference)
    if event is None:
        return {}
    rows: dict[str, list[Any]] = {"cap": [], "off": [], "ind": [], "y": [], "pos": []}
    for end in range(WINDOW, event + 1):
        sl = slice(end - WINDOW, end)
        position = float(cycles[end - 1])
        if position >= cycles[event]:
            break
        rows["cap"].append(capacity[sl] / reference)
        rows["off"].append((cycles[sl] - cycles[sl][0]) / 100.0)
        rows["ind"].append(
            indicators[sl] if indicators is not None else np.zeros((WINDOW, 0))
        )
        rows["y"].append(float(cycles[event]) - position)
        rows["pos"].append(position)
    if not rows["y"]:
        return {}
    return {k: np.array(v, dtype=float) for k, v in rows.items()}


def load_arms(cache: Path = CACHE) -> dict[str, dict[str, dict[str, np.ndarray]]]:
    """Per arm and cell: windows with capacity, offset, indicators, target, position."""
    fixed = json.loads(cache.read_text())
    arms: dict[str, dict[str, dict[str, np.ndarray]]] = {"fixed": {}, "adaptive": {}}
    for name, cell in fixed.items():
        stack = np.array(
            [
                [np.nan if v is None else v for v in cell["indicators"][n]]
                for n in INDICATORS
            ]
        ).T
        w = windows(
            np.array(cell["cycles"], dtype=float),
            np.array(cell["capacity_ah"]),
            cell["reference_ah"],
            stack,
        )
        if w:
            arms["fixed"][name] = w
    histories = json.loads(ADAPTIVE_CELLS.read_text())
    indicators = json.loads(ADAPTIVE_INDICATORS.read_text())
    for history in histories:
        battery = history["profile"]["battery_id"]
        records = history["records"]
        cycles = np.array([r["equivalent_cycles"] for r in records], dtype=float)
        capacity = np.array([r["capacity_ah"] for r in records])
        found = indicators.get(battery, {})
        stack = np.array(
            [
                [found.get(str(int(c)), {}).get(n, np.nan) for n in INDICATORS]
                for c in cycles
            ]
        )
        w = windows(
            cycles,
            capacity,
            history["profile"]["reference_capacity_ah"],
            stack,
        )
        if w:
            arms["adaptive"][battery.removeprefix("HUST-")] = w
    return arms


def make_folds(names: list[str]) -> list[dict[str, list[str]]]:
    order = list(np.random.default_rng(FOLD_SEED).permutation(sorted(names)))
    parts = np.array_split(np.arange(len(order)), FOLDS)
    folds = []
    for part in parts:
        test = [order[i] for i in part]
        rest = [n for n in order if n not in set(test)]
        folds.append(
            {
                "test": test,
                "calibration": rest[:CAL_CELLS],
                "validation": rest[CAL_CELLS : CAL_CELLS + VAL_CELLS],
                "train": rest[CAL_CELLS + VAL_CELLS :],
            }
        )
    return folds


def stack_cells(
    arm: dict[str, dict[str, np.ndarray]], names: list[str]
) -> dict[str, np.ndarray]:
    parts = [arm[n] for n in names if n in arm]
    out = {k: np.concatenate([p[k] for p in parts]) for k in parts[0]}
    out["cell"] = np.concatenate([[n] * len(arm[n]["y"]) for n in names if n in arm])
    return out


FEATURES = (
    "capacity",
    "capacity_offset",
    "indicators",
    "span_only",
    "capacity_indicators",
)


def features(w: dict[str, np.ndarray], kind: str) -> np.ndarray:
    n = len(w["y"])
    if kind == "capacity":
        return w["cap"]
    if kind == "capacity_offset":
        return np.concatenate([w["cap"], w["off"]], axis=1)
    if kind == "span_only":
        return w["off"][:, -1:]
    if kind == "capacity_indicators":
        return np.concatenate([w["cap"], w["off"], w["ind"].reshape(n, -1)], axis=1)
    raise ValueError(kind)


def linear_prediction(w: dict[str, np.ndarray]) -> np.ndarray:
    out = np.empty(len(w["y"]))
    for k in range(len(out)):
        soh = w["cap"][k] * 100
        axis = w["off"][k] * 100
        slope = np.polyfit(axis, soh, 1)[0]
        out[k] = (
            np.clip((soh[-1] - THRESHOLD_PCT) / -slope, 0, 1000.0)
            if slope < -1e-6
            else 1000.0
        )
    return out


def gb() -> HistGradientBoostingRegressor:
    return HistGradientBoostingRegressor(
        max_iter=100, max_leaf_nodes=10, l2_regularization=1.0, random_state=3
    )


def fit_models(
    train: dict[str, np.ndarray],
    validation: dict[str, np.ndarray],
    kind: str,
    ind: bool,
) -> dict[str, Any]:
    """Models for one feature kind; the indicator model only when ``ind`` is set."""
    x = features(train, kind)
    models: dict[str, Any] = {}
    scaler = StandardScaler().fit(np.nan_to_num(x))
    models["scaler"] = scaler
    models["median"] = float(np.median(train["y"]))
    if not ind:
        models["ridge"] = Ridge(alpha=10).fit(
            scaler.transform(np.nan_to_num(x)), train["y"]
        )
        models["gb"] = gb().fit(x, train["y"])
        sample = np.random.default_rng(3).choice(
            len(x), size=min(GPR_TRAIN_WINDOWS, len(x)), replace=False
        )
        kernel = ConstantKernel(1.0) * RBF(
            length_scale=np.ones(x.shape[1])
        ) + WhiteKernel(0.1)
        models["gpr"] = GaussianProcessRegressor(
            kernel=kernel, normalize_y=True, random_state=3
        ).fit(scaler.transform(x[sample]), train["y"][sample])
        models["gru"] = _fit_gru(train, validation)
    else:
        models["gb"] = gb().fit(x, train["y"])
    return models


def _fit_gru(train: dict[str, np.ndarray], validation: dict[str, np.ndarray]) -> Any:
    import copy

    import torch
    from torch import nn

    from argus.battery.models import BatteryGRU
    from argus.training.reproducibility import seed_training

    def seq(w: dict[str, np.ndarray]) -> np.ndarray:
        return np.stack([w["cap"], w["off"]], axis=2).astype(np.float32)

    xtr, xva = seq(train), seq(validation)
    mean, scale = xtr.reshape(-1, 2).mean(0), xtr.reshape(-1, 2).std(0) + 1e-6
    ytr = (train["y"] / 100).astype(np.float32)
    yva = (validation["y"] / 100).astype(np.float32)
    generator = seed_training(3)
    model = BatteryGRU(n_features=2)
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.002, weight_decay=0.001)
    xt = torch.from_numpy((xtr - mean) / scale)
    xv = torch.from_numpy((xva - mean) / scale)
    yt = torch.from_numpy(ytr)
    best, stale, state = float("inf"), 0, None
    for _ in range(40):
        model.train()
        order = torch.randperm(len(xt), generator=generator)
        for start in range(0, len(order), 64):
            idx = order[start : start + 64]
            optimizer.zero_grad()
            nn.functional.smooth_l1_loss(model(xt[idx]), yt[idx]).backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
        model.eval()
        with torch.inference_mode():
            mae = float(torch.abs(model(xv) - torch.from_numpy(yva)).mean())
        if mae < best - 1e-5:
            best, stale, state = mae, 0, copy.deepcopy(model.state_dict())
        else:
            stale += 1
        if stale >= 10:
            break
    if state is None:
        raise RuntimeError("nonfinite validation loss")
    model.load_state_dict(state)
    model.eval()
    return {"model": model, "mean": mean, "scale": scale}


def predict(
    models: dict[str, Any], name: str, w: dict[str, np.ndarray], kind: str
) -> np.ndarray:
    if name == "median":
        return np.full(len(w["y"]), models["median"])
    if name == "linear_window":
        return linear_prediction(w)
    x = features(w, kind)
    if name == "ridge":
        return np.maximum(
            0, models["ridge"].predict(models["scaler"].transform(np.nan_to_num(x)))
        )
    if name == "gb":
        return np.maximum(0, models["gb"].predict(x))
    if name == "gpr":
        return np.maximum(0, models["gpr"].predict(models["scaler"].transform(x)))
    if name == "gru":
        import torch

        bundle = models["gru"]
        seq = np.stack([w["cap"], w["off"]], axis=2).astype(np.float32)
        z = torch.from_numpy((seq - bundle["mean"]) / bundle["scale"])
        with torch.inference_mode():
            return bundle["model"](z).numpy() * 100
    raise ValueError(name)


def macro(
    cells: np.ndarray, error: np.ndarray, squared: bool = False
) -> dict[str, float]:
    values = {}
    for c in np.unique(cells):
        e = error[cells == c]
        values[str(c)] = float(
            np.sqrt(np.mean(e**2)) if squared else np.mean(np.abs(e))
        )
    return values


def conformal_radius(scores: np.ndarray, coverage: float = COVERAGE) -> float:
    n = len(scores)
    rank = int(np.ceil((n + 1) * coverage))
    return float(np.sort(scores)[min(rank, n) - 1])


def interval_score(
    y: np.ndarray, low: np.ndarray, high: np.ndarray, alpha: float
) -> np.ndarray:
    return (high - low) + 2 / alpha * (low - y).clip(0) + 2 / alpha * (y - high).clip(0)


def run(cache: Path = CACHE) -> dict[str, Any]:
    arms = load_arms(cache)
    names = sorted(set(arms["fixed"]) & set(arms["adaptive"]))
    folds = make_folds(names)
    pred: dict[str, dict[str, list[np.ndarray]]] = {}
    meta: list[dict[str, np.ndarray]] = []
    meta_adaptive: list[dict[str, np.ndarray]] = []
    validation_mae: dict[str, list[float]] = {}
    timing: dict[str, float] = {}
    calibration_targets: list[np.ndarray] = []
    sizes: dict[str, int] = {}
    # arm -> (feature kind, indicator model?)
    for fold in folds:
        fixed = {k: stack_cells(arms["fixed"], fold[k]) for k in fold}
        adaptive = {k: stack_cells(arms["adaptive"], fold[k]) for k in fold}
        meta.append(fixed["test"])
        calibration_targets.append(fixed["calibration"]["y"])
        meta_adaptive.append(adaptive["test"])
        runs: dict[
            str,
            tuple[
                dict[str, np.ndarray],
                dict[str, np.ndarray],
                dict[str, np.ndarray],
                dict[str, np.ndarray],
                str,
                bool,
            ],
        ] = {
            "fixed_cap": (
                fixed["train"],
                fixed["validation"],
                fixed["test"],
                fixed["calibration"],
                "capacity",
                False,
            ),
            "fixed_ind": (
                fixed["train"],
                fixed["validation"],
                fixed["test"],
                fixed["calibration"],
                "capacity_indicators",
                True,
            ),
            "adaptive_cap_offset": (
                adaptive["train"],
                adaptive["validation"],
                adaptive["test"],
                adaptive["calibration"],
                "capacity_offset",
                False,
            ),
            "adaptive_cap_only": (
                adaptive["train"],
                adaptive["validation"],
                adaptive["test"],
                adaptive["calibration"],
                "capacity",
                False,
            ),
            "adaptive_span_only": (
                adaptive["train"],
                adaptive["validation"],
                adaptive["test"],
                adaptive["calibration"],
                "span_only",
                True,
            ),
            "adaptive_ind": (
                adaptive["train"],
                adaptive["validation"],
                adaptive["test"],
                adaptive["calibration"],
                "capacity_indicators",
                True,
            ),
        }
        for arm, (tr, va, te, ca, kind, ind) in runs.items():
            started = time.perf_counter()
            models = fit_models(tr, va, kind, ind)
            names_to_run = (
                ["gb"]
                if ind
                else ["median", "linear_window", "ridge", "gb", "gpr", "gru"]
            )
            for model in names_to_run:
                key = f"{arm}/{model}"
                p = predict(models, model, te, kind)
                pred.setdefault(key, {"test": [], "calibration": [], "validation": []})
                pred[key]["test"].append(p)
                pred[key]["calibration"].append(predict(models, model, ca, kind))
                pred[key]["validation"].append(predict(models, model, va, kind))
                validation_mae.setdefault(key, []).append(
                    float(
                        np.mean(
                            list(
                                macro(
                                    va["cell"], pred[key]["validation"][-1] - va["y"]
                                ).values()
                            )
                        )
                    )
                )
                if arm == "fixed_ind" and model == "gb":
                    sizes[key] = len(pickle.dumps(models["gb"]))
            timing[arm] = timing.get(arm, 0.0) + time.perf_counter() - started
            if arm == "fixed_ind":
                # Latency of the proposed model on the test windows of this fold.
                t0 = time.perf_counter()
                predict(models, "gb", te, kind)
                timing["fixed_ind_predict_s_per_1000_windows"] = (
                    timing.get("fixed_ind_predict_s_per_1000_windows", 0.0)
                    + (time.perf_counter() - t0) / len(te["y"]) * 1000 / FOLDS
                )
                missing = _with_missing(te)
                key = "fixed_ind_missing/gb"
                pred.setdefault(key, {"test": [], "calibration": [], "validation": []})
                pred[key]["test"].append(predict(models, "gb", missing, kind))
    out = {
        k: {s: np.concatenate(v) for s, v in d.items() if v} for k, d in pred.items()
    }
    fixed_meta = {k: np.concatenate([m[k] for m in meta]) for k in meta[0]}
    adaptive_meta = {
        k: np.concatenate([m[k] for m in meta_adaptive]) for k in meta_adaptive[0]
    }
    result = analyse(
        out, fixed_meta, adaptive_meta, validation_mae, pred, calibration_targets
    )
    result["latency_and_size"] = {
        "gb_indicators_predict_seconds_per_1000_windows": timing.get(
            "fixed_ind_predict_s_per_1000_windows"
        ),
        "gb_indicators_pickle_bytes": sizes.get("fixed_ind/gb"),
        "fit_seconds_total_per_arm": {
            k: round(v, 1) for k, v in timing.items() if "predict" not in k
        },
    }
    result["folds"] = [{k: v for k, v in f.items()} for f in folds]
    return result


def _with_missing(w: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(7)
    ind = w["ind"].copy()
    mask = rng.random(ind.shape[:2]) < MISSING_SHARE
    ind[mask] = np.nan
    return {**w, "ind": ind}


def bootstrap(cells: np.ndarray, diff: dict[str, float]) -> dict[str, float]:
    values = np.array(list(diff.values()))
    rng = np.random.default_rng(7)
    means = [rng.choice(values, size=len(values)).mean() for _ in range(BOOTSTRAPS)]
    return {
        "mean": float(values.mean()),
        "low95": float(np.percentile(means, 2.5)),
        "high95": float(np.percentile(means, 97.5)),
        "cells_better": int((values > 0).sum()),
        "cells": len(values),
    }


def analyse(
    out: dict[str, dict[str, np.ndarray]],
    fixed: dict[str, np.ndarray],
    adaptive: dict[str, np.ndarray],
    validation_mae: dict[str, list[float]],
    raw: dict[str, dict[str, list[np.ndarray]]],
    calibration_targets: list[np.ndarray],
) -> dict[str, Any]:
    result: dict[str, Any] = {"models": {}, "pairs": {}, "go_no_go": {}}

    def meta_of(key: str) -> dict[str, np.ndarray]:
        return fixed if key.startswith("fixed") else adaptive

    per_cell: dict[str, dict[str, float]] = {}
    for key, parts in out.items():
        m = meta_of(key)
        err = parts["test"] - m["y"]
        mae = macro(m["cell"], err)
        per_cell[key] = mae
        result["models"][key] = {
            "macro_mae_cycles": round(float(np.mean(list(mae.values()))), 2),
            "macro_rmse_cycles": round(
                float(np.mean(list(macro(m["cell"], err, True).values()))), 2
            ),
            "pooled_mae_cycles": round(float(np.abs(err).mean()), 2),
            "windows": int(len(err)),
            "cells": len(mae),
            "mean_validation_macro_mae": round(float(np.mean(validation_mae[key])), 2)
            if key in validation_mae
            else None,
        }
    # Baseline chosen on validation only.
    pool = ["fixed_cap/linear_window", "fixed_cap/ridge", "fixed_cap/gb"]
    result["baseline_by_validation"] = min(
        pool, key=lambda k: np.mean(validation_mae[k])
    )
    base = result["baseline_by_validation"]

    def pair(a: str, b: str) -> dict[str, float]:
        diff = {c: per_cell[a][c] - per_cell[b][c] for c in per_cell[a]}
        return bootstrap(fixed["cell"], diff)

    result["pairs"]["baseline_minus_gb_indicators_fixed"] = pair(base, "fixed_ind/gb")
    result["pairs"]["fixed_cap_gb_minus_fixed_ind_gb"] = pair(
        "fixed_cap/gb", "fixed_ind/gb"
    )
    result["pairs"]["adaptive_cap_offset_gb_minus_adaptive_cap_only_gb"] = pair(
        "adaptive_cap_offset/gb", "adaptive_cap_only/gb"
    )
    result["pairs"]["adaptive_cap_offset_gb_minus_fixed_cap_gb"] = pair(
        "adaptive_cap_offset/gb", "fixed_cap/gb"
    )
    result["pairs"]["adaptive_ind_gb_minus_fixed_ind_gb"] = pair(
        "adaptive_ind/gb", "fixed_ind/gb"
    )
    # Intervals: split-conformal on calibration cells of each fold.
    for key, label in (
        ("fixed_ind/gb", "gb_indicators"),
        ("fixed_cap/gb", "gb_capacity"),
    ):
        result.setdefault("intervals", {})[label] = _intervals(
            key, raw, fixed, calibration_targets
        )
    # Scenarios on the fixed arm.
    y, cell, pos = fixed["y"], fixed["cell"], fixed["pos"]
    limited = pos <= AGE_LIMIT
    result["scenarios"] = {
        "age_limited_position_le_300": {
            k: _subset_macro(out[k]["test"], y, cell, limited)
            for k in ("fixed_cap/gb", "fixed_ind/gb")
        },
        "missing_30pct_indicator_points": {
            "gb_indicators_clean": _subset_macro(
                out["fixed_ind/gb"]["test"], y, cell, np.ones_like(limited)
            ),
            "gb_indicators_missing": _subset_macro(
                out["fixed_ind_missing/gb"]["test"], y, cell, np.ones_like(limited)
            ),
            "gb_capacity": _subset_macro(
                out["fixed_cap/gb"]["test"], y, cell, np.ones_like(limited)
            ),
        },
    }
    result["risk_coverage"] = _risk_coverage(out, fixed)
    # Go/no-go as declared.
    median = result["models"]["adaptive_cap_offset/median"]["macro_mae_cycles"]
    span = result["models"]["adaptive_span_only/gb"]["macro_mae_cycles"]
    result["go_no_go"] = {
        "G1_stride_channel_material": {
            "span_only_over_median": round(span / median, 3),
            "pass_if_below": 0.8,
            "material": span / median < 0.8,
        },
        "G2_primary": {
            **result["pairs"]["baseline_minus_gb_indicators_fixed"],
            "pass": result["pairs"]["baseline_minus_gb_indicators_fixed"]["low95"] > 0,
        },
        "G3_coverage": {
            "per_cell_relative_conformal_coverage": result["intervals"][
                "gb_indicators"
            ]["relative"]["mean_per_cell_coverage"],
            "pass": result["intervals"]["gb_indicators"]["relative"][
                "mean_per_cell_coverage"
            ]
            >= 0.85,
        },
        "G4_abstention": {
            "ratio_at_60pct": result["risk_coverage"]["disagreement_ratio_at_0.6"],
            "pass": result["risk_coverage"]["disagreement_ratio_at_0.6"] <= 0.8,
        },
    }
    return result


def _subset_macro(
    pred: np.ndarray, y: np.ndarray, cell: np.ndarray, mask: np.ndarray
) -> dict[str, float]:
    err = (pred - y)[mask]
    vals = macro(cell[mask], err)
    return {
        "macro_mae_cycles": round(float(np.mean(list(vals.values()))), 2),
        "cells": len(vals),
        "windows": int(mask.sum()),
    }


def _intervals(
    key: str,
    raw: dict[str, dict[str, list[np.ndarray]]],
    fixed: dict[str, np.ndarray],
    calibration_targets: list[np.ndarray],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    sizes = [len(p) for p in raw[key]["test"]]
    start = 0
    absolute: list[tuple[np.ndarray, ...]] = []
    relative: list[tuple[np.ndarray, ...]] = []
    for i, size in enumerate(sizes):
        sl = slice(start, start + size)
        start += size
        y = fixed["y"][sl]
        p = raw[key]["test"][i]
        cal_p = raw[key]["calibration"][i]
        cal_y = calibration_targets[i]
        q_abs = conformal_radius(np.abs(cal_p - cal_y))
        q_rel = conformal_radius(np.abs(cal_p - cal_y) / np.maximum(cal_p, REL_FLOOR))
        absolute.append((fixed["cell"][sl], y, np.maximum(0, p - q_abs), p + q_abs))
        half = q_rel * np.maximum(p, REL_FLOOR)
        relative.append((fixed["cell"][sl], y, np.maximum(0, p - half), p + half))
    for label, parts in (("absolute", absolute), ("relative", relative)):
        cells = np.concatenate([x[0] for x in parts])
        y = np.concatenate([x[1] for x in parts])
        low = np.concatenate([x[2] for x in parts])
        high = np.concatenate([x[3] for x in parts])
        covered = (low <= y) & (y <= high)
        cov = {c: float(covered[cells == c].mean()) for c in np.unique(cells)}
        width = {c: float((high - low)[cells == c].mean()) for c in np.unique(cells)}
        score = interval_score(y, low, high, 1 - COVERAGE)
        iscore = {c: float(score[cells == c].mean()) for c in np.unique(cells)}
        result[label] = {
            "nominal": COVERAGE,
            "mean_per_cell_coverage": round(float(np.mean(list(cov.values()))), 3),
            "pooled_coverage": round(float(covered.mean()), 3),
            "mean_width_cycles": round(float(np.mean(list(width.values()))), 1),
            "mean_interval_score": round(float(np.mean(list(iscore.values()))), 1),
            "cells_with_coverage_below_0.5": int(sum(v < 0.5 for v in cov.values())),
        }
    return result


def _risk_coverage(
    out: dict[str, dict[str, np.ndarray]], fixed: dict[str, np.ndarray]
) -> dict[str, Any]:
    cell, y = fixed["cell"], fixed["y"]
    weight = np.array([1.0 / (cell == c).sum() for c in cell])
    ind, cap = out["fixed_ind/gb"]["test"], out["fixed_cap/gb"]["test"]
    err = np.abs(ind - y)
    proxies = {
        "disagreement": np.abs(ind - cap) / np.maximum(ind, REL_FLOOR),
        "predicted_remaining_inverse": 1.0 / np.maximum(ind, REL_FLOOR),
    }
    result: dict[str, Any] = {
        "weighted_mae_all": round(float((err * weight).sum() / weight.sum()), 2)
    }
    for name, score in proxies.items():
        order = np.argsort(score, kind="stable")
        cumulative = np.cumsum(weight[order]) / weight.sum()
        row = {}
        for share in (1.0, 0.8, 0.6, 0.4):
            keep = order[cumulative <= share + 1e-9]
            row[str(share)] = round(
                float((err[keep] * weight[keep]).sum() / weight[keep].sum()), 2
            )
        result[name] = row
    result["disagreement_ratio_at_0.6"] = round(
        result["disagreement"]["0.6"] / result["disagreement"]["1.0"], 3
    )
    result["note"] = (
        "random abstention keeps the weighted MAE at weighted_mae_all in expectation"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build.add_argument("--archive", type=Path, default=ARCHIVE)
    build.add_argument("--output", type=Path, default=CACHE)
    runner = sub.add_parser("run")
    runner.add_argument("--cache", type=Path, default=CACHE)
    runner.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "build":
        print(
            f"{build_cache(args.archive, args.output)} cells written to {args.output}"
        )
    else:
        result = run(args.cache)
        args.output.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
        print(json.dumps(result["go_no_go"], indent=1))


if __name__ == "__main__":
    main()
