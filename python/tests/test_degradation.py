from __future__ import annotations

import numpy as np
import pytest

from argus.battery.config import ProjectionConfig
from argus.battery.degradation import (
    bootstrap_crossings,
    crossing,
    fit_exponential,
    fit_linear,
    fit_quadratic,
    select_model,
)

X = np.arange(0, 400, 10.0)


def test_each_curve_recovers_its_own_noiseless_shape() -> None:
    for fitter, truth in (
        (fit_linear, 100 - 0.05 * X),
        (fit_quadratic, 100 - 0.02 * X - 0.0001 * X**2),
        (fit_exponential, 70 + 30 * np.exp(-X / 150)),
    ):
        np.testing.assert_allclose(fitter(X, truth)(X), truth, atol=0.3)


def test_crossing_interpolates_and_reports_never_as_infinity() -> None:
    line = lambda q: 100 - 0.1 * (np.asarray(q) - 0)  # noqa: E731
    assert crossing(line, 0.0, 90.0, 1000.0) == pytest.approx(100.0, abs=0.5)
    assert crossing(line, 0.0, 10.0, 100.0) == float("inf")
    assert crossing(line, 950.0, 90.0, 1000.0) == 0.0


def test_straight_fade_keeps_the_linear_model() -> None:
    noise = np.random.default_rng(1).normal(0, 0.05, len(X))
    name, _ = select_model(X, 100 - 0.05 * X + noise, ProjectionConfig(model="auto"))
    assert name == "linear"


def test_strongly_curved_fade_selects_a_curved_model() -> None:
    y = 100 - 0.00045 * X**2
    name, scores = select_model(X, y, ProjectionConfig(model="auto"))
    assert name != "linear"
    assert scores[name] < scores["linear"]


def test_bootstrap_times_are_reproducible() -> None:
    y = 100 - 0.00045 * X**2
    config = ProjectionConfig(model="quadratic", nonlinear_replicates=30)
    a, _ = bootstrap_crossings("quadratic", X, y, 80.0, config)
    b, _ = bootstrap_crossings("quadratic", X, y, 80.0, config)
    np.testing.assert_array_equal(a, b)
    assert np.all(a[np.isfinite(a)] >= 0)
