import numpy as np

from argus.simulator import AssetSimulator, AssetType, FaultType
from argus.simulator.telemetry_simulator import SENSOR_COLUMNS


def test_healthy_run_shape_and_columns():
    sim = AssetSimulator(seed=1)
    run = sim.generate_run(
        "A1", AssetType.MARINE_CONVERTER, n_steps=120, fault_type=FaultType.NONE
    )
    assert len(run) == 120
    for col in SENSOR_COLUMNS:
        assert col in run.columns
    assert (run["fault_label"] == 0).all()


def test_faulty_run_severity_increases_and_label_flips():
    sim = AssetSimulator(seed=2)
    run = sim.generate_run(
        "A2",
        AssetType.UAV_PDU,
        n_steps=200,
        fault_type=FaultType.OVERHEATING,
        fault_onset_frac=0.5,
    )
    assert run["fault_severity"].iloc[-1] > run["fault_severity"].iloc[0]
    assert (
        run["fault_severity"].is_monotonic_increasing
        or run["fault_severity"].diff().fillna(0).ge(-1e-9).all()
    )
    assert run["fault_label"].iloc[-1] == 1
    assert run["fault_label"].iloc[0] == 0
    # Overheating should raise temperature toward the end of the run.
    assert run["temperature_c"].iloc[-5:].mean() > run["temperature_c"].iloc[:5].mean()


def test_waveform_shape_and_finiteness():
    sim = AssetSimulator(seed=3)
    wave = sim.generate_waveform(
        AssetType.MARINE_CONVERTER,
        FaultType.BEARING_WEAR,
        severity=0.7,
        n_samples=1024,
        sample_rate_hz=2000.0,
    )
    assert wave.shape == (1024,)
    assert np.all(np.isfinite(wave))


def test_default_fleet_has_both_asset_types():
    sim = AssetSimulator(seed=4)
    fleet = sim.default_fleet()
    types = {t for _, t in fleet}
    assert AssetType.MARINE_CONVERTER in types
    assert AssetType.UAV_PDU in types
