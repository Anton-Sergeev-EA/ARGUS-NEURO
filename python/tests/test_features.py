import numpy as np

from argus.features import extract_features


def test_dc_signal_features():
    samples = np.full(512, 3.0)
    feats = extract_features(samples, sample_rate_hz=1000.0)
    names = ["mean", "rms", "std_dev", "peak", "crest_factor", "kurtosis",
              "skewness", "zero_crossing_rate", "dominant_frequency_hz",
              "spectral_centroid_hz", "spectral_energy"]
    values = dict(zip(names, feats))
    assert np.isclose(values["mean"], 3.0, atol=1e-6)
    assert np.isclose(values["rms"], 3.0, atol=1e-3)
    assert np.isclose(values["std_dev"], 0.0, atol=1e-3)
    assert values["zero_crossing_rate"] == 0.0


def test_sine_wave_dominant_frequency_matches():
    sample_rate = 2048.0
    target_freq = 128.0
    n = 2048
    t = np.arange(n) / sample_rate
    samples = np.sin(2 * np.pi * target_freq * t)

    feats = extract_features(samples, sample_rate)
    dominant_freq = feats[8]  # index of dominant_frequency_hz
    assert abs(dominant_freq - target_freq) < 2.0


def test_feature_vector_length():
    samples = np.random.default_rng(0).normal(size=256)
    feats = extract_features(samples, 1000.0)
    assert feats.shape == (11,)
