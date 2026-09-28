#include "argus_core/signal_features.hpp"

#include <algorithm>
#include <bit>
#include <cmath>
#include <limits>
#include <numbers>
#include <numeric>
#include <stdexcept>

namespace argus_core {

std::array<double, 11> FeatureVector::to_array() const noexcept {
    return {mean,       rms,
            std_dev,    peak,
            crest_factor, kurtosis,
            skewness,   zero_crossing_rate,
            dominant_frequency_hz, spectral_centroid_hz,
            spectral_energy};
}

std::vector<std::string> FeatureVector::field_names() {
    return {"mean",         "rms",
            "std_dev",      "peak",
            "crest_factor", "kurtosis",
            "skewness",     "zero_crossing_rate",
            "dominant_frequency_hz", "spectral_centroid_hz",
            "spectral_energy"};
}

namespace {

std::size_t next_pow2(std::size_t n) {
    if (n <= 1) return 1;
    const auto bits = std::bit_width(n - 1);
    if (bits >= std::numeric_limits<std::size_t>::digits) {
        throw std::length_error("sample window is too large for FFT padding");
    }
    return std::size_t{1} << bits;
}

void validate_samples(std::span<const double> samples) {
    if (samples.empty()) {
        throw std::invalid_argument("expected a non-empty sample window");
    }
    if (!std::all_of(samples.begin(), samples.end(), [](double value) {
            return std::isfinite(value);
        })) {
        throw std::invalid_argument("samples must contain only finite values");
    }
}

}  // namespace

void fft_radix2(std::vector<std::complex<double>>& data) {
    const std::size_t n = data.size();
    if (n == 0) return;
    if ((n & (n - 1)) != 0) {
        throw std::invalid_argument("fft_radix2: size must be a power of two");
    }

    // Bit-reversal permutation.
    for (std::size_t i = 1, j = 0; i < n; ++i) {
        std::size_t bit = n >> 1;
        for (; j & bit; bit >>= 1) {
            j ^= bit;
        }
        j ^= bit;
        if (i < j) std::swap(data[i], data[j]);
    }

    // Iterative Cooley-Tukey butterflies.
    for (std::size_t len = 2; len <= n; len <<= 1) {
        const double angle = -2.0 * std::numbers::pi / static_cast<double>(len);
        const std::complex<double> wlen(std::cos(angle), std::sin(angle));
        for (std::size_t i = 0; i < n; i += len) {
            std::complex<double> w(1.0, 0.0);
            for (std::size_t k = 0; k < len / 2; ++k) {
                const std::complex<double> u = data[i + k];
                const std::complex<double> v = data[i + k + len / 2] * w;
                data[i + k] = u + v;
                data[i + k + len / 2] = u - v;
                w *= wlen;
            }
        }
    }
}

std::vector<double> magnitude_spectrum(std::span<const double> input) {
    validate_samples(input);
    const std::size_t padded = next_pow2(input.size());
    std::vector<std::complex<double>> buffer(padded, {0.0, 0.0});
    for (std::size_t i = 0; i < input.size(); ++i) {
        buffer[i] = {input[i], 0.0};
    }
    fft_radix2(buffer);

    const std::size_t half = padded / 2 + 1;
    std::vector<double> magnitude(half);
    for (std::size_t i = 0; i < half; ++i) {
        magnitude[i] = std::abs(buffer[i]) / static_cast<double>(padded);
    }
    return magnitude;
}

FeatureVector extract_features(std::span<const double> samples,
                                double sample_rate_hz) {
    validate_samples(samples);
    if (!std::isfinite(sample_rate_hz) || sample_rate_hz <= 0.0) {
        throw std::invalid_argument("sample_rate_hz must be finite and > 0");
    }

    const auto n = static_cast<double>(samples.size());

    FeatureVector f;

    // --- Time-domain statistics ---
    const double sum = std::accumulate(samples.begin(), samples.end(), 0.0);
    f.mean = sum / n;

    double sq_sum = 0.0, abs_peak = 0.0;
    for (const double v : samples) {
        sq_sum += v * v;
        abs_peak = std::max(abs_peak, std::abs(v));
    }
    f.rms = std::sqrt(sq_sum / n);
    f.peak = abs_peak;
    f.crest_factor = (f.rms > 1e-12) ? f.peak / f.rms : 0.0;

    double m2 = 0.0, m3 = 0.0, m4 = 0.0;
    for (const double v : samples) {
        const double d = v - f.mean;
        m2 += d * d;
        m3 += d * d * d;
        m4 += d * d * d * d;
    }
    m2 /= n;
    m3 /= n;
    m4 /= n;
    f.std_dev = std::sqrt(m2);
    f.skewness = (m2 > 1e-12) ? m3 / std::pow(m2, 1.5) : 0.0;
    // Excess kurtosis (0 == Gaussian), the standard convention for
    // impulsiveness-based fault indicators (bearing wear, arcing, etc).
    f.kurtosis = (m2 > 1e-12) ? (m4 / (m2 * m2)) - 3.0 : 0.0;

    std::size_t crossings = 0;
    for (std::size_t i = 1; i < samples.size(); ++i) {
        if ((samples[i - 1] - f.mean) * (samples[i] - f.mean) < 0.0) {
            ++crossings;
        }
    }
    f.zero_crossing_rate = static_cast<double>(crossings) / n;

    // --- Frequency-domain features ---
    const auto spectrum = magnitude_spectrum(samples);
    const std::size_t padded = next_pow2(samples.size());
    const double bin_hz = sample_rate_hz / static_cast<double>(padded);

    double energy = 0.0, weighted_freq = 0.0, best_mag = 0.0;
    std::size_t best_bin = 0;
    // Skip DC bin (index 0) when looking for the dominant oscillation.
    for (std::size_t bin = 1; bin < spectrum.size(); ++bin) {
        const double mag = spectrum[bin];
        energy += mag * mag;
        weighted_freq += mag * static_cast<double>(bin) * bin_hz;
        best_mag = std::max(best_mag, mag);
    }
    const double mag_sum = std::accumulate(spectrum.begin() + 1, spectrum.end(), 0.0);

    // Ignore numerical noise and choose the lowest bin for effectively tied
    // peaks, so equivalent FFT implementations produce the same frequency.
    if (best_mag > 1e-12) {
        for (std::size_t bin = 1; bin < spectrum.size(); ++bin) {
            if (spectrum[bin] >= best_mag * (1.0 - 1e-12)) {
                best_bin = bin;
                break;
            }
        }
    }

    f.dominant_frequency_hz = static_cast<double>(best_bin) * bin_hz;
    f.spectral_centroid_hz = (mag_sum > 1e-12) ? weighted_freq / mag_sum : 0.0;
    f.spectral_energy = energy;

    return f;
}

}  // namespace argus_core
