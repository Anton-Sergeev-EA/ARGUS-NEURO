"""Synthetic telemetry generator for power-electronics assets.

Two asset classes stand in for the shared ground between the two
industrial domains this project targets:

* ``MARINE_CONVERTER`` -- a shipboard frequency converter / thruster drive
  (three-phase power stage feeding a steering or propulsion motor).
* ``UAV_PDU``           -- an unmanned-aircraft power distribution unit
  feeding the flight controller and actuators from the battery pack.

Both are, electrically, the same kind of object: a power-electronic stage
with voltage, current, temperature, vibration and frequency telemetry, that
degrades in a handful of well-known ways before it fails. Modelling them
with one simulator (and, later, one ML/DL pipeline) is the point of this
project -- a single health-monitoring stack that generalizes across both
fleets instead of two bespoke ones.
"""

from __future__ import annotations

import enum
import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd


class AssetType(str, enum.Enum):
    MARINE_CONVERTER = "MARINE_CONVERTER"
    UAV_PDU = "UAV_PDU"


class FaultType(str, enum.Enum):
    NONE = "NONE"
    OVERHEATING = "OVERHEATING"               # cooling degradation / overload
    BEARING_WEAR = "BEARING_WEAR"              # rising broadband vibration
    VOLTAGE_SAG = "VOLTAGE_SAG"                # weakening supply / connector
    FREQUENCY_DRIFT = "FREQUENCY_DRIFT"        # control-loop / clock fault
    INSULATION_DEGRADATION = "INSULATION_DEGRADATION"  # leakage current rise


@dataclass(frozen=True)
class _NominalProfile:
    """Steady-state operating point and sensor noise for an asset type."""

    voltage_v: float
    current_a: float
    temperature_c: float
    vibration_g: float
    frequency_hz: float
    load_factor: float
    noise_std: dict = field(default_factory=dict)


_PROFILES: dict[AssetType, _NominalProfile] = {
    AssetType.MARINE_CONVERTER: _NominalProfile(
        voltage_v=400.0,
        current_a=120.0,
        temperature_c=55.0,
        vibration_g=0.15,
        frequency_hz=50.0,
        load_factor=0.65,
        noise_std=dict(voltage_v=1.5, current_a=2.0, temperature_c=0.4,
                        vibration_g=0.01, frequency_hz=0.03, load_factor=0.03),
    ),
    AssetType.UAV_PDU: _NominalProfile(
        voltage_v=48.0,
        current_a=35.0,
        temperature_c=42.0,
        vibration_g=0.35,
        frequency_hz=400.0,
        load_factor=0.55,
        noise_std=dict(voltage_v=0.4, current_a=1.2, temperature_c=0.6,
                        vibration_g=0.03, frequency_hz=0.5, load_factor=0.05),
    ),
}

# Per-sensor column order shared by every consumer (simulator, features,
# models, API, dashboard) so a "window" always means the same thing.
SENSOR_COLUMNS: list[str] = [
    "voltage_v",
    "current_a",
    "temperature_c",
    "vibration_g",
    "frequency_hz",
    "load_factor",
]


def fault_progression(n_steps: int, onset_frac: float) -> np.ndarray:
    """A smooth 0 -> 1 degradation ramp starting at ``onset_frac`` of the run
    and reaching 1.0 (failure) at the final step -- used to scale fault
    severity and to derive ground-truth remaining-useful-life labels."""
    onset_step = int(n_steps * onset_frac)
    ramp = np.zeros(n_steps)
    tail = n_steps - onset_step
    if tail > 0:
        # Smoothstep-ish ramp: slow start, accelerating decay -> failure.
        x = np.linspace(0.0, 1.0, tail)
        ramp[onset_step:] = x ** 1.6
    return ramp


