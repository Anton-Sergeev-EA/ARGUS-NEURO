from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pytest

from argus.features import extract_features
from argus.features.extraction import FEATURE_NAMES, _extract_features_numpy


def test_dc_signal_features() -> None:
    samples = np.full(512, 3.0)
    feats = extract_features(samples, sample_rate_hz=1000.0)
    names = [
        "mean",
        "rms",
        "std_dev",
        "peak",
        "crest_factor",
        "kurtosis",
        "skewness",
        "zero_crossing_rate",
        "dominant_frequency_hz",
        "spectral_centroid_hz",
        "spectral_energy",
    ]
    values = dict(zip(names, feats))
    assert np.isclose(values["mean"], 3.0, atol=1e-6)
    assert np.isclose(values["rms"], 3.0, atol=1e-3)
    assert np.isclose(values["std_dev"], 0.0, atol=1e-3)
    assert values["zero_crossing_rate"] == 0.0


def test_sine_wave_dominant_frequency_matches() -> None:
    sample_rate = 2048.0
    target_freq = 128.0
    n = 2048
    t = np.arange(n) / sample_rate
    samples = np.sin(2 * np.pi * target_freq * t)

    feats = extract_features(samples, sample_rate)
    dominant_freq = feats[8]  # index of dominant_frequency_hz
    assert abs(dominant_freq - target_freq) < 2.0


def test_feature_vector_length() -> None:
    samples = np.random.default_rng(0).normal(size=256)
    feats = extract_features(samples, 1000.0)
    assert feats.shape == (11,)


@pytest.mark.parametrize("length", [1, 2, 3, 7, 31, 255, 1000, 1024])
def test_native_and_numpy_features_match(length: int) -> None:
    native = pytest.importorskip("argus_core")
    samples = np.random.default_rng(length).normal(size=length)
    expected = _extract_features_numpy(samples, 2048.0)
    actual = np.asarray(native.extract_features(samples, 2048.0).to_array())
    np.testing.assert_allclose(actual, expected, rtol=1e-10, atol=1e-10)
    assert native.FeatureVector.field_names() == FEATURE_NAMES
    padded = 1 << (length - 1).bit_length()
    np.testing.assert_allclose(
        native.magnitude_spectrum(samples),
        np.abs(np.fft.rfft(samples, n=padded)) / padded,
        rtol=1e-10,
        atol=1e-10,
    )


@pytest.mark.parametrize("step", [2, -1, -3])
def test_native_strided_arrays(step: int) -> None:
    native = pytest.importorskip("argus_core")
    samples = np.arange(100, dtype=np.float64)[::step]
    assert not samples.flags.c_contiguous
    expected = _extract_features_numpy(samples, 1000.0)
    np.testing.assert_allclose(
        native.extract_features(samples, 1000.0).to_array(),
        expected,
        rtol=1e-10,
        atol=1e-10,
    )
    np.testing.assert_allclose(
        native.magnitude_spectrum(samples), native.magnitude_spectrum(samples.copy())
    )


@pytest.mark.parametrize("value", [0.0, 3.0, -2.0])
def test_single_sample_is_finite(value: float) -> None:
    samples = np.array([value])
    for extractor in (extract_features, _extract_features_numpy):
        features = extractor(samples, 1000.0)
        assert np.isfinite(features).all()
        assert features[0] == value
        assert features[1] == abs(value)
        np.testing.assert_array_equal(features[8:], [0.0, 0.0, 0.0])


@pytest.mark.parametrize("length", [1, 7, 256])
def test_silent_window_has_no_dominant_frequency(length: int) -> None:
    for extractor in (extract_features, _extract_features_numpy):
        np.testing.assert_array_equal(extractor(np.zeros(length), 1000.0), np.zeros(11))


def test_tied_spectral_peaks_choose_lowest_frequency() -> None:
    native = pytest.importorskip("argus_core")
    # A delayed unit impulse has equal magnitude in every frequency bin.
    samples = np.zeros(32)
    samples[7] = 1.0
    expected = _extract_features_numpy(samples, 1024.0)
    assert expected[8] == 32.0
    np.testing.assert_allclose(
        native.extract_features(samples, 1024.0).to_array(), expected
    )


@pytest.mark.parametrize("sample_rate", [0.0, -1000.0, np.nan, np.inf, -np.inf])
def test_invalid_sample_rate(sample_rate: float) -> None:
    for extractor in (extract_features, _extract_features_numpy):
        with pytest.raises(ValueError, match="sample_rate_hz"):
            extractor(np.ones(16), sample_rate)


@pytest.mark.parametrize(
    "samples",
    [
        np.array([]),
        np.array(1.0),
        np.ones((2, 3)),
        np.array([1.0, np.nan]),
        np.array([np.inf]),
        np.array([-np.inf]),
    ],
)
def test_invalid_samples(samples: np.ndarray) -> None:
    for extractor in (extract_features, _extract_features_numpy):
        with pytest.raises(ValueError):
            extractor(samples, 1000.0)


def test_direct_native_rejects_invalid_inputs() -> None:
    native = pytest.importorskip("argus_core")
    for samples in (
        np.array([]),
        np.array(1.0),
        np.ones((2, 3)),
        np.array([np.nan]),
        np.array([np.inf]),
    ):
        with pytest.raises(ValueError):
            native.extract_features(samples, 1000.0)
        with pytest.raises(ValueError):
            native.magnitude_spectrum(samples)
    for rate in (0.0, -1.0, np.nan, np.inf):
        with pytest.raises(ValueError):
            native.extract_features(np.ones(16), rate)


def test_native_parallel_calls_are_independent() -> None:
    native = pytest.importorskip("argus_core")
    windows = [
        np.random.default_rng(seed).normal(size=1000 + seed) for seed in range(8)
    ]

    def run(samples: np.ndarray) -> np.ndarray:
        return np.asarray(native.extract_features(samples, 2048.0).to_array())

    with ThreadPoolExecutor(max_workers=4) as executor:
        actual = list(executor.map(run, windows))
    expected = [_extract_features_numpy(samples, 2048.0) for samples in windows]
    np.testing.assert_allclose(actual, expected, rtol=1e-10, atol=1e-10)


def test_native_accepts_unaligned_contiguous_array() -> None:
    native = pytest.importorskip("argus_core")
    samples = np.ndarray((16,), dtype=np.float64, buffer=bytearray(129), offset=1)
    samples[:] = np.arange(16)
    assert samples.flags.c_contiguous and not samples.flags.aligned
    np.testing.assert_allclose(
        native.extract_features(samples, 1000.0).to_array(),
        _extract_features_numpy(samples, 1000.0),
    )
