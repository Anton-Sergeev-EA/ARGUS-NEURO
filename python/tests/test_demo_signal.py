import numpy as np

from argus.demo_signal import run_demo


def test_demo_keeps_dominant_tone_but_exposes_added_energy() -> None:
    report = run_demo()
    healthy = report["cases"]["healthy"]
    changed = report["cases"]["added_250hz"]
    assert report["source"] == "synthetic"
    assert report["backend_matches_numpy"] is True
    assert healthy["dominant_frequency_hz"] == 50.0
    assert changed["dominant_frequency_hz"] == 50.0
    assert changed["rms"] > healthy["rms"] * 1.2
    assert changed["spectral_energy"] > healthy["spectral_energy"] * 1.5
    for case in (healthy, changed):
        assert len(case) == 11
        assert np.isfinite(list(case.values())).all()
