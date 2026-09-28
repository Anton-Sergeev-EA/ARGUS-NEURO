"""Train waveform and trend anomaly detectors with independent run splits."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from argus.features import extract_features, using_native_core
from argus.models import LSTMAutoencoder, SpectralBaselineDetector
from argus.simulator import AssetSimulator, AssetType, FaultType
from argus.simulator.telemetry_simulator import SENSOR_COLUMNS
from argus.training.datasets import (
    WINDOW_LEN,
    SensorScaler,
    build_window_dataset,
    healthy_runs,
    sensor_reference_profiles,
    simulate_runs,
    split_runs,
)
from argus.training.reproducibility import (
    classification_metrics,
    package_versions,
    seed_training,
    sha256_file,
    validate_training_config,
)

ARTIFACTS_DIR = Path(__file__).resolve().parents[3] / "artifacts"
WAVEFORM_SAMPLE_RATE_HZ = 2000.0


def _wave_features(sim: AssetSimulator, fault: FaultType, count: int) -> np.ndarray:
    return np.stack(
        [
            extract_features(
                sim.generate_waveform(
                    asset_type,
                    fault,
                    severity=0.0 if fault == FaultType.NONE else 0.85,
                    sample_rate_hz=WAVEFORM_SAMPLE_RATE_HZ,
                ),
                WAVEFORM_SAMPLE_RATE_HZ,
            )
            for asset_type in AssetType
            for _ in range(count)
        ]
    )


def _train_baseline(
    rng_seed: int = 11,
) -> tuple[SpectralBaselineDetector, dict[str, Any]]:
    features = _wave_features(AssetSimulator(seed=rng_seed), FaultType.NONE, 150)
    validation = _wave_features(AssetSimulator(seed=rng_seed + 1), FaultType.NONE, 150)
    detector = SpectralBaselineDetector().fit(features)
    detector.calibrate(validation, quantile=0.99)
    test_simulator = AssetSimulator(seed=rng_seed + 2)
    healthy_scores = detector.score_batch(
        _wave_features(test_simulator, FaultType.NONE, 40)
    )
    faulty_scores = np.concatenate(
        [
            detector.score_batch(_wave_features(test_simulator, fault, 15))
            for fault in FaultType
            if fault != FaultType.NONE
        ]
    )
    labels = np.concatenate(
        [np.zeros(len(healthy_scores)), np.ones(len(faulty_scores))]
    )
    scores = np.concatenate([healthy_scores, faulty_scores])
    metrics = {
        **classification_metrics(labels, scores > detector.anomaly_threshold),
        "backend": "native_cpp" if using_native_core() else "numpy_fallback",
        "healthy_mean_score": float(np.mean(healthy_scores)),
        "faulty_mean_score": float(np.mean(faulty_scores)),
        "separation": float(np.mean(faulty_scores) - np.mean(healthy_scores)),
        "anomaly_threshold": detector.anomaly_threshold,
        "threshold_quantile": 0.99,
        "train_seed": rng_seed,
        "validation_seed": rng_seed + 1,
        "test_seed": rng_seed + 2,
        "evaluation_partition": "independent_synthetic_test_waveforms",
    }
    return detector, metrics


def _reconstruction_errors(
    model: LSTMAutoencoder, values: np.ndarray, batch_size: int
) -> np.ndarray:
    return np.concatenate(
        [
            model.reconstruction_error(
                torch.from_numpy(values[start : start + batch_size])
            ).numpy()
            for start in range(0, len(values), batch_size)
        ]
    )


def _train_autoencoder(
    epochs: int = 12,
    batch_size: int = 64,
    lr: float = 1e-3,
    seed: int = 3,
    n_steps: int = 600,
    dt_seconds: float = 5.0,
) -> tuple[LSTMAutoencoder, SensorScaler, dict[str, Any]]:
    validate_training_config(epochs, batch_size, lr)
    generator = seed_training(seed)
    runs = simulate_runs(
        n_healthy_per_asset=16,
        n_faulty_per_fault_per_asset=3,
        seed=seed,
        n_steps=n_steps,
        dt_seconds=dt_seconds,
    )
    split = split_runs(runs, seed=seed)
    healthy_train = healthy_runs(split.train)
    scaler = SensorScaler.fit(healthy_train)
    x_train, _, _ = build_window_dataset(healthy_train, scaler)
    x_validation, _, _ = build_window_dataset(healthy_runs(split.validation), scaler)
    x_test, y_test, _ = build_window_dataset(split.test, scaler)
    train_loader = DataLoader(
        TensorDataset(torch.from_numpy(x_train)),
        batch_size=batch_size,
        shuffle=True,
        generator=generator,
    )
    model = LSTMAutoencoder(n_features=x_train.shape[-1])
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    loss_fn = nn.MSELoss()
    history = []
    model.train()
    for _ in range(epochs):
        epoch_loss = 0.0
        for (batch,) in train_loader:
            optimizer.zero_grad()
            loss = loss_fn(model(batch), batch)
            loss.backward()
            optimizer.step()
            epoch_loss += loss.item() * batch.size(0)
        history.append(epoch_loss / len(x_train))

    validation_errors = _reconstruction_errors(model, x_validation, batch_size)
    threshold = float(np.quantile(validation_errors, 0.99))
    test_errors = _reconstruction_errors(model, x_test, batch_size)
    metrics = {
        **classification_metrics(y_test, test_errors > threshold),
        "epochs": epochs,
        "batch_size": batch_size,
        "learning_rate": lr,
        "seed": seed,
        "final_train_loss": history[-1],
        "loss_history": history,
        "anomaly_threshold": threshold,
        "threshold_quantile": 0.99,
        "threshold_partition": "healthy_validation_runs",
        "scaler_partition": "healthy_train_runs",
        "evaluation_partition": "test",
        "split": split.to_json(),
        "n_train_windows": len(x_train),
        "n_validation_windows": len(x_validation),
        "sensor_reference_profiles": sensor_reference_profiles(split.train),
        "model_config": {
            "n_features": len(SENSOR_COLUMNS),
            "hidden_size": 32,
            "latent_size": 12,
            "num_layers": 1,
        },
    }
    return model, scaler, metrics


def main(
    artifacts_dir: Path = ARTIFACTS_DIR,
    epochs: int = 12,
    batch_size: int = 64,
    lr: float = 1e-3,
    seed: int = 3,
    n_steps: int = 600,
    dt_seconds: float = 5.0,
) -> None:
    validate_training_config(epochs, batch_size, lr)
    artifacts_dir = Path(artifacts_dir)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()
    print("[1/2] Training spectral baseline...", flush=True)
    baseline, baseline_metrics = _train_baseline()
    joblib.dump(baseline, artifacts_dir / "baseline_detector.joblib")
    print("[2/2] Training autoencoder on healthy training runs...", flush=True)
    autoencoder, scaler, ae_metrics = _train_autoencoder(
        epochs,
        batch_size,
        lr,
        seed,
        n_steps,
        dt_seconds,
    )
    torch.save(autoencoder.state_dict(), artifacts_dir / "autoencoder.pt")
    scaler.save(artifacts_dir / "sensor_scaler.json")
    report = {
        "schema_version": 2,
        "data_source": "synthetic",
        "real_world_calibrated": False,
        "versions": package_versions(),
        "sample_interval_seconds": dt_seconds,
        "n_steps": n_steps,
        "window_len": WINDOW_LEN,
        "sensor_columns": SENSOR_COLUMNS,
        "sensor_reference_profiles": ae_metrics.pop("sensor_reference_profiles"),
        "baseline": baseline_metrics,
        "autoencoder": ae_metrics,
        "sha256": {
            name: sha256_file(artifacts_dir / name)
            for name in (
                "baseline_detector.joblib",
                "autoencoder.pt",
                "sensor_scaler.json",
            )
        },
        "seconds": time.monotonic() - t0,
    }
    (artifacts_dir / "anomaly_training_report.json").write_text(
        json.dumps(report, indent=2)
    )
    print(
        f"Independent synthetic test F1={ae_metrics['f1']:.3f}. "
        f"Done in {report['seconds']:.1f}s -> {artifacts_dir}",
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts-dir", type=Path, default=ARTIFACTS_DIR)
    parser.add_argument("--epochs", type=int, default=12)
    parser.add_argument("--seed", type=int, default=3)
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
