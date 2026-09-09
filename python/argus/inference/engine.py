"""Runtime inference engine: the two-tier ML/DL stack behind both the API
and, conceptually, an embedded C++ inference loop (see docs on the ONNX
export).

Tier 1 (SpectralBaselineDetector) scores an instantaneous raw waveform.
Tier 2 (LSTMAutoencoder + RULRegressorGRU) scores a rolling window of
recent multivariate telemetry. The two are fused into a single 0-100
health index that is what the dashboard and any downstream alerting
actually consumes -- the point of the cascade is that tier 1 is cheap
enough to run continuously at the edge, while tier 2 captures slower,
trend-level degradation that a single-instant reading cannot see.

If trained artifacts are not present (i.e. the training scripts have not
been run yet), the engine falls back to a transparent statistical
heuristic so the API and dashboard remain fully functional out of the
box -- clearly flagged via ``HealthAssessment.model_backed``.
"""

from __future__ import annotations

import collections
from dataclasses import dataclass, field
from pathlib import Path

import joblib
import numpy as np
import torch

from argus.features import extract_features
from argus.models import LSTMAutoencoder, RULRegressorGRU, SpectralBaselineDetector
from argus.simulator.telemetry_simulator import SENSOR_COLUMNS
from argus.training.datasets import SensorScaler

ARTIFACTS_DIR = Path(__file__).resolve().parents[3] / "artifacts"
WINDOW_LEN = 24
N_FEATURES = len(SENSOR_COLUMNS)
# A typical shift-to-shift-maintenance horizon this project's normalized
# RUL of "1.0" is calibrated against, purely for a human-readable estimate.
RUL_HORIZON_HOURS = 240.0


@dataclass
class HealthAssessment:
    asset_id: str
    asset_type: str
    baseline_anomaly_score: float
    autoencoder_anomaly_score: float
    is_anomaly: bool
    rul_normalized: float
    rul_hours: float
    health_index: float          # 0 (critical) .. 100 (nominal)
    model_backed: bool           # False => heuristic fallback, no trained artifacts found


class HealthInferenceEngine:
    def __init__(self, artifacts_dir: Path = ARTIFACTS_DIR):
        self._buffers: dict[str, collections.deque] = {}
        self._loaded = self._try_load(artifacts_dir)

    # ------------------------------------------------------------------
    def _try_load(self, artifacts_dir: Path) -> bool:
        try:
            self._baseline: SpectralBaselineDetector = joblib.load(artifacts_dir / "baseline_detector.joblib")
            self._scaler = SensorScaler.load(artifacts_dir / "sensor_scaler.json")

            self._autoencoder = LSTMAutoencoder(n_features=N_FEATURES)
            self._autoencoder.load_state_dict(torch.load(artifacts_dir / "autoencoder.pt", map_location="cpu"))
            self._autoencoder.eval()

            self._rul_model = RULRegressorGRU(n_features=N_FEATURES)
            self._rul_model.load_state_dict(torch.load(artifacts_dir / "rul_predictor.pt", map_location="cpu"))
            self._rul_model.eval()

            report_path = artifacts_dir / "anomaly_training_report.json"
            self._ae_threshold = 0.05
            if report_path.exists():
                import json
                report = json.loads(report_path.read_text())
                self._ae_threshold = report["autoencoder"]["anomaly_threshold"]
            return True
        except (FileNotFoundError, OSError):
            return False

    @property
    def model_backed(self) -> bool:
        return self._loaded

    # ------------------------------------------------------------------
    def push_sample(self, asset_id: str, sensor_row: dict) -> None:
        """Feed one new telemetry sample for `asset_id` into its rolling
        window buffer (call once per simulated/real control cycle)."""
        buf = self._buffers.setdefault(asset_id, collections.deque(maxlen=WINDOW_LEN))
        buf.append([sensor_row[c] for c in SENSOR_COLUMNS])

    def ready(self, asset_id: str) -> bool:
        return len(self._buffers.get(asset_id, [])) >= WINDOW_LEN

    # ------------------------------------------------------------------
    def assess(
        self,
        asset_id: str,
        asset_type: str,
        waveform: np.ndarray,
        waveform_sample_rate_hz: float,
    ) -> HealthAssessment:
        """Fuse tier-1 (instantaneous waveform) and tier-2 (rolling
        telemetry window) scores into one HealthAssessment."""
        if not self._loaded:
            return self._heuristic_assess(asset_id, asset_type, waveform)

        feat = extract_features(waveform, waveform_sample_rate_hz)
        baseline_score = self._baseline.score(feat).anomaly_score

        buf = self._buffers.get(asset_id)
        if buf and len(buf) >= WINDOW_LEN:
            window = self._scaler.transform(np.array(buf, dtype=np.float64))
            x = torch.from_numpy(window[np.newaxis, :, :].astype(np.float32))
            with torch.no_grad():
                ae_error = self._autoencoder.reconstruction_error(x).item()
                rul_norm = self._rul_model(x).item()
            ae_score = float(np.clip(ae_error / (self._ae_threshold * 3.0), 0.0, 1.0))
            is_anomaly = ae_error > self._ae_threshold or baseline_score > 0.75
        else:
            ae_score, rul_norm, is_anomaly = 0.0, 1.0, baseline_score > 0.75

        health_index = 100.0 * (1.0 - (0.45 * baseline_score + 0.35 * ae_score + 0.20 * (1.0 - rul_norm)))
        health_index = float(np.clip(health_index, 0.0, 100.0))

        return HealthAssessment(
            asset_id=asset_id,
            asset_type=asset_type,
            baseline_anomaly_score=round(baseline_score, 4),
            autoencoder_anomaly_score=round(ae_score, 4),
            is_anomaly=bool(is_anomaly),
            rul_normalized=round(rul_norm, 4),
            rul_hours=round(rul_norm * RUL_HORIZON_HOURS, 1),
            health_index=round(health_index, 1),
            model_backed=True,
        )

    # ------------------------------------------------------------------
    def _heuristic_assess(self, asset_id: str, asset_type: str, waveform: np.ndarray) -> HealthAssessment:
        """Used only when no trained artifacts are found -- a simple,
        transparent stand-in so the system is runnable before training."""
        rms = float(np.sqrt(np.mean(waveform ** 2)))
        deviation = float(np.clip(abs(rms - 0.75) / 0.75, 0.0, 1.0))
        health_index = float(np.clip(100.0 * (1.0 - deviation), 0.0, 100.0))
        return HealthAssessment(
            asset_id=asset_id,
            asset_type=asset_type,
            baseline_anomaly_score=round(deviation, 4),
            autoencoder_anomaly_score=0.0,
            is_anomaly=deviation > 0.6,
            rul_normalized=round(1.0 - deviation, 4),
            rul_hours=round((1.0 - deviation) * RUL_HORIZON_HOURS, 1),
            health_index=round(health_index, 1),
            model_backed=False,
        )
