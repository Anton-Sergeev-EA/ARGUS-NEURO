"""Evidence-bearing diagnostics with explicit abstention and synthetic RUL provenance.

Sensor evidence measures distance from healthy training references. It is not a
causal fault diagnosis or a probability of failure. Models and references remain
fixed at runtime: the engine never silently learns a degrading asset as normal.
"""

from __future__ import annotations

import collections
import hashlib
import json
import logging
import pickle
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import torch
from sklearn.exceptions import InconsistentVersionWarning

from argus.artifacts import ARTIFACTS_ROOT, active_artifacts_dir
from argus.features import extract_features
from argus.models import LSTMAutoencoder, RULRegressorGRU, SpectralBaselineDetector
from argus.simulator.telemetry_simulator import SENSOR_COLUMNS
from argus.training.datasets import WINDOW_LEN, SensorScaler

ARTIFACTS_DIR = ARTIFACTS_ROOT
N_FEATURES = len(SENSOR_COLUMNS)
REFERENCE_THRESHOLD_SIGMA = 6.0
logger = logging.getLogger(__name__)


@dataclass
class HealthAssessment:
    asset_id: str
    asset_type: str
    baseline_anomaly_score: float | None = None
    autoencoder_anomaly_score: float | None = None
    is_anomaly: bool | None = None
    rul_normalized: float | None = None
    rul_hours: float | None = None
    health_index: float | None = None
    model_backed: bool = False
    status: str = "warming_up"
    data_quality: dict[str, Any] = field(default_factory=dict)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    explanation: list[str] = field(default_factory=list)
    source: str = "simulation"
    rul_basis: str = "unavailable"
    rul_interval_normalized: list[float] | None = None
    detector_disagreement: bool = False
    model_version: str = "unavailable"
    assessment_id: str = ""


