"""ARGUS-NEURO: predictive health intelligence for power-electronics fleets.

A unified monitoring stack applicable to both marine power/control
equipment (frequency converters, UPS, energy storage, steering/thruster
drives) and unmanned aerial system power trains (power distribution units,
flight controllers, battery packs) -- the common ground between shipboard
and airborne electrical assets.

Sub-packages
------------
simulator   Synthetic multivariate telemetry generator with injectable
            fault modes, used for training and for the live demo feed.
features    Fast feature extraction (native C++ core when available,
            NumPy fallback otherwise).
models      PyTorch deep-learning models (LSTM autoencoder, GRU RUL
            regressor) and the classical Isolation Forest baseline.
training    Training / evaluation entry points.
export      ONNX export for cross-language, cross-platform inference.
inference   The runtime HealthInferenceEngine used by the API and,
            conceptually, by an embedded C++ inference bridge.
api         FastAPI + WebSocket backend serving the web dashboard.
"""

__version__ = "1.0.0"
