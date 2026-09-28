"""Feature extraction front-end.

Prefers the compiled ``argus_core`` C++ extension (built from
``cpp_core/``, see the project README) for speed; transparently falls back
to an equivalent pure-NumPy implementation so the ML pipeline still runs
end to end on a machine where the native extension has not been built
(e.g. a plain ``pip install`` without a C++ toolchain).

Both paths produce feature vectors in the exact same order, defined once
here as ``FEATURE_NAMES``, so trained models are portable between the two
backends.
"""

from __future__ import annotations

import numpy as np

FEATURE_NAMES: list[str] = [
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

try:
    import argus_core as _native  # type: ignore

    _HAVE_NATIVE = True
except ImportError:  # pragma: no cover - exercised when the extension isn't built
    _native = None
    _HAVE_NATIVE = False


def using_native_core() -> bool:
    """True if the compiled C++ extension is being used instead of the
    NumPy fallback."""
    return _HAVE_NATIVE


def _validate_input(samples: np.ndarray, sample_rate_hz: float) -> np.ndarray:
    samples = np.asarray(samples, dtype=np.float64)
    if samples.ndim != 1:
        raise ValueError("expected a 1-D array of samples")
    if samples.size == 0:
        raise ValueError("extract_features: empty sample window")
    if not np.isfinite(samples).all():
        raise ValueError("samples must contain only finite values")
    if not np.isfinite(sample_rate_hz) or sample_rate_hz <= 0:
        raise ValueError("sample_rate_hz must be finite and > 0")
    return samples


def _extract_features_numpy(samples: np.ndarray, sample_rate_hz: float) -> np.ndarray:
    samples = _validate_input(samples, sample_rate_hz)
    n = samples.size

    mean = samples.mean()
    rms = np.sqrt(np.mean(samples**2))
    peak = np.max(np.abs(samples))
    crest_factor = peak / rms if rms > 1e-12 else 0.0

    centered = samples - mean
    m2 = np.mean(centered**2)
    m3 = np.mean(centered**3)
    m4 = np.mean(centered**4)
    std_dev = np.sqrt(m2)
    skewness = m3 / m2**1.5 if m2 > 1e-12 else 0.0
    kurtosis = (m4 / m2**2) - 3.0 if m2 > 1e-12 else 0.0

    signs = np.sign(centered)
    zero_crossings = np.sum(signs[1:] * signs[:-1] < 0)
    zero_crossing_rate = zero_crossings / n

    # Shared native/NumPy contract: no window function, zero-pad to the next
    # power of two, normalize by padded length, exclude DC from spectral
    # features. Changing backends must not change a trained model's inputs.
    padded = 1 << (n - 1).bit_length()
    spectrum = np.abs(np.fft.rfft(samples, n=padded)) / padded
    freqs = np.arange(spectrum.size) * (sample_rate_hz / padded)
    if len(spectrum) > 1:
        spectrum_no_dc = spectrum[1:]
        freqs_no_dc = freqs[1:]
        best_magnitude = float(spectrum_no_dc.max())
        if best_magnitude > 1e-12:
            # First effectively tied peak matches the native FFT's policy.
            best_bin = int(np.argmax(spectrum_no_dc >= best_magnitude * (1 - 1e-12)))
            dominant_frequency_hz = float(freqs_no_dc[best_bin])
        else:
            dominant_frequency_hz = 0.0
        mag_sum = spectrum_no_dc.sum()
        spectral_centroid_hz = (
            float((spectrum_no_dc * freqs_no_dc).sum() / mag_sum)
            if mag_sum > 1e-12
            else 0.0
        )
        spectral_energy = float((spectrum_no_dc**2).sum())
    else:
        dominant_frequency_hz = 0.0
        spectral_centroid_hz = 0.0
        spectral_energy = 0.0

    return np.array(
        [
            mean,
            rms,
            std_dev,
            peak,
            crest_factor,
            kurtosis,
            skewness,
            zero_crossing_rate,
            dominant_frequency_hz,
            spectral_centroid_hz,
            spectral_energy,
        ],
        dtype=np.float64,
    )


def extract_features(samples: np.ndarray, sample_rate_hz: float) -> np.ndarray:
    """Extract the 11-dimensional statistical + spectral feature vector
    (see ``FEATURE_NAMES``) from one finite, non-empty 1-D waveform window.

    The sample rate must be finite and positive. FFT input is zero-padded to
    the next power of two in both backends. A single sample has no AC energy;
    spectra with no non-DC energy return a dominant frequency of zero.
    """
    if _HAVE_NATIVE:
        samples = _validate_input(samples, sample_rate_hz)
        fv = _native.extract_features(samples, sample_rate_hz)
        return np.asarray(fv.to_array(), dtype=np.float64)
    return _extract_features_numpy(samples, sample_rate_hz)