class HealthInferenceEngine:
    def __init__(
        self,
        artifacts_dir: Path | None = None,
        *,
        sample_interval_seconds: float = 5.0,
        source: str = "simulation",
    ) -> None:
        if not np.isfinite(sample_interval_seconds) or sample_interval_seconds <= 0:
            raise ValueError("sample_interval_seconds must be finite and positive")
        self._sample_interval = sample_interval_seconds
        self._source = source
        self._buffers: dict[str, collections.deque[list[float]]] = {}
        self._sample_times: dict[str, float] = {}
        self._issues: dict[str, list[str]] = {}
        self._model_version = "unavailable"
        self._load_error: str | None = None
        self._profiles: dict[str, dict[str, Any]] = {}
        try:
            selected = (
                Path(artifacts_dir)
                if artifacts_dir is not None
                else active_artifacts_dir()
            )
            self._loaded = self._try_load(selected)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            self._loaded = False
            self._load_error = type(exc).__name__
            logger.warning("Active bundle unavailable: %s", exc)

    def _try_load(self, artifacts_dir: Path) -> bool:
        try:
            report = json.loads(
                (artifacts_dir / "anomaly_training_report.json").read_text()
            )
            metadata = json.loads((artifacts_dir / "rul_metadata.json").read_text())
            for document in (report, metadata):
                if (
                    not isinstance(document, dict)
                    or document.get("schema_version") != 2
                    or document.get("sensor_columns") != SENSOR_COLUMNS
                    or document.get("window_len") != WINDOW_LEN
                ):
                    raise ValueError("incompatible model schema")
                if not np.isclose(
                    document["sample_interval_seconds"], self._sample_interval
                ):
                    raise ValueError("model sampling interval mismatch")
            for document, names in (
                (
                    report,
                    (
                        "baseline_detector.joblib",
                        "autoencoder.pt",
                        "sensor_scaler.json",
                    ),
                ),
                (metadata, ("rul_predictor.pt", "rul_sensor_scaler.json")),
            ):
                for name in names:
                    if (
                        hashlib.sha256((artifacts_dir / name).read_bytes()).hexdigest()
                        != document["sha256"][name]
                    ):
                        raise ValueError(f"model bundle checksum mismatch: {name}")
            if (
                metadata["schema_version"] != 2
                or metadata["sensor_columns"] != SENSOR_COLUMNS
                or metadata["window_len"] != WINDOW_LEN
            ):
                raise ValueError("incompatible model schema")
            if (
                metadata["data_source"] != "synthetic"
                or metadata["real_world_calibrated"] is not False
            ):
                raise ValueError(
                    "unsupported RUL calibration; independent validation required"
                )
            if not np.isclose(
                metadata["sample_interval_seconds"], self._sample_interval
            ):
                raise ValueError("model sampling interval mismatch")
            self._rul_horizon_seconds = float(metadata["horizon_seconds"])
            self._rul_error = float(
                metadata["prediction_interval"]["absolute_error_quantile_normalized"]
            )
            if (
                not np.isfinite([self._rul_horizon_seconds, self._rul_error]).all()
                or self._rul_horizon_seconds <= 0
                or not 0 <= self._rul_error <= 1
            ):
                raise ValueError("invalid RUL metadata")
            self._ae_threshold = float(report["autoencoder"]["anomaly_threshold"])
            if not np.isfinite(self._ae_threshold) or self._ae_threshold <= 0:
                raise ValueError("invalid reconstruction threshold")
            self._profiles = report.get("sensor_reference_profiles", {})
            for profile in self._profiles.values():
                if profile["columns"] != SENSOR_COLUMNS:
                    raise ValueError("reference sensor order mismatch")
                values = np.asarray([profile["mean"], profile["std"]], dtype=float)
                if (
                    values.shape != (2, N_FEATURES)
                    or not np.isfinite(values).all()
                    or (values[1] <= 0).any()
                ):
                    raise ValueError("invalid sensor reference")
            self._scaler = SensorScaler.load(artifacts_dir / "sensor_scaler.json")
            # Fixed filenames prevent artifact metadata from redirecting reads.
            if metadata["scaler_file"] != "rul_sensor_scaler.json":
                raise ValueError("unexpected RUL scaler")
            self._rul_scaler = SensorScaler.load(
                artifacts_dir / "rul_sensor_scaler.json"
            )
            with warnings.catch_warnings():
                warnings.simplefilter("error", InconsistentVersionWarning)
                self._baseline: SpectralBaselineDetector = joblib.load(
                    artifacts_dir / "baseline_detector.joblib"
                )
            self._autoencoder = LSTMAutoencoder(n_features=N_FEATURES)
            self._autoencoder.load_state_dict(
                torch.load(
                    artifacts_dir / "autoencoder.pt",
                    map_location="cpu",
                    weights_only=True,
                )
            )
            self._autoencoder.eval()
            self._rul_model = RULRegressorGRU(n_features=N_FEATURES)
            self._rul_model.load_state_dict(
                torch.load(
                    artifacts_dir / "rul_predictor.pt",
                    map_location="cpu",
                    weights_only=True,
                )
            )
            self._rul_model.eval()
            digest = hashlib.sha256()
            for name in (
                "baseline_detector.joblib",
                "autoencoder.pt",
                "rul_predictor.pt",
                "sensor_scaler.json",
                "rul_sensor_scaler.json",
                "anomaly_training_report.json",
                "rul_metadata.json",
            ):
                digest.update((artifacts_dir / name).read_bytes())
            self._model_version = digest.hexdigest()[:16]
            return True
        except (
            OSError,
            ValueError,
            KeyError,
            TypeError,
            RuntimeError,
            EOFError,
            pickle.UnpicklingError,
            ImportError,
            InconsistentVersionWarning,
        ) as exc:
            self._load_error = type(exc).__name__
            logger.warning("Models unavailable (%s): %s", type(exc).__name__, exc)
            return False

    @property
    def model_backed(self) -> bool:
        return self._loaded

    def reset_asset(self, asset_id: str) -> None:
        """Start a new acquisition session; never mix pre/post-gap windows."""
        self._buffers.pop(asset_id, None)
        self._sample_times.pop(asset_id, None)
        self._issues.pop(asset_id, None)

    def push_sample(
        self,
        asset_id: str,
        sensor_row: dict[str, Any],
        *,
        sample_time_s: float | None = None,
    ) -> None:
        issues: list[str] = []
        try:
            values = np.array([sensor_row[c] for c in SENSOR_COLUMNS], dtype=float)
            if values.shape != (N_FEATURES,) or not np.isfinite(values).all():
                issues.append("non_finite_sensors")
        except KeyError:
            issues.append("missing_sensors")
        except (TypeError, ValueError, OverflowError):
            issues.append("non_finite_sensors")
        timestamp: float | None = None
        if sample_time_s is not None:
            try:
                timestamp = float(sample_time_s)
                if not np.isfinite(timestamp):
                    issues.append("invalid_timestamp")
                elif asset_id in self._sample_times:
                    delta = timestamp - self._sample_times[asset_id]
                    if delta <= 0:
                        issues.append("non_monotonic_timestamp")
                    elif not np.isclose(
                        delta, self._sample_interval, rtol=0.1, atol=1e-6
                    ):
                        issues.append("sampling_gap")
            except (TypeError, ValueError, OverflowError):
                issues.append("invalid_timestamp")
        if issues:
            self.reset_asset(asset_id)
            self._issues[asset_id] = issues
            return
        self._issues[asset_id] = []
        if timestamp is not None:
            self._sample_times[asset_id] = timestamp
        buf = self._buffers.setdefault(asset_id, collections.deque(maxlen=WINDOW_LEN))
        buf.append(values.tolist())

    def ready(self, asset_id: str) -> bool:
        return len(
            self._buffers.get(asset_id, ())
        ) >= WINDOW_LEN and not self._issues.get(asset_id)

    def _finish(
        self, result: HealthAssessment, features: np.ndarray | None = None
    ) -> HealthAssessment:
        # Reproducible evidence identity, not a digital signature or authentication.
        payload = {
            "asset": result.asset_id,
            "type": result.asset_type,
            "model": result.model_version,
            "window": list(self._buffers.get(result.asset_id, ())),
            "features": features.tolist() if features is not None else None,
            "issues": result.data_quality["issues"],
            "source": self._source,
        }
        result.assessment_id = hashlib.sha256(
            json.dumps(payload, sort_keys=True, allow_nan=False).encode()
        ).hexdigest()[:20]
        return result

    def assess(
        self,
        asset_id: str,
        asset_type: str,
        waveform: np.ndarray,
        waveform_sample_rate_hz: float,
    ) -> HealthAssessment:
        issues = list(self._issues.get(asset_id, []))
        result = HealthAssessment(
            asset_id=asset_id,
            asset_type=asset_type,
            model_backed=self._loaded,
            source=self._source,
            model_version=self._model_version,
            data_quality={
                "issues": issues,
                "samples_collected": len(self._buffers.get(asset_id, ())),
                "samples_required": WINDOW_LEN,
            },
        )
        try:
            features = extract_features(waveform, waveform_sample_rate_hz)
            if not np.isfinite(features).all():
                raise ValueError("non-finite features")
        except (ValueError, TypeError, OverflowError):
            issues.append("invalid_waveform")
            features = None
        if issues:
            result.status = "invalid_data"
            result.explanation = issues.copy()
            return self._finish(result, features)
        if not self._loaded:
            result.status = "degraded"
            issues.append("models_unavailable")
            result.explanation = ["models_unavailable"]
            return self._finish(result, features)

        baseline = self._baseline.score(features)
        result.baseline_anomaly_score = round(baseline.anomaly_score, 4)
        if baseline.is_anomaly:
            result.explanation.append("spectral_anomaly")
        if not self.ready(asset_id):
            result.status = "warming_up"
            result.is_anomaly = True if baseline.is_anomaly else None
            result.explanation.append("insufficient_history")
            return self._finish(result, features)

        raw = np.array(self._buffers[asset_id], dtype=float)
        window = self._scaler.transform(raw)
        rul_window = self._rul_scaler.transform(raw)
        with torch.inference_mode():
            x = torch.from_numpy(window[np.newaxis].astype(np.float32))
            ae_error = float(self._autoencoder.reconstruction_error(x).item())
            rul_norm = float(
                self._rul_model(
                    torch.from_numpy(rul_window[np.newaxis].astype(np.float32))
                ).item()
            )
        if not np.isfinite([ae_error, rul_norm, baseline.anomaly_score]).all():
            result.status = "degraded"
            issues.append("non_finite_model_output")
            result.baseline_anomaly_score = None
            result.explanation = ["non_finite_model_output"]
            return self._finish(result, features)
        ae_anomaly = ae_error > self._ae_threshold
        reference_anomaly = False
        profile = self._profiles.get(asset_type)
        if profile is not None:
            means, stds = np.asarray(profile["mean"]), np.asarray(profile["std"])
            # RMS preserves alternating deviations (e.g. unstable frequency).
            deviations = np.sqrt(np.mean(((raw - means) / stds) ** 2, axis=0))
            for index in np.argsort(deviations)[::-1][:3]:
                result.evidence.append(
                    {
                        "sensor": SENSOR_COLUMNS[index],
                        "observed": round(float(raw[-1, index]), 5),
                        "reference": round(float(means[index]), 5),
                        "deviation_sigma": round(float(deviations[index]), 3),
                    }
                )
            reference_anomaly = bool(np.max(deviations) > REFERENCE_THRESHOLD_SIGMA)
        else:
            issues.append("reference_unavailable")
        votes = [baseline.is_anomaly, ae_anomaly] + (
            [reference_anomaly] if profile is not None else []
        )
        result.detector_disagreement = any(votes) and not all(votes)
        if ae_anomaly:
            result.explanation.append("reconstruction_anomaly")
        if reference_anomaly:
            result.explanation.append("sensor_reference_deviation")
        if result.detector_disagreement:
            result.explanation.append("detector_disagreement")
        result.is_anomaly = bool(any(votes))
        if not result.is_anomaly:
            result.explanation.append("no_anomaly_detected")
        result.status = "ready" if profile is not None else "degraded"
        ae_score = float(np.clip(ae_error / (self._ae_threshold * 3), 0, 1))
        result.autoencoder_anomaly_score = round(ae_score, 4)
        # A heuristic index for display, explicitly not failure probability.
        risk = max(
            baseline.anomaly_score,
            ae_score,
            min(float(np.max(deviations)) / (REFERENCE_THRESHOLD_SIGMA * 2), 1)
            if profile is not None
            else 0,
        )
        result.health_index = round(100 * (1 - risk), 1)
        result.rul_normalized = round(float(np.clip(rul_norm, 0, 1)), 4)
        result.rul_basis = "synthetic"
        result.rul_hours = round(
            result.rul_normalized * self._rul_horizon_seconds / 3600, 4
        )
        if self._source != "simulation":
            result.rul_hours = None
        result.rul_interval_normalized = [
            round(max(0, rul_norm - self._rul_error), 4),
            round(min(1, rul_norm + self._rul_error), 4),
        ]
        result.explanation.append("uncalibrated_rul")
        return self._finish(result, features)
