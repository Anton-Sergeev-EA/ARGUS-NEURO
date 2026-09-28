"""Turns simulated telemetry runs into windowed tensors for the tier-2
deep models, and keeps a single, shared sensor normalization so training
and inference never disagree about scale.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from argus.simulator import AssetSimulator, AssetType, FaultType
from argus.simulator.telemetry_simulator import SENSOR_COLUMNS

WINDOW_LEN = 24  # samples per window (2 min at dt=5s)
WINDOW_STRIDE = 4

_FAULTS = [f for f in FaultType if f != FaultType.NONE]
_ASSET_TYPES = list(AssetType)


@dataclass
class SensorScaler:
    mean: np.ndarray
    std: np.ndarray

    def __post_init__(self) -> None:
        self.mean = np.asarray(self.mean, dtype=np.float64)
        self.std = np.asarray(self.std, dtype=np.float64)
        expected_shape = (len(SENSOR_COLUMNS),)
        if self.mean.shape != expected_shape or self.std.shape != expected_shape:
            raise ValueError(f"Scaler vectors must have shape {expected_shape}")
        if not np.isfinite(self.mean).all() or not np.isfinite(self.std).all():
            raise ValueError("Scaler values must be finite")
        if np.any(self.std <= 0):
            raise ValueError("Scaler standard deviations must be positive")

    def transform(self, x: np.ndarray) -> np.ndarray:
        values = np.asarray(x, dtype=np.float64)
        if values.ndim == 0 or values.shape[-1] != len(SENSOR_COLUMNS):
            raise ValueError(
                "Input must have one value per sensor in its final dimension"
            )
        if not np.isfinite(values).all():
            raise ValueError("Sensor values must be finite")
        return (values - self.mean) / self.std

    def to_json(self) -> dict[str, Any]:
        return {
            "mean": self.mean.tolist(),
            "std": self.std.tolist(),
            "columns": SENSOR_COLUMNS,
        }

    @staticmethod
    def from_json(d: dict[str, Any]) -> "SensorScaler":
        if d.get("columns") != SENSOR_COLUMNS:
            raise ValueError("Scaler sensor columns do not match the model input order")
        return SensorScaler(mean=np.array(d["mean"]), std=np.array(d["std"]))

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(self.to_json(), indent=2))

    @staticmethod
    def load(path: Path) -> "SensorScaler":
        return SensorScaler.from_json(json.loads(path.read_text()))

    @staticmethod
    def fit(runs: list[pd.DataFrame]) -> "SensorScaler":
        if not runs or any(run.empty for run in runs):
            raise ValueError("At least one nonempty training run is required")
        stacked = pd.concat(runs, ignore_index=True)[SENSOR_COLUMNS].to_numpy(
            dtype=np.float64
        )
        if not np.isfinite(stacked).all():
            raise ValueError("Training sensor values must be finite")
        mean = stacked.mean(axis=0)
        std = stacked.std(axis=0)
        std[std < 1e-6] = 1e-6
        return SensorScaler(mean=mean, std=std)


@dataclass(frozen=True)
class RunSplit:
    """Disjoint physical assets/runs, formed before scaling and windowing."""

    train: list[pd.DataFrame]
    validation: list[pd.DataFrame]
    test: list[pd.DataFrame]

    def to_json(self) -> dict[str, Any]:
        result: dict[str, Any] = {"strategy": "stratified_run"}
        for name in ("train", "validation", "test"):
            runs = getattr(self, name)
            result[name] = {
                "n_runs": len(runs),
                "run_ids": [str(run["asset_id"].iloc[0]) for run in runs],
            }
        return result


def split_runs(
    runs: list[pd.DataFrame],
    seed: int = 7,
    validation_fraction: float = 0.15,
    test_fraction: float = 0.15,
) -> RunSplit:
    """Stratify whole runs by equipment/fault; never split overlapping windows.

    Each asset ID must identify exactly one complete run. Repeated physical
    assets require an upstream grouped split rather than treating runs as
    independent assets. At least three runs per stratum are required.
    """
    if (
        not 0 < validation_fraction < 1
        or not 0 < test_fraction < 1
        or validation_fraction + test_fraction >= 1
    ):
        raise ValueError(
            "Validation/test fractions must be positive and sum to less than one"
        )
    if not runs:
        raise ValueError("No runs to split")
    strata: dict[tuple[str, str], list[pd.DataFrame]] = defaultdict(list)
    seen_ids: set[str] = set()
    for run in runs:
        if run.empty:
            raise ValueError("Cannot split an empty run")
        if any(
            run[column].nunique(dropna=False) != 1
            for column in ("asset_id", "asset_type", "fault_type")
        ):
            raise ValueError(
                "Each run must contain one asset ID, asset type, and fault type"
            )
        run_id = str(run["asset_id"].iloc[0])
        if run_id in seen_ids:
            raise ValueError("Duplicate asset IDs could leak between partitions")
        seen_ids.add(run_id)
        key = (str(run["asset_type"].iloc[0]), str(run["fault_type"].iloc[0]))
        strata[key].append(run)

    rng = np.random.default_rng(seed)
    train, validation, test = [], [], []
    for key in sorted(strata):
        group = sorted(strata[key], key=lambda run: str(run["asset_id"].iloc[0]))
        if len(group) < 3:
            raise ValueError(f"Stratum {key} requires at least three independent runs")
        n_validation = max(1, int(len(group) * validation_fraction))
        n_test = max(1, int(len(group) * test_fraction))
        if n_validation + n_test >= len(group):
            raise ValueError(f"Stratum {key} has no training runs after splitting")
        shuffled = [group[index] for index in rng.permutation(len(group))]
        validation.extend(shuffled[:n_validation])
        test.extend(shuffled[n_validation : n_validation + n_test])
        train.extend(shuffled[n_validation + n_test :])
    return RunSplit(train=train, validation=validation, test=test)


def healthy_runs(runs: list[pd.DataFrame]) -> list[pd.DataFrame]:
    return [run for run in runs if (run["fault_type"] == FaultType.NONE.value).all()]


def sensor_reference_profiles(runs: list[pd.DataFrame]) -> dict[str, dict[str, Any]]:
    """Equipment-specific healthy references fitted on training runs only."""
    references = {}
    healthy = healthy_runs(runs)
    for asset_type in AssetType:
        selected = [
            run for run in healthy if run["asset_type"].iloc[0] == asset_type.value
        ]
        if selected:
            references[asset_type.value] = SensorScaler.fit(selected).to_json()
    return references


def simulate_runs(
    n_healthy_per_asset: int = 12,
    n_faulty_per_fault_per_asset: int = 4,
    n_steps: int = 600,
    dt_seconds: float = 5.0,
    seed: int = 7,
) -> list[pd.DataFrame]:
    """Generate a balanced mixed-fleet dataset: healthy runs for every
    asset type, plus runs for every (asset type, fault type) combination.
    """
    if n_steps < 1 or not np.isfinite(dt_seconds) or dt_seconds <= 0:
        raise ValueError(
            "Simulation requires positive n_steps and finite positive dt_seconds"
        )
    if n_healthy_per_asset < 0 or n_faulty_per_fault_per_asset < 0:
        raise ValueError("Run counts cannot be negative")
    sim = AssetSimulator(seed=seed)
    runs: list[pd.DataFrame] = []

    for asset_type in _ASSET_TYPES:
        for i in range(n_healthy_per_asset):
            runs.append(
                sim.generate_run(
                    asset_id=f"{asset_type.value}-HEALTHY-{i:03d}",
                    asset_type=asset_type,
                    n_steps=n_steps,
                    dt_seconds=dt_seconds,
                    fault_type=FaultType.NONE,
                )
            )
        for fault in _FAULTS:
            for i in range(n_faulty_per_fault_per_asset):
                onset = 0.35 + 0.35 * (i / max(n_faulty_per_fault_per_asset - 1, 1))
                runs.append(
                    sim.generate_run(
                        asset_id=f"{asset_type.value}-{fault.value}-{i:03d}",
                        asset_type=asset_type,
                        n_steps=n_steps,
                        dt_seconds=dt_seconds,
                        fault_type=fault,
                        fault_onset_frac=onset,
                    )
                )
    return runs


def make_windows(
    run: pd.DataFrame,
    scaler: SensorScaler,
    window_len: int = WINDOW_LEN,
    stride: int = WINDOW_STRIDE,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Slice one run into overlapping windows.

    Returns
    -------
    X          (n_windows, window_len, n_features) normalized sensor windows
    y_anomaly  (n_windows,) 1 if any sample in the window is past fault onset
    y_rul      (n_windows,) normalized RUL in [0, 1] at the window's last step
    """
    if window_len < 1 or stride < 1:
        raise ValueError("Window length and stride must be positive")
    values = scaler.transform(run[SENSOR_COLUMNS].to_numpy())
    fault_label = run["fault_label"].to_numpy()
    rul = run["rul_steps"].to_numpy().astype(np.float64)
    n = len(run)
    horizon = float(n)
    if not np.isfinite(rul).all() or np.any(rul < 0):
        raise ValueError("RUL labels must be finite and nonnegative")
    if not np.isin(fault_label, [0, 1]).all():
        raise ValueError("Fault labels must be binary")
    if n < window_len:
        return (
            np.empty((0, window_len, len(SENSOR_COLUMNS)), dtype=np.float32),
            np.empty(0, dtype=np.int64),
            np.empty(0, dtype=np.float32),
        )

    xs, ys_anomaly, ys_rul = [], [], []
    for start in range(0, n - window_len + 1, stride):
        end = start + window_len
        xs.append(values[start:end])
        ys_anomaly.append(int(fault_label[start:end].any()))
        ys_rul.append(float(np.clip(rul[end - 1] / horizon, 0.0, 1.0)))

    return (
        np.stack(xs).astype(np.float32),
        np.array(ys_anomaly, dtype=np.int64),
        np.array(ys_rul, dtype=np.float32),
    )


def build_window_dataset(
    runs: list[pd.DataFrame], scaler: SensorScaler
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    all_x, all_ya, all_yr = [], [], []
    for run in runs:
        x, ya, yr = make_windows(run, scaler)
        all_x.append(x)
        all_ya.append(ya)
        all_yr.append(yr)
    if not all_x or not any(len(x) for x in all_x):
        raise ValueError("Dataset has no complete windows")
    return np.concatenate(all_x), np.concatenate(all_ya), np.concatenate(all_yr)
