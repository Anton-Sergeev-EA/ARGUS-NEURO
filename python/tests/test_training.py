from __future__ import annotations

import numpy as np
import pytest

from argus.models import SpectralBaselineDetector
from argus.training.datasets import (
    SensorScaler,
    healthy_runs,
    make_windows,
    sensor_reference_profiles,
    simulate_runs,
    split_runs,
)


def test_whole_runs_are_disjoint_and_split_is_reproducible() -> None:
    runs = simulate_runs(
        n_healthy_per_asset=3, n_faulty_per_fault_per_asset=3, n_steps=30
    )
    split = split_runs(runs, seed=11)
    ids = [
        set(part["run_ids"])
        for key, part in split.to_json().items()
        if key != "strategy"
    ]
    assert all(ids[i].isdisjoint(ids[j]) for i in range(3) for j in range(i))
    assert sum(map(len, ids)) == len(runs)
    assert split.to_json() == split_runs(list(reversed(runs)), seed=11).to_json()
    with pytest.raises(ValueError, match="Duplicate"):
        split_runs(runs + [runs[0]])


def test_reference_only_uses_healthy_training_assets() -> None:
    split = split_runs(
        simulate_runs(n_healthy_per_asset=3, n_faulty_per_fault_per_asset=3, n_steps=30)
    )
    before = sensor_reference_profiles(split.train)
    for run in split.validation + split.test:
        run.loc[:, "voltage_v"] = 1e9
    assert before == sensor_reference_profiles(split.train)
    scaler = SensorScaler.fit(healthy_runs(split.train))
    assert np.max(scaler.mean) < 1000


def test_short_runs_return_empty_windows_with_stable_shape() -> None:
    runs = simulate_runs(
        n_healthy_per_asset=1, n_faulty_per_fault_per_asset=0, n_steps=10
    )
    x, anomaly, rul = make_windows(runs[0], SensorScaler.fit(runs))
    assert x.shape == (0, 24, 6)
    assert anomaly.shape == rul.shape == (0,)
    with pytest.raises(ValueError):
        make_windows(runs[0], SensorScaler.fit(runs), stride=0)


def test_scaler_rejects_wrong_sensor_order_and_nonfinite_input() -> None:
    scaler = SensorScaler(np.zeros(6), np.ones(6))
    payload = scaler.to_json()
    payload["columns"] = list(reversed(payload["columns"]))
    with pytest.raises(ValueError, match="columns"):
        SensorScaler.from_json(payload)
    with pytest.raises(ValueError, match="finite"):
        scaler.transform(np.full((24, 6), float("nan")))


def test_spectral_calibration_controls_the_actual_decision() -> None:
    rng = np.random.default_rng(10)
    detector = SpectralBaselineDetector().fit(rng.normal(size=(100, 11)))
    calibration = rng.normal(size=(100, 11))
    detector.calibrate(calibration, quantile=0.99)
    assert detector.anomaly_threshold == pytest.approx(
        np.quantile(detector.score_batch(calibration), 0.99)
    )
    sample = np.full(11, 10.0)
    result = detector.score(sample)
    assert result.is_anomaly == (result.anomaly_score > detector.anomaly_threshold)
