"""Remaining-life method comparison on HUST under the protocol in
``experiments/2026-10-30_method_hust/preregistration.json``.

Independent of ``fixed_stride_experiment``. Cells are the unit of independence: ten
grouped development splits plus one locked confirmation group of cells that are never
used for choosing the baseline. Every model sees the same windows (common requirement,
fixed physical stride), and scalers and models are fitted on training cells only.
"""

from __future__ import annotations

import argparse
import json
import pickle
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, ConstantKernel, WhiteKernel
from sklearn.linear_model import Ridge
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler

from argus.battery import hust, hust_curves
from argus.battery.data import load_histories_with_meta
from argus.battery.windows import CellWindows, cell_windows, stack

STRIDE = 5
SIZE = 8
THRESHOLD_PCT = 90.0
DEV_SEEDS = tuple(range(201, 211))
LOCK_SEED = 999
FINAL_SEED = 777
LOCKED = 15
DEV_TEST, DEV_CAL, DEV_VAL = 12, 10, 10
FINAL_CAL, FINAL_VAL = 10, 10
COVERAGE = 0.9
ALPHA = 1.0 - COVERAGE
FLOOR = 50.0
GPR_WINDOWS = 800
ACCEPT = 0.6
MISSING_SHARE = 0.3
BOOTSTRAPS = 2000
BOOT_SEED = 7
# Post-hoc sensitivity (not in the preregistration): anisotropic GPR kernel.
ARD = False
BASELINES = (
    "median",
    "linear_window",
    "ridge",
    "gb_capacity",
    "gpr_capacity",
    "gru_capacity",
)
METHODS = ("gb_indicators", "ensemble", "ensemble_gated")
ALL_MODELS = BASELINES + METHODS
CHANNELS = hust_curves.INDICATORS
OUTPUT = (
    Path(__file__).resolve().parents[3]
    / "experiments/2026-10-30_method_hust/metrics.json"
)


# ---------------------------------------------------------------- data


def load_cells() -> tuple[dict[str, CellWindows], dict[str, Any]]:
    meta, histories = load_histories_with_meta(hust.OUTPUT, THRESHOLD_PCT)
    if meta.get("diagnostic_only") or meta.get("stride") != STRIDE:
        raise ValueError("expected the fixed-stride cache at stride 5")
    imeta, series = hust_curves.load_with_meta(hust_curves.OUTPUT)
    if imeta.get("stride") != STRIDE:
        raise ValueError("indicator cache was thinned differently")
    cells = {
        h.profile.battery_id: cell_windows(
            h, series.get(h.profile.battery_id, {}), CHANNELS
        )
        for h in histories
    }
    kept = {k: v for k, v in cells.items() if len(v)}
    info = {
        "cells_total": len(cells),
        "cells_with_windows": len(kept),
        "censored_or_empty": sorted(set(cells) - set(kept)),
        "windows": int(sum(len(v) for v in kept.values())),
    }
    return kept, info


