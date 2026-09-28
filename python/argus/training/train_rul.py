"""Train synthetic RUL on whole-run splits with an independent sensor scaler.

The horizon describes simulator time only. It is not a calibrated estimate
of real equipment lifetime. Healthy labels are right-censored at the horizon.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from argus.models import RULRegressorGRU
from argus.simulator.telemetry_simulator import SENSOR_COLUMNS
from argus.training.datasets import (
    WINDOW_LEN,
    SensorScaler,
    build_window_dataset,
    healthy_runs,
    simulate_runs,
    split_runs,
)
from argus.training.reproducibility import (
    package_versions,
    seed_training,
    sha256_file,
    validate_training_config,
)

ARTIFACTS_DIR = Path(__file__).resolve().parents[3] / "artifacts"


def _predict(model: RULRegressorGRU, values: np.ndarray, batch_size: int) -> np.ndarray:
    model.eval()
    with torch.no_grad():
        return np.concatenate(
            [
                model(torch.from_numpy(values[start : start + batch_size])).numpy()
                for start in range(0, len(values), batch_size)
            ]
        )


def train(
    epochs: int = 15,
    batch_size: int = 64,
    lr: float = 1e-3,
    seed: int = 5,
    n_steps: int = 600,
    dt_seconds: float = 5.0,
) -> tuple[RULRegressorGRU, SensorScaler, dict[str, Any]]:
    validate_training_config(epochs, batch_size, lr)
    generator = seed_training(seed)
    runs = simulate_runs(
        n_healthy_per_asset=10,
        n_faulty_per_fault_per_asset=6,
        seed=seed,
        n_steps=n_steps,
        dt_seconds=dt_seconds,
    )
    split = split_runs(runs, seed=seed)
    scaler = SensorScaler.fit(healthy_runs(split.train))
    x_train, _, y_train = build_window_dataset(split.train, scaler)
    x_validation, _, y_validation = build_window_dataset(split.validation, scaler)
    x_test, _, y_test = build_window_dataset(split.test, scaler)
    train_loader = DataLoader(
        TensorDataset(torch.from_numpy(x_train), torch.from_numpy(y_train)),
        batch_size=batch_size,
        shuffle=True,
        generator=generator,
    )
    model = RULRegressorGRU(n_features=len(SENSOR_COLUMNS))
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    loss_fn = nn.SmoothL1Loss()
    history = []
    for epoch in range(epochs):
        model.train()
        train_loss = 0.0
        for xb, yb in train_loader:
            optimizer.zero_grad()
            loss = loss_fn(model(xb), yb)
            loss.backward()
            optimizer.step()
            train_loss += loss.item() * xb.size(0)
        mae = float(
            np.abs(_predict(model, x_validation, batch_size) - y_validation).mean()
        )
        history.append(
            {
                "epoch": epoch + 1,
                "train_loss": train_loss / len(x_train),
                "val_mae": mae,
            }
        )
        print(f"  epoch {epoch + 1:02d}/{epochs} validation_MAE={mae:.4f}", flush=True)

    # Validation residuals determine the interval; the test set is evaluated once.
    validation_errors = np.abs(_predict(model, x_validation, batch_size) - y_validation)
    residual_quantile = float(np.quantile(validation_errors, 0.9, method="higher"))
    test_predictions = _predict(model, x_test, batch_size)
    test_errors = np.abs(test_predictions - y_test)
    baseline_prediction = float(np.median(y_train))
    baseline_mae = float(np.abs(y_test - baseline_prediction).mean())
    report = {
        "schema_version": 2,
        "data_source": "synthetic",
        "real_world_calibrated": False,
        "sample_interval_seconds": dt_seconds,
        "n_steps": n_steps,
        "horizon_seconds": n_steps * dt_seconds,
        "window_len": WINDOW_LEN,
        "sensor_columns": SENSOR_COLUMNS,
        "scaler_file": "rul_sensor_scaler.json",
        "scaler_partition": "healthy_train_runs",
        "prediction_interval": {
            "method": "held_out_validation_absolute_residual",
            "coverage": 0.9,
            "absolute_error_quantile_normalized": residual_quantile,
            "test_empirical_coverage": float(np.mean(test_errors <= residual_quantile)),
            "caveat": "Overlapping windows are correlated; no real-world coverage guarantee.",
        },
        "target_semantics": "Synthetic failure countdown; healthy runs right-censored at horizon.",
        "epochs": epochs,
        "batch_size": batch_size,
        "learning_rate": lr,
        "seed": seed,
        "versions": package_versions(),
        "model_config": {
            "n_features": len(SENSOR_COLUMNS),
            "hidden_size": 32,
            "num_layers": 2,
            "dropout": 0.1,
        },
        "split": split.to_json(),
        "evaluation_partition": "test",
        "final_val_mae_normalized": history[-1]["val_mae"],
        "test_mae_normalized": float(test_errors.mean()),
        "test_rmse_normalized": float(np.sqrt(np.mean(test_errors**2))),
        "baseline": {
            "method": "training_target_median",
            "prediction": baseline_prediction,
            "test_mae_normalized": baseline_mae,
        },
        "history": history,
        "n_train_windows": len(x_train),
        "n_validation_windows": len(x_validation),
        "n_test_windows": len(x_test),
    }
    return model, scaler, report


def main(
    epochs: int = 15,
    batch_size: int = 64,
    lr: float = 1e-3,
    seed: int = 5,
    artifacts_dir: Path = ARTIFACTS_DIR,
    n_steps: int = 600,
    dt_seconds: float = 5.0,
) -> None:
    started = time.monotonic()
    artifacts_dir = Path(artifacts_dir)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    model, scaler, report = train(epochs, batch_size, lr, seed, n_steps, dt_seconds)
    torch.save(model.state_dict(), artifacts_dir / "rul_predictor.pt")
    scaler.save(artifacts_dir / "rul_sensor_scaler.json")
    report["seconds"] = time.monotonic() - started
    report["sha256"] = {
        name: sha256_file(artifacts_dir / name)
        for name in (
            "rul_predictor.pt",
            "rul_sensor_scaler.json",
        )
    }
    (artifacts_dir / "rul_training_report.json").write_text(
        json.dumps(report, indent=2)
    )
    metadata_keys = (
        "schema_version",
        "data_source",
        "real_world_calibrated",
        "sample_interval_seconds",
        "n_steps",
        "horizon_seconds",
        "window_len",
        "sensor_columns",
        "scaler_file",
        "seed",
        "prediction_interval",
        "model_config",
        "versions",
        "sha256",
        "target_semantics",
    )
    (artifacts_dir / "rul_metadata.json").write_text(
        json.dumps({key: report[key] for key in metadata_keys}, indent=2),
    )
    print(
        f"Independent synthetic test MAE={report['test_mae_normalized']:.4f}; "
        f"median baseline={report['baseline']['test_mae_normalized']:.4f} -> {artifacts_dir}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts-dir", type=Path, default=ARTIFACTS_DIR)
    parser.add_argument("--epochs", type=int, default=15)
    parser.add_argument("--seed", type=int, default=5)
    parser.add_argument("--n-steps", type=int, default=600)
    parser.add_argument("--dt-seconds", type=float, default=5.0)
    arguments = parser.parse_args()
    main(
        artifacts_dir=arguments.artifacts_dir,
        epochs=arguments.epochs,
        seed=arguments.seed,
        n_steps=arguments.n_steps,
        dt_seconds=arguments.dt_seconds,
    )
