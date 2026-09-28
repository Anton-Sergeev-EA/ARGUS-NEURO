// ARGUS-NEURO :: cpp_core
// High-performance signal feature extraction for power-electronics telemetry.
//
// Designed to run on constrained edge hardware (shipboard control cabinets,
// UAV onboard computers) where the deep models cannot always live, so the
// heavy numeric work (statistics + spectral analysis) is done once in C++
// and reused both by the native pipeline and, via pybind11, by Python.

#pragma once

#include <array>
#include <complex>
#include <concepts>
#include <cstddef>
#include <span>
#include <string>
#include <vector>

namespace argus_core {

/// A flat set of scalar features describing one telemetry window.
/// Kept as a plain struct (not a map) so it is cheap to build, cheap to
/// copy across the pybind11 boundary, and trivial to turn into a fixed
/// width feature vector for the ML layer.
struct FeatureVector {
    double mean = 0.0;
    double rms = 0.0;
    double std_dev = 0.0;
    double peak = 0.0;
    double crest_factor = 0.0;   // peak / rms  -- classic fault indicator
    double kurtosis = 0.0;       // impulsiveness (bearing/insulation faults)
    double skewness = 0.0;
    double zero_crossing_rate = 0.0;
    double dominant_frequency_hz = 0.0;
    double spectral_centroid_hz = 0.0;
    double spectral_energy = 0.0;

    /// Fixed order used everywhere a plain numeric vector is required
    /// (ML feature matrices, ONNX tensors, etc).
    [[nodiscard]] std::array<double, 11> to_array() const noexcept;

    [[nodiscard]] static std::vector<std::string> field_names();
};

/// Concept: anything that looks like a contiguous range of floating point
/// samples. Lets extract_features() accept std::vector<double>,
/// std::array<double, N>, or a raw span without duplicating the API.
template <typename R>
concept SampleRange = requires(R r) {
    { std::span(r) } -> std::convertible_to<std::span<const double>>;
};

/// Extract the full statistical + spectral feature set from a single
/// telemetry window.
///
/// @param samples     Uniformly-sampled sensor values (e.g. current or
///                    vibration waveform) for one window.
/// @param sample_rate_hz  Sampling rate used to acquire `samples`, needed to
///                    convert FFT bins to physical frequencies (Hz).
/// @throws std::invalid_argument for empty/non-finite samples or a sampling
///                    rate that is not finite and positive.
FeatureVector extract_features(std::span<const double> samples,
                                double sample_rate_hz);

template <SampleRange R>
FeatureVector extract_features(const R& samples, double sample_rate_hz) {
    return extract_features(std::span<const double>(samples), sample_rate_hz);
}

/// In-place, iterative radix-2 Cooley-Tukey FFT.
///
/// `data.size()` must be a power of two. Provided directly (rather than
/// hidden inside extract_features) so the dashboard/backend can also request
/// raw spectra for visualization, not just summary features.
void fft_radix2(std::vector<std::complex<double>>& data);

/// Zero-pads `input` up to the next power-of-two length,
/// runs fft_radix2 and returns the single-sided magnitude spectrum
/// (length = padded_size / 2 + 1), normalized by padded_size. No samples are
/// truncated. Empty/non-finite input is rejected. A single sample has only DC.
std::vector<double> magnitude_spectrum(std::span<const double> input);

}  // namespace argus_core
