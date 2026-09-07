"""Trains the tier-2 GRU Remaining-Useful-Life (RUL) regressor on the
simulator's labelled degradation trajectories and writes it to
``artifacts/rul_predictor.pt``.

Run with::

    python -m argus.training.train_rul
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset, random_split

from argus.models import RULRegressorGRU
from argus.training.datasets import SensorScaler, build_window_dataset, simulate_runs

ARTIFACTS_DIR = Path(__file__).resolve().parents[3] / "artifacts"


def main(epochs: int = 15, batch_size: int = 64, lr: float = 1e-3, seed: int = 5) -> None:
    torch.manual_seed(seed)
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    runs = simulate_runs(n_healthy_per_asset=10, n_faulty_per_fault_per_asset=6, seed=seed)

    scaler_path = ARTIFACTS_DIR / "sensor_scaler.json"
    scaler = SensorScaler.load(scaler_path) if scaler_path.exists() else SensorScaler.fit(runs)
    if not scaler_path.exists():
        scaler.save(scaler_path)

    x, _, y_rul = build_window_dataset(runs, scaler)
    dataset = TensorDataset(torch.from_numpy(x), torch.from_numpy(y_rul))

    n_val = max(1, int(0.15 * len(dataset)))
    train_ds, val_ds = random_split(dataset, [len(dataset) - n_val, n_val],
                                     generator=torch.Generator().manual_seed(seed))
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size)

    model = RULRegressorGRU(n_features=x.shape[-1])
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    loss_fn = nn.SmoothL1Loss()  # Huber loss: robust to the few near-zero-RUL outliers

    history = []
    for epoch in range(epochs):
        model.train()
        train_loss = 0.0
        for xb, yb in train_loader:
            optimizer.zero_grad()
            pred = model(xb)
            loss = loss_fn(pred, yb)
            loss.backward()
            optimizer.step()
            train_loss += loss.item() * xb.size(0)
        train_loss /= len(train_loader.dataset)

        model.eval()
        with torch.no_grad():
            val_abs_err = []
            for xb, yb in val_loader:
                pred = model(xb)
                val_abs_err.append(torch.abs(pred - yb))
            mae = torch.cat(val_abs_err).mean().item()
        history.append({"epoch": epoch, "train_loss": train_loss, "val_mae": mae})
        print(f"  epoch {epoch + 1:02d}/{epochs}  train_loss={train_loss:.4f}  val_MAE={mae:.4f}")

    torch.save(model.state_dict(), ARTIFACTS_DIR / "rul_predictor.pt")
    report = {
        "epochs": epochs,
        "final_val_mae_normalized": history[-1]["val_mae"],
        "history": history,
        "seconds": time.time() - t0,
        "n_windows": int(len(dataset)),
    }
    (ARTIFACTS_DIR / "rul_training_report.json").write_text(json.dumps(report, indent=2))
    print(f"Done in {report['seconds']:.1f}s. "
          f"Final normalized val MAE={report['final_val_mae_normalized']:.4f}. "
          f"Artifacts written to {ARTIFACTS_DIR}")


if __name__ == "__main__":
    main()
