// Lightweight, dependency-free sanity checks for the signal core.
// Intentionally avoids pulling in a test framework so the native
// build stays trivial in any environment (no network fetch required).

#include <cmath>
#include <complex>
#include <iostream>
#include <limits>
#include <numbers>
#include <stdexcept>
#include <vector>

#include "argus_core/signal_features.hpp"

namespace {

// Unlike assert(), this remains active in optimized Release builds.
void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}

template <typename Function>
void require_invalid_argument(Function function) {
    try {
        function();
    } catch (const std::invalid_argument&) {
        return;
    }
    throw std::runtime_error("expected std::invalid_argument");
}

bool close(double a, double b, double tol = 1e-6) {
    return std::abs(a - b) <= tol;
}

void test_constant_signal_rms_and_zero_crossings() {
    std::vector<double> samples(256, 5.0);
    const auto f = argus_core::extract_features(samples, 1000.0);
    require(close(f.mean, 5.0), "constant mean");
    require(close(f.rms, 5.0, 1e-3), "constant RMS");
    require(close(f.std_dev, 0.0, 1e-3), "constant standard deviation");
    require(f.zero_crossing_rate == 0.0, "constant zero crossings");
    require(f.dominant_frequency_hz == 0.0, "DC has no dominant oscillation");
    std::cout << "[PASS] constant_signal_rms_and_zero_crossings\n";
}

void test_sine_wave_dominant_frequency() {
    constexpr double sample_rate = 2048.0;
    constexpr double target_freq = 128.0;  // Hz, exact FFT bin at N=2048
    constexpr std::size_t n = 2048;

    std::vector<double> samples(n);
    for (std::size_t i = 0; i < n; ++i) {
        samples[i] = std::sin(2.0 * std::numbers::pi * target_freq *
                               static_cast<double>(i) / sample_rate);
    }

    const auto f = argus_core::extract_features(samples, sample_rate);
    // RMS of a unit sine wave is 1/sqrt(2).
    require(close(f.rms, 1.0 / std::sqrt(2.0), 1e-2), "sine RMS");
    require(close(f.dominant_frequency_hz, target_freq, 1.0), "sine frequency");
    std::cout << "[PASS] sine_wave_dominant_frequency (detected "
              << f.dominant_frequency_hz << " Hz, expected " << target_freq
              << " Hz)\n";
}

void test_fft_matches_naive_dft() {
    for (std::size_t n = 1; n <= 37; ++n) {
        std::vector<double> samples(n);
        for (std::size_t i = 0; i < n; ++i) {
            samples[i] = std::sin(static_cast<double>(i)) + 0.1 * static_cast<double>(i);
        }
        std::size_t padded = 1;
        while (padded < n) padded *= 2;
        const auto spectrum = argus_core::magnitude_spectrum(samples);
        require(spectrum.size() == padded / 2 + 1, "padded spectrum length");
        for (std::size_t bin = 0; bin < spectrum.size(); ++bin) {
            std::complex<double> expected{0.0, 0.0};
            for (std::size_t i = 0; i < n; ++i) {
                const double angle = -2.0 * std::numbers::pi *
                                     static_cast<double>(bin * i) / static_cast<double>(padded);
                expected += samples[i] * std::complex<double>(std::cos(angle), std::sin(angle));
            }
            require(close(spectrum[bin], std::abs(expected) / static_cast<double>(padded), 1e-12),
                    "FFT must match independent DFT for every bin");
        }
    }
    std::cout << "[PASS] fft_matches_naive_dft\n";
}

void test_single_sample_and_silent_window() {
    const auto single = argus_core::extract_features(std::vector<double>{3.0}, 1000.0);
    for (double value : single.to_array()) {
        require(std::isfinite(value), "single sample features must be finite");
    }
    require(single.mean == 3.0 && single.rms == 3.0, "single sample statistics");
    require(single.dominant_frequency_hz == 0.0 && single.spectral_energy == 0.0,
            "single sample has only DC");
    const auto zero = argus_core::extract_features(std::vector<double>(13, 0.0), 1000.0);
    for (double value : zero.to_array()) require(value == 0.0, "silent window features");
    std::cout << "[PASS] single_sample_and_silent_window\n";
}

void test_invalid_inputs() {
    const std::vector<double> empty;
    require_invalid_argument([&] { argus_core::extract_features(empty, 1000.0); });
    require_invalid_argument([&] { argus_core::magnitude_spectrum(empty); });
    const double nan = std::numeric_limits<double>::quiet_NaN();
    const double inf = std::numeric_limits<double>::infinity();
    for (double invalid : {nan, inf, -inf}) {
        const std::vector<double> samples{1.0, invalid};
        require_invalid_argument([&] { argus_core::extract_features(samples, 1000.0); });
        require_invalid_argument([&] { argus_core::magnitude_spectrum(samples); });
    }
    for (double rate : {0.0, -1.0, nan, inf, -inf}) {
        require_invalid_argument([&] {
            argus_core::extract_features(std::vector<double>{1.0}, rate);
        });
    }
    std::vector<std::complex<double>> non_power_two(3);
    require_invalid_argument([&] { argus_core::fft_radix2(non_power_two); });
    std::cout << "[PASS] invalid_inputs\n";
}

}  // namespace

int main() {
    try {
        test_constant_signal_rms_and_zero_crossings();
        test_sine_wave_dominant_frequency();
        test_fft_matches_naive_dft();
        test_single_sample_and_silent_window();
        test_invalid_inputs();
    } catch (const std::exception& error) {
        std::cerr << "[FAIL] " << error.what() << '\n';
        return 1;
    }
    std::cout << "All cpp_core tests passed.\n";
    return 0;
}