class AssetSimulator:
    """Generates realistic multivariate telemetry runs and raw waveforms
    for the two supported asset classes, with optional injected faults."""

    def __init__(self, seed: int | None = None):
        self._rng = np.random.default_rng(seed)

    # ------------------------------------------------------------------
    # Multi-sensor low-rate telemetry (one row per control-cycle sample)
    # ------------------------------------------------------------------
    def generate_run(
        self,
        asset_id: str,
        asset_type: AssetType,
        n_steps: int = 600,
        dt_seconds: float = 5.0,
        fault_type: FaultType = FaultType.NONE,
        fault_onset_frac: float = 0.55,
    ) -> pd.DataFrame:
        """Simulate one asset's telemetry history.

        When ``fault_type`` is not NONE, a degradation trend is injected
        starting at ``fault_onset_frac`` of the run and reaching failure at
        the last sample; ``rul_steps`` then counts down to 0 at failure and
        ``fault_label`` flips to 1 once the fault becomes detectable
        (severity > 0.15), which is the ground truth used to score the
        anomaly detectors.
        """
        profile = _PROFILES[asset_type]
        severity = fault_progression(n_steps, fault_onset_frac) if fault_type != FaultType.NONE else np.zeros(n_steps)

        t = np.arange(n_steps) * dt_seconds
        rng = self._rng

        voltage = np.full(n_steps, profile.voltage_v) + rng.normal(0, profile.noise_std["voltage_v"], n_steps)
        current = np.full(n_steps, profile.current_a) + rng.normal(0, profile.noise_std["current_a"], n_steps)
        temperature = np.full(n_steps, profile.temperature_c) + rng.normal(0, profile.noise_std["temperature_c"], n_steps)
        vibration = np.full(n_steps, profile.vibration_g) + rng.normal(0, profile.noise_std["vibration_g"], n_steps)
        frequency = np.full(n_steps, profile.frequency_hz) + rng.normal(0, profile.noise_std["frequency_hz"], n_steps)
        load = np.clip(
            profile.load_factor + 0.12 * np.sin(2 * math.pi * t / (n_steps * dt_seconds / 3))
            + rng.normal(0, profile.noise_std["load_factor"], n_steps),
            0.05, 1.0,
        )

        if fault_type == FaultType.OVERHEATING:
            temperature += severity * (profile.temperature_c * 0.9)
            current += severity * (profile.current_a * 0.25)
        elif fault_type == FaultType.BEARING_WEAR:
            vibration += severity * (profile.vibration_g * 6.0)
            vibration += severity * rng.normal(0, profile.vibration_g * 1.5, n_steps)
        elif fault_type == FaultType.VOLTAGE_SAG:
            voltage -= severity * (profile.voltage_v * 0.22)
            current += severity * (profile.current_a * 0.15)
        elif fault_type == FaultType.FREQUENCY_DRIFT:
            frequency += severity * (profile.frequency_hz * 0.06) * np.sign(rng.normal(size=n_steps))
        elif fault_type == FaultType.INSULATION_DEGRADATION:
            current += severity * (profile.current_a * 0.35)
            temperature += severity * (profile.temperature_c * 0.3)

        detectable = severity > 0.15
        rul_steps = np.where(
            fault_type == FaultType.NONE,
            n_steps,  # censored / "healthy for the foreseeable horizon"
            np.maximum(n_steps - 1 - np.arange(n_steps), 0),
        )

        return pd.DataFrame({
            "t_s": t,
            "asset_id": asset_id,
            "asset_type": asset_type.value,
            "voltage_v": voltage,
            "current_a": current,
            "temperature_c": temperature,
            "vibration_g": np.clip(vibration, 0.0, None),
            "frequency_hz": frequency,
            "load_factor": load,
            "fault_type": fault_type.value,
            "fault_label": detectable.astype(int),
            "fault_severity": severity,
            "rul_steps": rul_steps,
        })

    # ------------------------------------------------------------------
    # Single high-rate raw waveform (for the C++ spectral feature core)
    # ------------------------------------------------------------------
    def generate_waveform(
        self,
        asset_type: AssetType,
        fault_type: FaultType = FaultType.NONE,
        severity: float = 0.0,
        n_samples: int = 2048,
        sample_rate_hz: float = 2000.0,
    ) -> np.ndarray:
        """Simulate one raw current/vibration waveform window.

        Healthy assets look like a clean fundamental tone plus a little
        harmonic content and noise; degradation modes inject the spectral
        signatures a real condition-monitoring system would look for
        (rising broadband energy for bearing wear, sub/inter-harmonics for
        electrical faults, etc).
        """
        profile = _PROFILES[asset_type]
        fundamental = profile.frequency_hz
        t = np.arange(n_samples) / sample_rate_hz
        rng = self._rng

        signal = np.sin(2 * math.pi * fundamental * t)
        signal += 0.05 * np.sin(2 * math.pi * 3 * fundamental * t)  # 3rd harmonic
        signal += 0.02 * np.sin(2 * math.pi * 5 * fundamental * t)  # 5th harmonic
        signal += rng.normal(0, 0.02, n_samples)

        severity = float(np.clip(severity, 0.0, 1.0))
        if fault_type == FaultType.BEARING_WEAR:
            signal += severity * 0.6 * rng.normal(0, 1.0, n_samples)  # broadband energy
            signal += severity * 0.3 * np.sin(2 * math.pi * fundamental * 2.7 * t)
        elif fault_type == FaultType.FREQUENCY_DRIFT:
            drift = severity * fundamental * 0.05
            signal = np.sin(2 * math.pi * (fundamental + drift) * t) + rng.normal(0, 0.02, n_samples)
        elif fault_type == FaultType.INSULATION_DEGRADATION:
            signal += severity * 0.25 * np.sin(2 * math.pi * fundamental * 0.5 * t)  # sub-harmonic leakage
        elif fault_type == FaultType.VOLTAGE_SAG:
            envelope = 1.0 - severity * 0.3
            signal *= envelope
        elif fault_type == FaultType.OVERHEATING:
            signal += severity * 0.15 * rng.normal(0, 1.0, n_samples)

        return signal.astype(np.float64)

    # ------------------------------------------------------------------
    def default_fleet(self) -> list[tuple[str, AssetType]]:
        """A representative mixed fleet: shipboard converters/drives plus
        a UAV squadron's power distribution units -- used by the demo API
        and the dashboard."""
        return [
            ("SHIP-CONV-01", AssetType.MARINE_CONVERTER),
            ("SHIP-CONV-02", AssetType.MARINE_CONVERTER),
            ("SHIP-THRUST-01", AssetType.MARINE_CONVERTER),
            ("UAV-PDU-07", AssetType.UAV_PDU),
            ("UAV-PDU-11", AssetType.UAV_PDU),
            ("UAV-PDU-14", AssetType.UAV_PDU),
        ]