def design(cells: list[CellWindows]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Columns: 8 capacity values, then 8 values per indicator in ``CHANNELS`` order."""
    return stack(cells, CHANNELS, with_offset=False)


def capacity(x: np.ndarray) -> np.ndarray:
    return x[:, :SIZE]


def columns(channels: tuple[str, ...]) -> list[int]:
    idx = list(range(SIZE))
    for name in channels:
        k = CHANNELS.index(name)
        idx += list(range(SIZE + SIZE * k, SIZE + SIZE * (k + 1)))
    return idx


# ---------------------------------------------------------------- models


def linear_prediction(x: np.ndarray, cap: float) -> np.ndarray:
    soh = capacity(x) * 100.0
    axis = np.arange(SIZE) * float(STRIDE)
    axis = axis - axis.mean()
    slope = ((soh - soh.mean(axis=1, keepdims=True)) * axis).sum(axis=1) / (
        axis**2
    ).sum()
    out = np.full(len(x), cap)
    falling = slope < -1e-6
    out[falling] = (soh[falling, -1] - THRESHOLD_PCT) / -slope[falling]
    return np.clip(out, 0.0, cap)


class Gru:
    def __init__(self, seed: int = 3) -> None:
        self.seed = seed

    def fit(
        self, x: np.ndarray, y: np.ndarray, xv: np.ndarray, yv: np.ndarray
    ) -> "Gru":
        import torch
        from torch import nn

        torch.set_num_threads(1)
        torch.manual_seed(self.seed)
        self.mu, self.sd = x.mean(), x.std() + 1e-9
        self.ym, self.ys = y.mean(), y.std() + 1e-9
        self.torch = torch

        class Net(nn.Module):
            def __init__(self) -> None:
                super().__init__()
                self.rnn = nn.GRU(1, 32, batch_first=True)
                self.head = nn.Linear(32, 1)

            def forward(self, s: Any) -> Any:
                out, _ = self.rnn(s)
                return self.head(out[:, -1]).squeeze(-1)

        self.net = Net()
        opt = torch.optim.Adam(self.net.parameters(), lr=3e-3)
        tx, ty = (
            self._seq(x),
            torch.tensor((y - self.ym) / self.ys, dtype=torch.float32),
        )
        vx = self._seq(xv)
        gen = torch.Generator().manual_seed(self.seed)
        best, best_state, patience = float("inf"), None, 0
        for _ in range(40):
            self.net.train()
            order = torch.randperm(len(tx), generator=gen)
            for i in range(0, len(tx), 256):
                b = order[i : i + 256]
                opt.zero_grad()
                loss = nn.functional.mse_loss(self.net(tx[b]), ty[b])
                loss.backward()
                opt.step()
            self.net.eval()
            with torch.no_grad():
                err = float(
                    np.abs(self.net(vx).numpy() * self.ys + self.ym - yv).mean()
                )
            if err < best:
                best, patience = err, 0
                best_state = {k: v.clone() for k, v in self.net.state_dict().items()}
            else:
                patience += 1
                if patience >= 6:
                    break
        assert best_state is not None
        self.net.load_state_dict(best_state)
        return self

    def _seq(self, x: np.ndarray) -> Any:
        return self.torch.tensor(
            ((x - self.mu) / self.sd)[:, :, None], dtype=self.torch.float32
        )

    def predict(self, x: np.ndarray) -> np.ndarray:
        self.net.eval()
        with self.torch.no_grad():
            return np.asarray(self.net(self._seq(x)).numpy() * self.ys + self.ym)


def gb(seed: int = 3, **extra: Any) -> HistGradientBoostingRegressor:
    return HistGradientBoostingRegressor(
        max_iter=100,
        max_leaf_nodes=10,
        l2_regularization=1.0,
        random_state=seed,
        **extra,
    )


def weighted_quantile(values: np.ndarray, weights: np.ndarray, level: float) -> float:
    order = np.argsort(values)
    v, w = values[order], weights[order]
    cum = np.cumsum(w) / w.sum()
    return float(v[min(int(np.searchsorted(cum, level)), len(v) - 1)])


def cell_weights(owner: np.ndarray) -> np.ndarray:
    counts = np.bincount(owner)
    return 1.0 / counts[owner]


def fit_all(
    train: list[CellWindows], val: list[CellWindows], seed: int
) -> dict[str, Any]:
    """Everything is fitted on ``train`` cells; ``val`` only drives GRU early stopping."""
    x, y, _ = design(train)
    xv, yv, _ = design(val)
    cap_scaler = StandardScaler().fit(capacity(x))
    zc = cap_scaler.transform(capacity(x))
    rng = np.random.default_rng(seed)
    sample = rng.choice(len(x), size=min(GPR_WINDOWS, len(x)), replace=False)
    length = np.full(SIZE, 3.0) if ARD else 3.0
    kernel = ConstantKernel(1.0) * RBF(length_scale=length) + WhiteKernel(0.1)
    gpr = GaussianProcessRegressor(kernel, normalize_y=True, random_state=seed).fit(
        zc[sample], y[sample]
    )
    ind_cols = columns(CHANNELS)
    ind_scaler = StandardScaler().fit(x[:, ind_cols])
    models: dict[str, Any] = {
        "max": float(y.max()),
        "median": float(np.median(y)),
        "cap_scaler": cap_scaler,
        "ind_scaler": ind_scaler,
        "ridge": Ridge(alpha=1.0).fit(zc, y),
        "gb_capacity": gb(seed).fit(zc, y),
        "gpr": gpr,
        "gb_indicators": gb(seed).fit(ind_scaler.transform(x[:, ind_cols]), y),
        "q_lo": gb(seed, loss="quantile", quantile=ALPHA / 2).fit(
            ind_scaler.transform(x[:, ind_cols]), y
        ),
        "q_hi": gb(seed, loss="quantile", quantile=1 - ALPHA / 2).fit(
            ind_scaler.transform(x[:, ind_cols]), y
        ),
        "gru": Gru(seed).fit(capacity(x), y, capacity(xv), yv),
        "knn": NearestNeighbors(n_neighbors=5).fit(
            zc[rng.choice(len(zc), size=min(3000, len(zc)), replace=False)]
        ),
    }
    return models


def predict_all(
    m: dict[str, Any], x: np.ndarray, missing: np.ndarray | None = None
) -> dict[str, np.ndarray]:
    """Predictions of every model. ``missing`` marks windows whose indicators are unavailable."""
    zc = m["cap_scaler"].transform(capacity(x))
    xi = x.copy()
    if missing is not None:
        xi[missing, SIZE:] = np.nan
    zi = m["ind_scaler"].transform(xi[:, columns(CHANNELS)])
    clip = lambda p: np.clip(p, 0.0, m["max"])  # noqa: E731
    gpr, sigma = m["gpr"].predict(zc, return_std=True)
    gpr = clip(gpr)
    gbi = clip(m["gb_indicators"].predict(zi))
    ens = 0.5 * (gbi + gpr)
    gated = ens.copy()
    if missing is not None:
        gated[missing] = gpr[missing]
    return {
        "median": np.full(len(x), m["median"]),
        "linear_window": linear_prediction(x, m["max"]),
        "ridge": clip(m["ridge"].predict(zc)),
        "gb_capacity": clip(m["gb_capacity"].predict(zc)),
        "gpr_capacity": gpr,
        "gru_capacity": clip(m["gru"].predict(capacity(x))),
        "gb_indicators": gbi,
        "ensemble": ens,
        "ensemble_gated": gated,
        "_sigma": sigma,
        "_q_lo": clip(m["q_lo"].predict(zi)),
        "_q_hi": clip(m["q_hi"].predict(zi)),
    }


# ---------------------------------------------------------------- one split


def macro(err: np.ndarray, owner: np.ndarray) -> float:
    return float(np.mean([err[owner == c].mean() for c in np.unique(owner)]))


def interval_scores(
    lo: np.ndarray, hi: np.ndarray, y: np.ndarray, owner: np.ndarray
) -> dict[str, float]:
    cover = ((y >= lo) & (y <= hi)).astype(float)
    score = (
        (hi - lo)
        + (2 / ALPHA) * np.maximum(lo - y, 0)
        + (2 / ALPHA) * np.maximum(y - hi, 0)
    )
    cells = np.unique(owner)
    per_cell = np.array([cover[owner == c].mean() for c in cells])
    return {
        "coverage_per_cell_mean": float(per_cell.mean()),
        "cells_below_0.85": float((per_cell < 0.85).mean()),
        "width": float(np.mean([(hi - lo)[owner == c].mean() for c in cells])),
        "interval_score": float(np.mean([score[owner == c].mean() for c in cells])),
    }


def intervals(
    cal_y: np.ndarray,
    cal_owner: np.ndarray,
    pred_cal: dict[str, np.ndarray],
    pred: dict[str, np.ndarray],
) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    w = cell_weights(cal_owner)
    out: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for name in ("gb_indicators", "ensemble", "gpr_capacity"):
        res = np.abs(cal_y - pred_cal[name])
        r = weighted_quantile(res, w, COVERAGE)
        out[f"{name}/absolute"] = (np.maximum(pred[name] - r, 0), pred[name] + r)
        scale_c, scale = (
            np.maximum(pred_cal[name], FLOOR),
            np.maximum(pred[name], FLOOR),
        )
        rr = weighted_quantile(res / scale_c, w, COVERAGE)
        out[f"{name}/relative"] = (
            np.maximum(pred[name] - rr * scale, 0),
            pred[name] + rr * scale,
        )
    sc = np.maximum(pred_cal["_sigma"], 1e-6)
    rs = weighted_quantile(np.abs(cal_y - pred_cal["gpr_capacity"]) / sc, w, COVERAGE)
    out["gpr_capacity/gpr_sigma"] = (
        np.maximum(pred["gpr_capacity"] - rs * pred["_sigma"], 0),
        pred["gpr_capacity"] + rs * pred["_sigma"],
    )
    cqr = np.maximum(pred_cal["_q_lo"] - cal_y, cal_y - pred_cal["_q_hi"])
    q = weighted_quantile(cqr, w, COVERAGE)
    out["gb_indicators/cqr"] = (np.maximum(pred["_q_lo"] - q, 0), pred["_q_hi"] + q)
    return out


def abstention_scores(
    m: dict[str, Any],
    x: np.ndarray,
    pred: dict[str, np.ndarray],
    width: np.ndarray,
    seed: int,
) -> dict[str, np.ndarray]:
    ens = pred["ensemble"]
    dist = m["knn"].kneighbors(m["cap_scaler"].transform(capacity(x)))[0].mean(axis=1)
    return {
        "disagreement": np.abs(pred["gb_indicators"] - pred["gpr_capacity"])
        / np.maximum(ens, FLOOR),
        "ensemble_size": ens,
        "knn_distance": dist,
        "relative_width": width / np.maximum(ens, FLOOR),
        "random": np.random.default_rng(seed).random(len(x)),
    }


def run_split(
    train: list[CellWindows],
    val: list[CellWindows],
    cal: list[CellWindows],
    test: list[CellWindows],
    seed: int,
) -> dict[str, Any]:
    t0 = time.perf_counter()
    m = fit_all(train, val, seed)
    fit_seconds = time.perf_counter() - t0
    xv, yv, ov = design(val)
    pv = predict_all(m, xv)
    val_mae = {n: macro(np.abs(pv[n] - yv), ov) for n in ALL_MODELS}
    xc, yc, oc = design(cal)
    pc = predict_all(m, xc)
    x, y, owner = design(test)
    p = predict_all(m, x)
    iv = intervals(yc, oc, pc, p)
    width = iv["ensemble/relative"][1] - iv["ensemble/relative"][0]
    scores = abstention_scores(m, x, p, width, seed)
    accept = {}
    for name, s in scores.items():
        mask = np.zeros(len(x), dtype=bool)
        mask[np.argsort(s, kind="stable")[: int(round(ACCEPT * len(x)))]] = True
        accept[name] = mask
    rng = np.random.default_rng(seed + 1)
    missing = rng.random(len(x)) < MISSING_SHARE
    pm = predict_all(m, x, missing)
    cell_ids = [c.cell_id for c in test]
    owners_names = np.array(cell_ids)[
        np.concatenate([np.full(len(c), i) for i, c in enumerate(test)])
    ]
    latency = {}
    one = x[:1]
    t0 = time.perf_counter()
    for _ in range(50):
        predict_all(m, one)
    latency["predict_all_models_one_window_ms"] = (time.perf_counter() - t0) / 50 * 1000
    sizes = {
        "gb_indicators_bytes": len(pickle.dumps(m["gb_indicators"])),
        "gpr_bytes": len(pickle.dumps(m["gpr"])),
    }
    return {
        "val_macro_mae": val_mae,
        "fit_seconds": fit_seconds,
        "cell_names": owners_names.tolist(),
        "y": y.tolist(),
        "owner": owner.tolist(),
        "pred": {n: p[n].tolist() for n in ALL_MODELS},
        "pred_missing": {
            n: pm[n].tolist() for n in ("gb_indicators", "ensemble", "ensemble_gated")
        },
        "missing": missing.tolist(),
        "intervals": {k: [v[0].tolist(), v[1].tolist()] for k, v in iv.items()},
        "accept": {k: v.tolist() for k, v in accept.items()},
        "latency": latency,
        "sizes": sizes,
    }


def _job(
    args: tuple[
        list[CellWindows], list[CellWindows], list[CellWindows], list[CellWindows], int
    ],
) -> dict[str, Any]:
    return run_split(*args)


# ---------------------------------------------------------------- statistics


def bootstrap_mean(values: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    idx = rng.integers(0, len(values), size=(BOOTSTRAPS, len(values)))
    return values[idx].mean(axis=1)


def per_cell_mean(splits: list[dict[str, Any]], getter: Any) -> dict[str, float]:
    """Average of a per-window quantity inside each test cell, then across its appearances."""
    acc: dict[str, list[float]] = {}
    for s in splits:
        names = np.array(s["cell_names"])
        values = getter(s)
        for c in np.unique(names):
            acc.setdefault(str(c), []).append(float(values[names == c].mean()))
    return {c: float(np.mean(v)) for c, v in acc.items()}


def summarize(
    splits: list[dict[str, Any]], baseline: str, rng: np.random.Generator
) -> dict[str, Any]:
    mae = {
        n: per_cell_mean(
            splits, lambda s, n=n: np.abs(np.array(s["pred"][n]) - np.array(s["y"]))
        )
        for n in ALL_MODELS
    }
    cells = sorted(mae["median"])
    out: dict[str, Any] = {
        "cells_evaluated": len(cells),
        "splits": len(splits),
        "models": {},
        "paired_vs_baseline": {},
    }
    for n in ALL_MODELS:
        v = np.array([mae[n][c] for c in cells])
        boot = bootstrap_mean(v, rng)
        out["models"][n] = {
            "macro_mae": round(float(v.mean()), 2),
            "ci95": [
                round(float(np.percentile(boot, 2.5)), 2),
                round(float(np.percentile(boot, 97.5)), 2),
            ],
        }
    base = np.array([mae[baseline][c] for c in cells])
    for n in ALL_MODELS:
        d = base - np.array([mae[n][c] for c in cells])
        boot = bootstrap_mean(d, rng)
        rel = bootstrap_mean(d, rng) / base.mean()
        out["paired_vs_baseline"][n] = {
            "gain_cycles": round(float(d.mean()), 2),
            "relative_gain": round(float(d.mean() / base.mean()), 4),
            "ci95": [
                round(float(np.percentile(boot, 2.5)), 2),
                round(float(np.percentile(boot, 97.5)), 2),
            ],
            "ci975_bonferroni": [
                round(float(np.percentile(boot, 1.25)), 2),
                round(float(np.percentile(boot, 98.75)), 2),
            ],
            "relative_ci95": [
                round(float(np.percentile(rel, 2.5)), 4),
                round(float(np.percentile(rel, 97.5)), 4),
            ],
            "cells_better": int((d > 0).sum()),
        }
    return out


def interval_summary(splits: list[dict[str, Any]]) -> dict[str, Any]:
    names = splits[0]["intervals"].keys()
    out = {}
    for k in names:
        rows = []
        for s in splits:
            lo, hi = (np.array(a) for a in s["intervals"][k])
            rows.append(interval_scores(lo, hi, np.array(s["y"]), np.array(s["owner"])))
        out[k] = {
            key: round(float(np.mean([r[key] for r in rows])), 3) for key in rows[0]
        }
    return out


def abstention_summary(
    splits: list[dict[str, Any]], rng: np.random.Generator
) -> dict[str, Any]:
    """Risk of accepted windows per ranking, with cell-bootstrap intervals of differences."""
    rows: dict[str, list[tuple[str, float, float, float]]] = {}
    for s in splits:
        names = np.array(s["cell_names"])
        err = np.abs(np.array(s["pred"]["ensemble"]) - np.array(s["y"]))
        rel = err / np.maximum(np.array(s["y"]), FLOOR)
        for rank, mask in s["accept"].items():
            mask = np.array(mask)
            for c in np.unique(names):
                sel = names == c
                a = sel & mask
                rows.setdefault(rank, []).append(
                    (
                        str(c),
                        float(err[sel].mean()),
                        float(err[a].mean()) if a.any() else np.nan,
                        float(rel[a].mean()) if a.any() else np.nan,
                    )
                )
    cells = sorted({r[0] for r in rows["random"]})

    def table(rank: str, col: int) -> np.ndarray:
        acc: dict[str, list[float]] = {}
        for r in rows[rank]:
            if not np.isnan(r[col]):
                acc.setdefault(r[0], []).append(r[col])
        return np.array([np.mean(acc[c]) if c in acc else np.nan for c in cells])

    full = table("random", 1)
    out: dict[str, Any] = {
        "accepted_share": ACCEPT,
        "full_macro_mae": round(float(np.nanmean(full)), 2),
        "rankings": {},
    }
    ref = table("ensemble_size", 2)
    for rank in rows:
        mae60, rel60 = table(rank, 2), table(rank, 3)
        ok = ~np.isnan(mae60) & ~np.isnan(ref)
        diff = (ref - mae60)[ok]
        boot = bootstrap_mean(diff, rng)
        out["rankings"][rank] = {
            "macro_mae_at_accepted": round(float(np.nanmean(mae60)), 2),
            "ratio_to_full": round(float(np.nanmean(mae60) / np.nanmean(full)), 3),
            "relative_error_at_accepted": round(float(np.nanmean(rel60)), 3),
            "gain_vs_ensemble_size_ranking": round(float(diff.mean()), 2),
            "gain_vs_ensemble_size_ci95": [
                round(float(np.percentile(boot, 2.5)), 2),
                round(float(np.percentile(boot, 97.5)), 2),
            ],
        }
    return out


def missing_summary(
    splits: list[dict[str, Any]], rng: np.random.Generator
) -> dict[str, Any]:
    def per_cell(name: str) -> dict[str, float]:
        acc: dict[str, list[float]] = {}
        for s in splits:
            names, miss = np.array(s["cell_names"]), np.array(s["missing"])
            err = np.abs(np.array(s["pred_missing"][name]) - np.array(s["y"]))
            for c in np.unique(names):
                sel = (names == c) & miss
                if sel.any():
                    acc.setdefault(str(c), []).append(float(err[sel].mean()))
        return {c: float(np.mean(v)) for c, v in acc.items()}

    tables = {n: per_cell(n) for n in ("gb_indicators", "ensemble", "ensemble_gated")}
    cells = sorted(tables["ensemble"])
    out: dict[str, Any] = {"share_missing": MISSING_SHARE, "models": {}}
    for n, t in tables.items():
        out["models"][n] = round(float(np.mean([t[c] for c in cells])), 2)
    d = np.array([tables["ensemble"][c] - tables["ensemble_gated"][c] for c in cells])
    boot = bootstrap_mean(d, rng)
    out["gated_gain_over_ungated"] = {
        "mean": round(float(d.mean()), 2),
        "ci95": [
            round(float(np.percentile(boot, 2.5)), 2),
            round(float(np.percentile(boot, 97.5)), 2),
        ],
    }
    return out


# ---------------------------------------------------------------- orchestration


def group(cells: dict[str, CellWindows], ids: list[str]) -> list[CellWindows]:
    return [cells[i] for i in ids]


def run(
    workers: int = 10, seeds: tuple[int, ...] = DEV_SEEDS, ard: bool = False
) -> dict[str, Any]:
    global ARD
    ARD = ard
    cells, info = load_cells()
    ids = sorted(cells)
    order = np.random.default_rng(LOCK_SEED).permutation(len(ids))
    locked = [ids[i] for i in order[:LOCKED]]
    dev = [ids[i] for i in order[LOCKED:]]
    jobs = []
    for seed in seeds:
        p = [dev[i] for i in np.random.default_rng(seed).permutation(len(dev))]
        test, cal, val = (
            p[:DEV_TEST],
            p[DEV_TEST : DEV_TEST + DEV_CAL],
            p[DEV_TEST + DEV_CAL : DEV_TEST + DEV_CAL + DEV_VAL],
        )
        train = p[DEV_TEST + DEV_CAL + DEV_VAL :]
        jobs.append(
            (
                group(cells, train),
                group(cells, val),
                group(cells, cal),
                group(cells, test),
                seed,
            )
        )
    with ProcessPoolExecutor(max_workers=workers) as pool:
        dev_runs = list(pool.map(_job, jobs))
    baseline = min(
        BASELINES,
        key=lambda n: float(np.mean([r["val_macro_mae"][n] for r in dev_runs])),
    )
    rng = np.random.default_rng(BOOT_SEED)
    result: dict[str, Any] = {
        "data": info,
        "locked_cells": locked,
        "dev_splits": list(seeds),
        "baseline_validation_macro_mae": {
            n: round(float(np.mean([r["val_macro_mae"][n] for r in dev_runs])), 2)
            for n in BASELINES
        },
        "chosen_baseline": baseline,
        "development": summarize(dev_runs, baseline, rng),
        "development_intervals": interval_summary(dev_runs),
        "development_abstention": abstention_summary(dev_runs, rng),
        "development_missing_indicators": missing_summary(dev_runs, rng),
        "latency_and_size": {
            "fit_seconds_mean": round(
                float(np.mean([r["fit_seconds"] for r in dev_runs])), 1
            ),
            **{
                k: round(float(np.mean([r["latency"][k] for r in dev_runs])), 2)
                for k in dev_runs[0]["latency"]
            },
            **{
                k: int(np.mean([r["sizes"][k] for r in dev_runs]))
                for k in dev_runs[0]["sizes"]
            },
        },
    }
    p = [dev[i] for i in np.random.default_rng(FINAL_SEED).permutation(len(dev))]
    val, cal, train = (
        p[:FINAL_VAL],
        p[FINAL_VAL : FINAL_VAL + FINAL_CAL],
        p[FINAL_VAL + FINAL_CAL :],
    )
    final = run_split(
        group(cells, train),
        group(cells, val),
        group(cells, cal),
        group(cells, locked),
        FINAL_SEED,
    )
    result["confirmation"] = summarize([final], baseline, rng)
    result["confirmation_intervals"] = interval_summary([final])
    result["confirmation_abstention"] = abstention_summary([final], rng)
    result["confirmation_missing_indicators"] = missing_summary([final], rng)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=10)
    parser.add_argument(
        "--ard", action="store_true", help="post-hoc sensitivity: anisotropic GPR"
    )
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    started = time.perf_counter()
    result = run(args.workers, ard=args.ard)
    result["post_hoc_ard_gpr"] = args.ard
    result["wall_seconds"] = round(time.perf_counter() - started, 1)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {k: result[k] for k in ("chosen_baseline", "development", "confirmation")},
            indent=1,
        )
    )


if __name__ == "__main__":
    main()
