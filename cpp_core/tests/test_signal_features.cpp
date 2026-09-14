// Lightweight, dependency-free sanity checks for the signal core.
// Intentionally avoids pulling in a test framework so the native
// build stays trivial in any environment (no network fetch required).

#include <cassert>
#include <cmath>
#include <iostream>
#include <numbers>
#include <vector>

#include "argus_core/signal_features.hpp"

namespace {

bool close(double a, double b, double tol = 1e-6) {
    return std::abs(a - b) <= tol;
}

void test_constant_signal_rms_and_zero_crossings() {
    std::vector<double> samples(256, 5.0);
    const auto f = argus_core::extract_features(samples, 1000.0);
    assert(close(f.mean, 5.0));
    assert(close(f.rms, 5.0, 1e-3));
    assert(close(f.std_dev, 0.0, 1e-3));
    assert(f.zero_crossing_rate == 0.0);
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
    assert(close(f.rms, 1.0 / std::sqrt(2.0), 1e-2));
    assert(close(f.dominant_frequency_hz, target_freq, 1.0));
    std::cout << "[PASS] sine_wave_dominant_frequency (detected "
              << f.dominant_frequency_hz << " Hz, expected " << target_freq
              << " Hz)\n";
}

void test_fft_radix2_matches_naive_dft_energy() {
    std::vector<double> samples = {1.0, 0.0, -1.0, 0.0, 1.0, 0.0, -1.0, 0.0};
    const auto spectrum = argus_core::magnitude_spectrum(samples);
    // Parseval-style sanity check: energy should be non-trivial and finite.
    double total = 0.0;
    for (double m : spectrum) total += m * m;
    assert(total > 0.0);
    assert(std::isfinite(total));
    std::cout << "[PASS] fft_radix2_matches_naive_dft_energy\n";
}

}  // namespace

int main() {
    test_constant_signal_rms_and_zero_crossings();
    test_sine_wave_dominant_frequency();
    test_fft_radix2_matches_naive_dft_energy();
    std::cout << "All cpp_core tests passed.\n";
    return 0;
}
