"""Tier-1 classical ML detector: fast, interpretable, and cheap enough to
run on constrained edge hardware (a shipboard control cabinet or a UAV
companion computer) right next to the C++ feature core it consumes.

This is the first line of defence in the two-tier architecture: an
Isolation Forest trained on the 11-dimensional spectral/statistical
feature vector (see ``argus.features``) flags obviously anomalous raw
waveforms in microseconds, without needing a GPU or a trend history.
Anything it flags -- or a periodic sample of everything -- is escalated to
the tier-2 deep sequence models (see ``models/autoencoder.py`` and
``models/rul_predictor.py``) for a fuller, trend-aware diagnosis.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler


@dataclass
class BaselineAssessment:
    anomaly_score: float  # higher = more anomalous, roughly in [0, 1]
    is_anomaly: bool


class SpectralBaselineDetector:
    """Isolation Forest over engineered waveform features."""

    def __init__(self, contamination: float = 0.08, random_state: int = 42) -> None:
        self._scaler = StandardScaler()
        self._model = IsolationForest(
            n_estimators=200,
            contamination=contamination,
            random_state=random_state,
        )
        self._fitted = False
        self.anomaly_threshold = 0.5

    def fit(self, feature_matrix: np.ndarray) -> "SpectralBaselineDetector":
        scaled = self._scaler.fit_transform(feature_matrix)
        self._model.fit(scaled)
        self._fitted = True
        return self

    def calibrate(
        self, healthy_features: np.ndarray, quantile: float = 0.99
    ) -> "SpectralBaselineDetector":
        """Set a threshold from separate healthy calibration waveforms."""
        if not 0 < quantile < 1:
            raise ValueError("quantile must be strictly between zero and one")
        scores = self.score_batch(healthy_features)
        self.anomaly_threshold = float(np.quantile(scores, quantile))
        return self

    def score(self, feature_vector: np.ndarray) -> BaselineAssessment:
        if not self._fitted:
            raise RuntimeError(
                "SpectralBaselineDetector.fit() must be called before score()"
            )
        x = self._scaler.transform(feature_vector.reshape(1, -1))
        # decision_function: higher = more normal. Flip + squash to [0, 1]
        # so it reads the same direction as the DL anomaly score.
        raw = -self._model.decision_function(x)[0]
        anomaly_score = float(1.0 / (1.0 + np.exp(-6.0 * raw)))
        is_anomaly = anomaly_score > getattr(self, "anomaly_threshold", 0.5)
        return BaselineAssessment(anomaly_score=anomaly_score, is_anomaly=is_anomaly)

    def score_batch(self, feature_matrix: np.ndarray) -> np.ndarray:
        if not self._fitted:
            raise RuntimeError(
                "SpectralBaselineDetector.fit() must be called before score_batch()"
            )
        scaled = self._scaler.transform(feature_matrix)
        raw = -self._model.decision_function(scaled)
        return 1.0 / (1.0 + np.exp(-6.0 * raw))
