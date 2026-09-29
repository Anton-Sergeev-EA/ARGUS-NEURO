"""Contract tests for evidence, abstention, time gaps and model provenance."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
import pytest
import torch

from argus.inference.engine import HealthAssessment, HealthInferenceEngine, WINDOW_LEN
from argus.models import LSTMAutoencoder, RULRegressorGRU, SpectralBaselineDetector
from argus.models.baseline import BaselineAssessment
from argus.simulator.telemetry_simulator import SENSOR_COLUMNS
from argus.training.datasets import SensorScaler


@pytest.fixture(scope="module")
def artifacts(tmp_path_factory: pytest.TempPathFactory) -> Path:
    directory = tmp_path_factory.mktemp("inference-models")
    scaler = SensorScaler(np.ones(6), np.ones(6))
    scaler.save(directory / "sensor_scaler.json")
    scaler.save(directory / "rul_sensor_scaler.json")
    baseline = SpectralBaselineDetector().fit(
        np.random.default_rng(7).normal(size=(30, 11))
    )
    joblib.dump(baseline, directory / "baseline_detector.joblib")
    for model, filename in [
        (LSTMAutoencoder(), "autoencoder.pt"),
        (RULRegressorGRU(), "rul_predictor.pt"),
    ]:
        with torch.no_grad():
            for parameter in model.parameters():
                parameter.zero_()
        torch.save(model.state_dict(), directory / filename)
    report = {
        "schema_version": 2,
        "sensor_columns": SENSOR_COLUMNS,
        "window_len": WINDOW_LEN,
        "sample_interval_seconds": 5.0,
        "sha256": {
            name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
            for name in (
                "baseline_detector.joblib",
                "autoencoder.pt",
                "sensor_scaler.json",
            )
        },
        "autoencoder": {"anomaly_threshold": 1000.0},
        "sensor_reference_profiles": {
            "TEST": {"columns": SENSOR_COLUMNS, "mean": [1.0] * 6, "std": [1.0] * 6}
        },
    }
    (directory / "anomaly_training_report.json").write_text(json.dumps(report))
    metadata = {
        "sha256": {
            name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
            for name in ("rul_predictor.pt", "rul_sensor_scaler.json")
        },
        "schema_version": 2,
        "sensor_columns": SENSOR_COLUMNS,
        "window_len": WINDOW_LEN,
        "data_source": "synthetic",
        "real_world_calibrated": False,
        "sample_interval_seconds": 5.0,
        "horizon_seconds": 3000.0,
        "scaler_file": "rul_sensor_scaler.json",
        "prediction_interval": {"absolute_error_quantile_normalized": 0.2},
    }
    (directory / "rul_metadata.json").write_text(json.dumps(metadata))
    return directory


@pytest.fixture
def engine(artifacts: Path) -> HealthInferenceEngine:
    result = HealthInferenceEngine(artifacts)
    assert result.model_backed
    result._baseline.score = lambda _: BaselineAssessment(0.1, False)
    return result


def row(**updates: float) -> dict[str, float]:
    return dict.fromkeys(SENSOR_COLUMNS, 1.0) | updates


def assess(engine: HealthInferenceEngine) -> HealthAssessment:
    return engine.assess("A", "TEST", np.sin(np.arange(256)), 1000.0)


def test_warmup_never_claims_full_remaining_life(engine: HealthInferenceEngine) -> None:
    engine.push_sample("A", row())
    result = assess(engine)
    assert result.status == "warming_up"
    assert result.rul_hours is result.rul_normalized is result.health_index is None
    assert result.is_anomaly is None


@pytest.mark.parametrize(
    "bad_row", [{}, row(voltage_v=float("nan")), row(current_a=float("inf"))]
)
def test_invalid_input_abstains_and_requires_fresh_history(
    engine: HealthInferenceEngine, bad_row: dict[str, float]
) -> None:
    for _ in range(WINDOW_LEN):
        engine.push_sample("A", row())
    engine.push_sample("A", bad_row)
    result = assess(engine)
    assert result.status == "invalid_data"
    assert result.is_anomaly is result.rul_hours is None
    assert result.data_quality["samples_collected"] == 0
    engine.push_sample("A", row())
    assert assess(engine).status == "warming_up"


@pytest.mark.parametrize(
    "timestamp,issue",
    [
        (0.0, "non_monotonic_timestamp"),
        (20.0, "sampling_gap"),
        (float("nan"), "invalid_timestamp"),
    ],
)
def test_time_discontinuity_resets_session(
    engine: HealthInferenceEngine, timestamp: float, issue: str
) -> None:
    engine.push_sample("A", row(), sample_time_s=0)
    engine.push_sample("A", row(), sample_time_s=timestamp)
    result = assess(engine)
    assert result.status == "invalid_data"
    assert issue in result.data_quality["issues"]


def test_alternating_frequency_deviation_has_traceable_evidence(
    engine: HealthInferenceEngine,
) -> None:
    for i in range(WINDOW_LEN):
        engine.push_sample(
            "A", row(frequency_hz=1 + (-1) ** i * 10), sample_time_s=i * 5
        )
    result = assess(engine)
    assert result.is_anomaly is True
    assert result.detector_disagreement is True
    assert result.evidence[0]["sensor"] == "frequency_hz"
    assert result.evidence[0]["deviation_sigma"] == 10.0
    assert "sensor_reference_deviation" in result.explanation
    assert result.assessment_id == assess(engine).assessment_id
    assert len(result.model_version) == 16


def test_synthetic_time_scale_and_uncertainty_are_explicit(
    engine: HealthInferenceEngine,
) -> None:
    for _ in range(WINDOW_LEN):
        engine.push_sample("A", row())
    result = assess(engine)
    assert result.status == "ready"
    assert result.rul_basis == "synthetic"
    assert result.rul_hours == pytest.approx(0.5 * 3000 / 3600, abs=0.0001)
    assert result.rul_interval_normalized == [0.3, 0.7]
    engine.reset_asset("A")
    assert assess(engine).status == "warming_up"


def test_live_data_does_not_receive_synthetic_hours(artifacts: Path) -> None:
    engine = HealthInferenceEngine(artifacts, source="telemetry")
    for _ in range(WINDOW_LEN):
        engine.push_sample("A", row())
    assert assess(engine).rul_hours is None


def test_missing_models_and_incompatible_sampling_abstain(
    tmp_path: Path, artifacts: Path
) -> None:
    for engine in [
        HealthInferenceEngine(tmp_path),
        HealthInferenceEngine(artifacts, sample_interval_seconds=1),
    ]:
        result = assess(engine)
        assert result.status == "degraded"
        assert not result.model_backed
        assert result.rul_hours is result.is_anomaly is None


def test_invalid_waveform_cannot_produce_json_nan(
    engine: HealthInferenceEngine,
) -> None:
    from dataclasses import asdict

    result = engine.assess("A", "TEST", np.array([float("nan")]), 1000)
    assert result.status == "invalid_data"
    json.dumps(asdict(result), allow_nan=False)


def test_tampered_bundle_is_rejected(artifacts: Path, tmp_path: Path) -> None:
    import shutil

    shutil.copytree(artifacts, tmp_path / "bundle")
    (tmp_path / "bundle" / "autoencoder.pt").write_bytes(b"corrupt")
    assert not HealthInferenceEngine(tmp_path / "bundle").model_backed
