"""Trains both tiers of the anomaly-detection stack and writes their
artifacts to ``artifacts/``:

Tier 1 -- SpectralBaselineDetector (Isolation Forest over C++/NumPy
          spectral features extracted from raw high-rate waveforms).
Tier 2 -- LSTMAutoencoder (trained unsupervised on healthy multivariate
          telemetry trends only; reconstruction error is the anomaly
          score).

Run with::

    python -m argus.training.train_anomaly
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import joblib
import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from argus.features import extract_features, using_native_core
from argus.models import LSTMAutoencoder, SpectralBaselineDetector
from argus.simulator import AssetSimulator, AssetType, FaultType
from argus.training.datasets import SensorScaler, build_window_dataset, simulate_runs

ARTIFACTS_DIR = Path(__file__).resolve().parents[3] / "artifacts"
WAVEFORM_SAMPLE_RATE_HZ = 2000.0


def _train_baseline(rng_seed: int = 11) -> tuple[SpectralBaselineDetector, dict]:
    sim = AssetSimulator(seed=rng_seed)
    features = []
    for asset_type in AssetType:
        for _ in range(150):
            wave = sim.generate_waveform(asset_type, FaultType.NONE, severity=0.0,
                                          sample_rate_hz=WAVEFORM_SAMPLE_RATE_HZ)
            features.append(extract_features(wave, WAVEFORM_SAMPLE_RATE_HZ))
    feature_matrix = np.stack(features)

    detector = SpectralBaselineDetector().fit(feature_matrix)

    # Quick sanity evaluation: healthy vs. faulty waveform separation.
    healthy_scores, faulty_scores = [], []
    for asset_type in AssetType:
        for _ in range(40):
            wave = sim.generate_waveform(asset_type, FaultType.NONE, severity=0.0,
                                          sample_rate_hz=WAVEFORM_SAMPLE_RATE_HZ)
            healthy_scores.append(detector.score(extract_features(wave, WAVEFORM_SAMPLE_RATE_HZ)).anomaly_score)
        for fault in [f for f in FaultType if f != FaultType.NONE]:
            for _ in range(15):
                wave = sim.generate_waveform(asset_type, fault, severity=0.85,
                                              sample_rate_hz=WAVEFORM_SAMPLE_RATE_HZ)
                faulty_scores.append(detector.score(extract_features(wave, WAVEFORM_SAMPLE_RATE_HZ)).anomaly_score)

    metrics = {
        "backend": "native_cpp" if using_native_core() else "numpy_fallback",
        "healthy_mean_score": float(np.mean(healthy_scores)),
        "faulty_mean_score": float(np.mean(faulty_scores)),
        "separation": float(np.mean(faulty_scores) - np.mean(healthy_scores)),
    }
    return detector, metrics


def _train_autoencoder(
    epochs: int = 12, batch_size: int = 64, lr: float = 1e-3, seed: int = 3,
) -> tuple[LSTMAutoencoder, SensorScaler, dict]:
    torch.manual_seed(seed)

    runs = simulate_runs(n_healthy_per_asset=16, n_faulty_per_fault_per_asset=3, seed=seed)
    healthy_runs = [r for r in runs if (r["fault_type"] == FaultType.NONE.value).all()]
    scaler = SensorScaler.fit(healthy_runs)

    x_healthy, _, _ = build_window_dataset(healthy_runs, scaler)
    x_all, y_anomaly_all, _ = build_window_dataset(runs, scaler)

    n_val = max(1, int(0.15 * len(x_healthy)))
    x_train, x_val = x_healthy[:-n_val], x_healthy[-n_val:]

    train_loader = DataLoader(TensorDataset(torch.from_numpy(x_train)), batch_size=batch_size, shuffle=True)

    model = LSTMAutoencoder(n_features=x_train.shape[-1])
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    loss_fn = nn.MSELoss()

    history = []
    model.train()
    for epoch in range(epochs):
        epoch_loss = 0.0
        for (batch,) in train_loader:
            optimizer.zero_grad()
            recon = model(batch)
            loss = loss_fn(recon, batch)
            loss.backward()
            optimizer.step()
            epoch_loss += loss.item() * batch.size(0)
        epoch_loss /= len(train_loader.dataset)
        history.append(epoch_loss)

    # Detection threshold: 95th percentile of held-out *healthy* reconstruction error.
    val_errors = model.reconstruction_error(torch.from_numpy(x_val)).numpy()
    threshold = float(np.percentile(val_errors, 95))

    # Evaluate against the full mixed (healthy + faulty) window set.
    all_errors = model.reconstruction_error(torch.from_numpy(x_all)).numpy()
    predicted_anomaly = (all_errors > threshold).astype(int)
    tp = int(((predicted_anomaly == 1) & (y_anomaly_all == 1)).sum())
    fp = int(((predicted_anomaly == 1) & (y_anomaly_all == 0)).sum())
    fn = int(((predicted_anomaly == 0) & (y_anomaly_all == 1)).sum())
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    metrics = {
        "epochs": epochs,
        "final_train_loss": history[-1],
        "loss_history": history,
        "anomaly_threshold": threshold,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "n_windows_evaluated": int(len(x_all)),
    }
    return model, scaler, metrics


def main() -> None:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    print("[1/2] Training tier-1 spectral baseline (Isolation Forest)...")
    baseline, baseline_metrics = _train_baseline()
    joblib.dump(baseline, ARTIFACTS_DIR / "baseline_detector.joblib")
    print(f"      backend={baseline_metrics['backend']} "
          f"healthy={baseline_metrics['healthy_mean_score']:.3f} "
          f"faulty={baseline_metrics['faulty_mean_score']:.3f} "
          f"separation={baseline_metrics['separation']:.3f}")

    print("[2/2] Training tier-2 LSTM autoencoder...")
    autoencoder, scaler, ae_metrics = _train_autoencoder()
    torch.save(autoencoder.state_dict(), ARTIFACTS_DIR / "autoencoder.pt")
    scaler.save(ARTIFACTS_DIR / "sensor_scaler.json")
    print(f"      loss={ae_metrics['final_train_loss']:.5f} "
          f"precision={ae_metrics['precision']:.3f} "
          f"recall={ae_metrics['recall']:.3f} f1={ae_metrics['f1']:.3f}")

    report = {"baseline": baseline_metrics, "autoencoder": ae_metrics, "seconds": time.time() - t0}
    (ARTIFACTS_DIR / "anomaly_training_report.json").write_text(json.dumps(report, indent=2))
    print(f"Done in {report['seconds']:.1f}s. Artifacts written to {ARTIFACTS_DIR}")


if __name__ == "__main__":
    main()
