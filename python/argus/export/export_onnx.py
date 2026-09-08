"""Exports the trained tier-2 PyTorch models to ONNX.

ONNX is the interoperability layer of this project: a model trained once
in Python can be loaded and run from C++ (via ONNX Runtime's C++ API) for
low-latency inference on the same edge hardware that runs the
``argus_core`` feature extraction library -- no Python interpreter
required in the deployed loop. See ``docs`` / README for the C++
integration sketch.

Run with::

    python -m argus.export.export_onnx
"""

from __future__ import annotations

from pathlib import Path

import torch

from argus.models import LSTMAutoencoder, RULRegressorGRU
from argus.simulator.telemetry_simulator import SENSOR_COLUMNS
from argus.training.datasets import WINDOW_LEN

ARTIFACTS_DIR = Path(__file__).resolve().parents[3] / "artifacts"
N_FEATURES = len(SENSOR_COLUMNS)


def export_autoencoder() -> Path:
    model = LSTMAutoencoder(n_features=N_FEATURES)
    state_path = ARTIFACTS_DIR / "autoencoder.pt"
    model.load_state_dict(torch.load(state_path, map_location="cpu"))
    model.eval()

    # Fixed batch size of 1: the deployed inference loop (edge C++ side)
    # scores one telemetry window at a time, so a dynamic batch axis buys
    # nothing here and only adds exporter overhead/noise.
    dummy = torch.randn(1, WINDOW_LEN, N_FEATURES)
    out_path = ARTIFACTS_DIR / "autoencoder.onnx"
    torch.onnx.export(
        model, dummy, out_path,
        input_names=["telemetry_window"],
        output_names=["reconstruction"],
        opset_version=18,
    )
    return out_path


def export_rul_predictor() -> Path:
    model = RULRegressorGRU(n_features=N_FEATURES)
    state_path = ARTIFACTS_DIR / "rul_predictor.pt"
    model.load_state_dict(torch.load(state_path, map_location="cpu"))
    model.eval()

    dummy = torch.randn(1, WINDOW_LEN, N_FEATURES)
    out_path = ARTIFACTS_DIR / "rul_predictor.onnx"
    torch.onnx.export(
        model, dummy, out_path,
        input_names=["telemetry_window"],
        output_names=["normalized_rul"],
        opset_version=18,
    )
    return out_path


def main() -> None:
    ae_path = export_autoencoder()
    print(f"Exported autoencoder -> {ae_path}")
    rul_path = export_rul_predictor()
    print(f"Exported RUL predictor -> {rul_path}")


if __name__ == "__main__":
    main()
