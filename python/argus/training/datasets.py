"""Turns simulated telemetry runs into windowed tensors for the tier-2
deep models, and keeps a single, shared sensor normalization so training
and inference never disagree about scale.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from argus.simulator import AssetSimulator, AssetType, FaultType
from argus.simulator.telemetry_simulator import SENSOR_COLUMNS

WINDOW_LEN = 24     # samples per window (2 min at dt=5s)
WINDOW_STRIDE = 4

_FAULTS = [f for f in FaultType if f != FaultType.NONE]
_ASSET_TYPES = list(AssetType)


@dataclass
class SensorScaler:
    mean: np.ndarray
    std: np.ndarray

    def transform(self, x: np.ndarray) -> np.ndarray:
        return (x - self.mean) / self.std

    def to_json(self) -> dict:
        return {"mean": self.mean.tolist(), "std": self.std.tolist(), "columns": SENSOR_COLUMNS}

    @staticmethod
    def from_json(d: dict) -> "SensorScaler":
        return SensorScaler(mean=np.array(d["mean"]), std=np.array(d["std"]))

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(self.to_json(), indent=2))

    @staticmethod
    def load(path: Path) -> "SensorScaler":
        return SensorScaler.from_json(json.loads(path.read_text()))

    @staticmethod
    def fit(runs: list[pd.DataFrame]) -> "SensorScaler":
        stacked = pd.concat(runs, ignore_index=True)[SENSOR_COLUMNS].to_numpy()
        mean = stacked.mean(axis=0)
        std = stacked.std(axis=0)
        std[std < 1e-6] = 1e-6
        return SensorScaler(mean=mean, std=std)


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
    sim = AssetSimulator(seed=seed)
    runs: list[pd.DataFrame] = []

    for asset_type in _ASSET_TYPES:
        for i in range(n_healthy_per_asset):
            runs.append(sim.generate_run(
                asset_id=f"{asset_type.value}-HEALTHY-{i:03d}",
                asset_type=asset_type,
                n_steps=n_steps, dt_seconds=dt_seconds,
                fault_type=FaultType.NONE,
            ))
        for fault in _FAULTS:
            for i in range(n_faulty_per_fault_per_asset):
                onset = 0.35 + 0.35 * (i / max(n_faulty_per_fault_per_asset - 1, 1))
                runs.append(sim.generate_run(
                    asset_id=f"{asset_type.value}-{fault.value}-{i:03d}",
                    asset_type=asset_type,
                    n_steps=n_steps, dt_seconds=dt_seconds,
                    fault_type=fault, fault_onset_frac=onset,
                ))
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
    values = scaler.transform(run[SENSOR_COLUMNS].to_numpy())
    fault_label = run["fault_label"].to_numpy()
    rul = run["rul_steps"].to_numpy().astype(np.float64)
    n = len(run)
    horizon = float(n)

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
    return np.concatenate(all_x), np.concatenate(all_ya), np.concatenate(all_yr)
