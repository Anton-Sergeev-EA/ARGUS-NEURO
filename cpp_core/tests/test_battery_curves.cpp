// Checks for the battery voltage-curve indicators. Like the signal-core tests this
// has no framework dependency and stays active in Release builds.

#include <cmath>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <vector>

#include "argus_core/battery_curves.hpp"

namespace {

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

bool close(double a, double b, double tol) { return std::abs(a - b) <= tol; }

// Charge record whose dQ/dV is a Gaussian peak at `centre` volts on a small plateau.
struct Charge {
    std::vector<double> voltage, capacity;
};

Charge gaussian_charge(double centre, double sigma, double height, std::size_t n = 4000) {
    Charge c;
    double q = 0.0;
    const double v_lo = 3.4, v_hi = 4.2;
    for (std::size_t i = 0; i < n; ++i) {
        const double v = v_lo + (v_hi - v_lo) * static_cast<double>(i) / static_cast<double>(n - 1);
        const double slope =
            0.2 + height * std::exp(-0.5 * std::pow((v - centre) / sigma, 2.0));
        if (i > 0) q += slope * (v - c.voltage.back());
        c.voltage.push_back(v);
        c.capacity.push_back(q);
    }
    return c;
}

void test_peak_position_height_and_width_are_recovered() {
    const auto c = gaussian_charge(3.80, 0.05, 4.0);
    const auto ica = argus_core::incremental_capacity(c.voltage, c.capacity, 160, 5);
    require(close(ica.peak_voltage_v, 3.80, 0.01), "peak voltage");
    require(close(ica.peak_height_ah_per_v, 4.2, 0.15), "peak height");
    // FWHM of a Gaussian sitting on a plateau is close to 2.355 sigma.
    require(close(ica.peak_width_v, 2.355 * 0.05, 0.025), "peak width");
    require(close(ica.area_ah, c.capacity.back(), 1e-9), "area equals total charge");
    std::cout << "[PASS] incremental_capacity_peak_features\n";
}

void test_ageing_shifts_and_lowers_the_peak() {
    const auto fresh = gaussian_charge(3.80, 0.05, 4.0);
    const auto aged = gaussian_charge(3.84, 0.05, 2.5);
    const auto a = argus_core::incremental_capacity(fresh.voltage, fresh.capacity, 160, 5);
    const auto b = argus_core::incremental_capacity(aged.voltage, aged.capacity, 160, 5);
    require(b.peak_voltage_v > a.peak_voltage_v, "aged peak moves up");
    require(b.peak_height_ah_per_v < a.peak_height_ah_per_v, "aged peak is lower");
    std::cout << "[PASS] ageing_shifts_and_lowers_the_peak\n";
}

void test_noise_and_repeated_voltages_do_not_break_monotonic_clamp() {
    auto c = gaussian_charge(3.80, 0.05, 4.0, 1500);
    for (std::size_t i = 10; i < c.voltage.size(); i += 7) c.voltage[i] -= 0.001;  // dips
    c.voltage[100] = c.voltage[99];                                                // repeat
    const auto ica = argus_core::incremental_capacity(c.voltage, c.capacity, 100, 5);
    for (double v : ica.dq_dv_ah_per_v) require(std::isfinite(v) && v >= -1e-9, "finite, non-negative");
    require(close(ica.peak_voltage_v, 3.80, 0.03), "peak survives sensor dips");
    std::cout << "[PASS] noise_and_repeated_voltages\n";
}

void test_time_between_voltages_interpolates() {
    const std::vector<double> t{0, 10, 20, 30, 40};
    const std::vector<double> v{3.5, 3.7, 3.9, 4.1, 4.2};
    const auto span = argus_core::time_between_voltages(t, v, 3.6, 4.0);
    require(span && close(*span, 20.0, 1e-9), "interpolated rise time");
    require(!argus_core::time_between_voltages(t, v, 3.6, 4.3), "window not covered");
    const std::vector<double> dip{3.5, 3.7, 3.6, 3.9, 4.1};  // dip must not delay the rise
    require(argus_core::time_between_voltages(t, dip, 3.7, 3.9).has_value(), "dip tolerated");
    std::cout << "[PASS] time_between_voltages\n";
}

void test_dcir_uses_the_largest_current_step() {
    const std::vector<double> i{0.0, 0.0, -2.0, -2.0, -2.0};
    const std::vector<double> v{4.19, 4.19, 4.00, 3.99, 3.98};
    const auto r = argus_core::estimate_dcir(i, v, 0.5);
    require(r && close(*r, 0.095, 1e-9), "dcir = 0.19 V / 2 A");
    require(!argus_core::estimate_dcir(i, v, 3.0), "no step large enough");
    std::cout << "[PASS] dcir_largest_step\n";
}

void test_invalid_inputs_are_rejected() {
    const double nan = std::numeric_limits<double>::quiet_NaN();
    const std::vector<double> v{3.5, 3.6, 3.7, 3.8}, q{0, 1, 2, 3}, short_q{0, 1};
    require_invalid_argument([&] { argus_core::incremental_capacity(v, short_q, 16, 3); });
    require_invalid_argument([&] { argus_core::incremental_capacity(v, q, 4, 3); });
    require_invalid_argument([&] { argus_core::incremental_capacity(v, q, 16, 4); });
    require_invalid_argument([&] { argus_core::incremental_capacity(v, q, 16, 0); });
    const std::vector<double> flat{3.7, 3.7, 3.7, 3.7};
    require_invalid_argument([&] { argus_core::incremental_capacity(flat, q, 16, 3); });
    const std::vector<double> bad{3.5, nan, 3.7, 3.8};
    require_invalid_argument([&] { argus_core::incremental_capacity(bad, q, 16, 3); });
    const std::vector<double> t{0, 1, 1, 2};
    require_invalid_argument([&] { argus_core::time_between_voltages(t, v, 3.5, 3.7); });
    require_invalid_argument([&] { argus_core::time_between_voltages(t, v, 3.7, 3.5); });
    require_invalid_argument([&] { argus_core::estimate_dcir(q, v, 0.0); });
    std::cout << "[PASS] invalid_inputs\n";
}

}  // namespace

int main() {
    try {
        test_peak_position_height_and_width_are_recovered();
        test_ageing_shifts_and_lowers_the_peak();
        test_noise_and_repeated_voltages_do_not_break_monotonic_clamp();
        test_time_between_voltages_interpolates();
        test_dcir_uses_the_largest_current_step();
        test_invalid_inputs_are_rejected();
    } catch (const std::exception& error) {
        std::cerr << "[FAIL] " << error.what() << '\n';
        return 1;
    }
    std::cout << "All battery curve tests passed.\n";
    return 0;
}
