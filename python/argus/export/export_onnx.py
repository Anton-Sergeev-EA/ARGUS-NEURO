"""Export fixed-shape models and numerically verify ONNX against PyTorch."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import onnx
import torch
from onnx.reference import ReferenceEvaluator

from argus.artifacts import active_artifacts_dir
from argus.models import LSTMAutoencoder, RULRegressorGRU
from argus.simulator.telemetry_simulator import SENSOR_COLUMNS
from argus.training.datasets import WINDOW_LEN


def _export(
    model: torch.nn.Module, directory: Path, stem: str, output: str
) -> tuple[Path, float]:
    model.load_state_dict(
        torch.load(directory / f"{stem}.pt", map_location="cpu", weights_only=True)
    )
    model.eval()
    rng = np.random.default_rng(23)
    dummy = torch.from_numpy(
        rng.normal(size=(1, WINDOW_LEN, len(SENSOR_COLUMNS))).astype(np.float32)
    )
    path = directory / f"{stem}.onnx"
    torch.onnx.export(
        model,
        dummy,
        path,
        input_names=["telemetry_window"],
        output_names=[output],
        opset_version=18,
        dynamo=True,
        external_data=False,
    )
    onnx.checker.check_model(str(path), full_check=True)
    evaluator = ReferenceEvaluator(str(path))
    max_error = 0.0
    # Include zero, nominal random, and elevated normalized measurements.
    for scale in (0.0, 1.0, 5.0):
        sample = (rng.normal(size=tuple(dummy.shape)) * scale).astype(np.float32)
        with torch.inference_mode():
            expected = model(torch.from_numpy(sample)).numpy()
        actual = evaluator.run(None, {"telemetry_window": sample})[0]
        np.testing.assert_allclose(actual, expected, atol=1e-5, rtol=1e-4)
        max_error = max(max_error, float(np.max(np.abs(actual - expected))))
    return path, max_error


def export_autoencoder(artifacts_dir: Path | None = None) -> Path:
    return _export(
        LSTMAutoencoder(),
        artifacts_dir or active_artifacts_dir(),
        "autoencoder",
        "reconstruction",
    )[0]


def export_rul_predictor(artifacts_dir: Path | None = None) -> Path:
    return _export(
        RULRegressorGRU(),
        artifacts_dir or active_artifacts_dir(),
        "rul_predictor",
        "normalized_rul",
    )[0]


def main(artifacts_dir: Path | None = None) -> None:
    directory = artifacts_dir or active_artifacts_dir()
    report = {}
    for model, stem, output in [
        (LSTMAutoencoder(), "autoencoder", "reconstruction"),
        (RULRegressorGRU(), "rul_predictor", "normalized_rul"),
    ]:
        path, error = _export(model, directory, stem, output)
        report[stem] = {
            "path": path.name,
            "max_absolute_error": error,
            "test_scales": [0, 1, 5],
            "backend": "onnx.reference.ReferenceEvaluator",
        }
    (directory / "onnx_validation_report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts-dir", type=Path)
    main(parser.parse_args().artifacts_dir)
