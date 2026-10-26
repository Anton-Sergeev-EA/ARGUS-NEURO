"""Candidate capacity-fade curves and honest, forward-validated model choice.

Linear fade stays the default. A curved model replaces it only when it predicts the
held-out most recent observations clearly better, so extra flexibility is never used
just because it fits the past more closely.
"""

from __future__ import annotations

from typing import Callable

import numpy as np
from scipy.optimize import least_squares

from argus.battery.config import ProjectionConfig

Predictor = Callable[[np.ndarray], np.ndarray]
MODEL_NAMES = ("linear", "exponential", "quadratic")


def fit_linear(x: np.ndarray, y: np.ndarray) -> Predictor:
    slope, intercept = np.polyfit(x - x[-1], y, 1)
    return lambda q: intercept + slope * (np.asarray(q, dtype=float) - x[-1])


def fit_quadratic(x: np.ndarray, y: np.ndarray) -> Predictor:
    coefficients = np.polyfit(x - x[-1], y, 2)
    return lambda q: np.polyval(coefficients, np.asarray(q, dtype=float) - x[-1])


def fit_exponential(x: np.ndarray, y: np.ndarray) -> Predictor:
    """``floor + amplitude * exp(rate * (cycle - last))`` with a robust loss."""
    scale = max(float(x[-1] - x[0]), 1.0)
    last = float(x[-1])

    def curve(p: np.ndarray, q: np.ndarray) -> np.ndarray:
        return p[0] + p[1] * np.exp(p[2] * (q - last) / scale)

    start = np.array([y[-1] - 5.0, 5.0, 1.0])
    result = least_squares(
        lambda p: curve(p, x) - y,
        start,
        bounds=([0.0, -200.0, -8.0], [120.0, 200.0, 8.0]),
        loss="soft_l1",
        f_scale=1.0,
    )
    return lambda q: curve(result.x, np.asarray(q, dtype=float))


FITTERS: dict[str, Callable[[np.ndarray, np.ndarray], Predictor]] = {
    "linear": fit_linear,
    "exponential": fit_exponential,
    "quadratic": fit_quadratic,
}


def forward_error(
    name: str, x: np.ndarray, y: np.ndarray, config: ProjectionConfig
) -> float:
    """Mean absolute error when predicting the newest points from earlier ones."""
    errors = []
    for share in config.validation_origins:
        cut = int(len(x) * share)
        if cut < config.min_fit_points or cut >= len(x):
            continue
        try:
            predictor = FITTERS[name](x[:cut], y[:cut])
            errors.append(float(np.mean(np.abs(predictor(x[cut:]) - y[cut:]))))
        except (ValueError, FloatingPointError, np.linalg.LinAlgError):
            return float("inf")
    return float(np.mean(errors)) if errors else float("inf")


def select_model(
    x: np.ndarray, y: np.ndarray, config: ProjectionConfig
) -> tuple[str, dict[str, float]]:
    """Pick the curve by held-out error; linear wins unless clearly beaten."""
    if len(x) < config.nonlinear_min_records or config.model == "linear":
        return "linear", {}
    scores = {name: forward_error(name, x, y, config) for name in MODEL_NAMES}
    if config.model != "auto":
        return config.model, scores
    best = min(scores, key=lambda name: scores[name])
    linear = scores["linear"]
    if best != "linear" and scores[best] <= linear * (1 - config.required_improvement):
        return best, scores
    return "linear", scores


def crossing(
    predictor: Predictor, last: float, threshold: float, horizon: float
) -> float:
    """Cycles after ``last`` at which the curve first reaches ``threshold``; inf if never."""
    grid = np.linspace(last, last + horizon, 801)
    values = predictor(grid)
    below = np.nonzero(values <= threshold)[0]
    if not len(below):
        return float("inf")
    i = int(below[0])
    if i == 0:
        return 0.0
    # Linear interpolation inside the bracketing grid cell.
    v0, v1 = values[i - 1], values[i]
    fraction = 0.0 if v0 == v1 else (v0 - threshold) / (v0 - v1)
    return float(grid[i - 1] + fraction * (grid[i] - grid[i - 1]) - last)


def bootstrap_crossings(
    name: str,
    x: np.ndarray,
    y: np.ndarray,
    threshold: float,
    config: ProjectionConfig,
) -> tuple[np.ndarray, Predictor]:
    """Moving-block residual bootstrap of the time to threshold for any curve."""
    fitter = FITTERS[name]
    base = fitter(x, y)
    residual = y - base(x)
    rng = np.random.default_rng(config.seed)
    block = max(2, int(np.sqrt(len(y))))
    horizon = config.horizon_spans * float(x[-1] - x[0])
    times = []
    for _ in range(config.nonlinear_replicates):
        starts = rng.integers(0, len(y) - block + 1, size=int(np.ceil(len(y) / block)))
        noise = np.concatenate([residual[s : s + block] for s in starts])[: len(y)]
        try:
            refit = fitter(x, base(x) + noise)
        except (ValueError, FloatingPointError, np.linalg.LinAlgError):
            times.append(float("inf"))
            continue
        times.append(crossing(refit, float(x[-1]), threshold, horizon))
    return np.array(times), base
