from __future__ import annotations

import numpy as np
import pytest

from argus.battery import curves

needs_native = pytest.mark.skipif(
    not curves.using_native_curves(), reason="C++ extension not built"
)


def charge(centre: float, height: float, n: int = 3000, seed: int | None = None):
    v = np.linspace(3.4, 4.2, n)
    slope = 0.2 + height * np.exp(-0.5 * ((v - centre) / 0.05) ** 2)
    q = np.concatenate([[0], np.cumsum(slope[1:] * np.diff(v))])
    if seed is not None:
        v = v + np.random.default_rng(seed).normal(0, 0.0003, n)
    return v, q


def test_numpy_path_finds_the_peak_and_its_ageing_shift() -> None:
    fresh = curves.incremental_capacity(*charge(3.80, 4.0), native=False)
    aged = curves.incremental_capacity(*charge(3.84, 2.5), native=False)
    assert fresh.peak_voltage_v == pytest.approx(3.80, abs=0.01)
    assert aged.peak_voltage_v > fresh.peak_voltage_v
    assert aged.peak_height_ah_per_v < fresh.peak_height_ah_per_v


@needs_native
@pytest.mark.parametrize("seed", [None, 1, 2, 3])
def test_native_and_numpy_incremental_capacity_agree(seed: int | None) -> None:
    v, q = charge(3.8, 3.0, seed=seed)
    a = curves.incremental_capacity(v, q, native=True)
    b = curves.incremental_capacity(v, q, native=False)
    np.testing.assert_allclose(a.dq_dv_ah_per_v, b.dq_dv_ah_per_v, atol=1e-9)
    for field in ("peak_voltage_v", "peak_height_ah_per_v", "peak_width_v", "area_ah"):
        assert getattr(a, field) == pytest.approx(getattr(b, field), abs=1e-9)


@pytest.mark.parametrize("native", [False, True])
def test_time_and_resistance_helpers(native: bool) -> None:
    if native and not curves.using_native_curves():
        pytest.skip("C++ extension not built")
    t = np.array([0, 10, 20, 30, 40.0])
    v = np.array([3.5, 3.7, 3.9, 4.1, 4.2])
    assert curves.time_between_voltages(t, v, 3.6, 4.0, native=native) == pytest.approx(
        20
    )
    assert curves.time_between_voltages(t, v, 3.6, 4.3, native=native) is None
    i = np.array([0, 0, -2, -2, -2.0])
    assert curves.estimate_dcir(
        i, np.array([4.19, 4.19, 4.0, 3.99, 3.98]), native=native
    ) == pytest.approx(0.095)
    assert curves.estimate_dcir(i, v, 3.0, native=native) is None


@pytest.mark.parametrize("native", [False, True])
def test_bad_input_is_rejected_the_same_way(native: bool) -> None:
    if native and not curves.using_native_curves():
        pytest.skip("C++ extension not built")
    v, q = np.array([3.5, 3.6, 3.7, 3.8]), np.array([0, 1, 2, 3.0])
    with pytest.raises(ValueError):
        curves.incremental_capacity(v, q[:2], native=native)
    with pytest.raises(ValueError):
        curves.incremental_capacity(v, q, smooth_window=4, native=native)
    with pytest.raises(ValueError):
        curves.incremental_capacity(np.array([3.7] * 4), q, native=native)
    with pytest.raises(ValueError):
        curves.incremental_capacity(np.array([3.5, np.nan, 3.7, 3.8]), q, native=native)
    with pytest.raises(ValueError):
        curves.time_between_voltages(
            np.array([0, 1, 1, 2.0]), v, 3.5, 3.7, native=native
        )


def test_charge_features_come_from_the_constant_current_phase_only() -> None:
    from argus.battery.curve_features import charge_features

    v_curve, q_curve = charge(3.8, 3.0)
    t = np.arange(800) * 3.0
    # Constant current makes charge linear in time; voltage follows Q(V).
    q_time = np.linspace(0, q_curve[-1], 800)
    v = np.interp(q_time, q_curve, v_curve)
    current = np.full(800, 1.5)
    current[:2] = 0.0
    current[790:] = 0.3  # constant-voltage tail must be ignored
    features = charge_features(
        {"Time": t, "Voltage_measured": v, "Current_measured": current}
    )
    assert features["ica_peak_v"] == pytest.approx(3.8, abs=0.05)
    assert features["rise_time_s"] is not None and features["rise_time_s"] > 0
    empty = charge_features(
        {"Time": t, "Voltage_measured": v, "Current_measured": current * 0}
    )
    assert empty["ica_peak_v"] is None
