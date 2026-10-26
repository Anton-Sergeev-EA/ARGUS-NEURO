#include "argus_core/battery_curves.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>

namespace argus_core {
namespace {

void require_finite(std::span<const double> values, const char* message) {
    for (const double value : values) {
        if (!std::isfinite(value)) throw std::invalid_argument(message);
    }
}

// Voltage clamped to a running maximum, with equal voltages merged so the abscissa
// is strictly increasing. The capacity kept for a merged voltage is the latest one.
struct Monotonic {
    std::vector<double> v;
    std::vector<double> q;
};

Monotonic make_monotonic(std::span<const double> voltage, std::span<const double> capacity) {
    Monotonic out;
    out.v.reserve(voltage.size());
    out.q.reserve(voltage.size());
    double running = -std::numeric_limits<double>::infinity();
    for (std::size_t i = 0; i < voltage.size(); ++i) {
        running = std::max(running, voltage[i]);
        if (out.v.empty() || running > out.v.back()) {
            out.v.push_back(running);
            out.q.push_back(capacity[i]);
        } else {
            out.q.back() = capacity[i];
        }
    }
    return out;
}

double interpolate(const Monotonic& curve, double level, std::size_t& cursor) {
    while (cursor + 2 < curve.v.size() && curve.v[cursor + 1] < level) ++cursor;
    const double span = curve.v[cursor + 1] - curve.v[cursor];
    const double t = (level - curve.v[cursor]) / span;
    return curve.q[cursor] + t * (curve.q[cursor + 1] - curve.q[cursor]);
}

}  // namespace

IncrementalCapacity incremental_capacity(std::span<const double> voltage_v,
                                         std::span<const double> capacity_ah,
                                         std::size_t bins, std::size_t smooth_window) {
    if (voltage_v.size() != capacity_ah.size())
        throw std::invalid_argument("voltage and capacity must have the same length");
    if (voltage_v.size() < 3) throw std::invalid_argument("at least three samples required");
    if (bins < 8) throw std::invalid_argument("at least eight bins required");
    if (smooth_window == 0 || smooth_window % 2 == 0 || smooth_window > bins)
        throw std::invalid_argument("smooth_window must be odd and not exceed bins");
    require_finite(voltage_v, "voltage must be finite");
    require_finite(capacity_ah, "capacity must be finite");

    const Monotonic curve = make_monotonic(voltage_v, capacity_ah);
    if (curve.v.size() < 3 || !(curve.v.back() > curve.v.front()))
        throw std::invalid_argument("voltage range is degenerate");

    const double v0 = curve.v.front();
    const double dv = (curve.v.back() - v0) / static_cast<double>(bins);
    std::vector<double> q_edge(bins + 1);
    std::size_t cursor = 0;
    for (std::size_t k = 0; k <= bins; ++k) {
        const double level = k == bins ? curve.v.back() : v0 + dv * static_cast<double>(k);
        q_edge[k] = interpolate(curve, level, cursor);
    }

    std::vector<double> raw(bins);
    for (std::size_t k = 0; k < bins; ++k) raw[k] = (q_edge[k + 1] - q_edge[k]) / dv;

    IncrementalCapacity out;
    out.voltage_v.resize(bins);
    out.dq_dv_ah_per_v.resize(bins);
    const std::size_t half = smooth_window / 2;
    for (std::size_t k = 0; k < bins; ++k) {
        const std::size_t lo = k >= half ? k - half : 0;
        const std::size_t hi = std::min(bins - 1, k + half);
        double sum = 0.0;
        for (std::size_t j = lo; j <= hi; ++j) sum += raw[j];
        out.dq_dv_ah_per_v[k] = sum / static_cast<double>(hi - lo + 1);
        out.voltage_v[k] = v0 + dv * (static_cast<double>(k) + 0.5);
    }

    const auto peak = std::max_element(out.dq_dv_ah_per_v.begin(), out.dq_dv_ah_per_v.end());
    const std::size_t p = static_cast<std::size_t>(peak - out.dq_dv_ah_per_v.begin());
    out.peak_voltage_v = out.voltage_v[p];
    out.peak_height_ah_per_v = *peak;
    out.area_ah = q_edge.back() - q_edge.front();

    // Full width at half maximum, interpolating the two crossings. A flank that
    // never falls below half height ends at the edge of the voltage range.
    const double half_height = *peak / 2.0;
    double left = out.voltage_v.front();
    for (std::size_t k = p; k > 0; --k) {
        if (out.dq_dv_ah_per_v[k - 1] < half_height) {
            const double a = out.dq_dv_ah_per_v[k - 1], b = out.dq_dv_ah_per_v[k];
            left = out.voltage_v[k - 1] + (half_height - a) / (b - a) * dv;
            break;
        }
    }
    double right = out.voltage_v.back();
    for (std::size_t k = p; k + 1 < bins; ++k) {
        if (out.dq_dv_ah_per_v[k + 1] < half_height) {
            const double a = out.dq_dv_ah_per_v[k], b = out.dq_dv_ah_per_v[k + 1];
            right = out.voltage_v[k] + (a - half_height) / (a - b) * dv;
            break;
        }
    }
    out.peak_width_v = right - left;
    return out;
}

std::optional<double> time_between_voltages(std::span<const double> time_s,
                                            std::span<const double> voltage_v,
                                            double v_low, double v_high) {
    if (time_s.size() != voltage_v.size() || time_s.size() < 2)
        throw std::invalid_argument("time and voltage need the same length of at least two");
    if (!std::isfinite(v_low) || !std::isfinite(v_high) || !(v_high > v_low))
        throw std::invalid_argument("voltage window must be finite and ordered");
    require_finite(time_s, "time must be finite");
    require_finite(voltage_v, "voltage must be finite");
    for (std::size_t i = 1; i < time_s.size(); ++i) {
        if (!(time_s[i] > time_s[i - 1]))
            throw std::invalid_argument("time must be strictly increasing");
    }

    // First time the running maximum of the voltage reaches `level`.
    const auto reach = [&](double level) -> std::optional<double> {
        double running = -std::numeric_limits<double>::infinity();
        double previous = running;
        for (std::size_t i = 0; i < voltage_v.size(); ++i) {
            running = std::max(running, voltage_v[i]);
            if (running >= level) {
                if (i == 0 || !std::isfinite(previous)) return time_s[i];
                const double t = (level - previous) / (running - previous);
                return time_s[i - 1] + t * (time_s[i] - time_s[i - 1]);
            }
            previous = running;
        }
        return std::nullopt;
    };

    const auto start = reach(v_low);
    const auto stop = reach(v_high);
    if (!start || !stop) return std::nullopt;
    return *stop - *start;
}

std::optional<double> estimate_dcir(std::span<const double> current_a,
                                    std::span<const double> voltage_v, double min_step_a) {
    if (current_a.size() != voltage_v.size() || current_a.size() < 2)
        throw std::invalid_argument("current and voltage need the same length of at least two");
    if (!std::isfinite(min_step_a) || min_step_a <= 0.0)
        throw std::invalid_argument("min_step_a must be finite and positive");
    require_finite(current_a, "current must be finite");
    require_finite(voltage_v, "voltage must be finite");

    double best_step = 0.0;
    std::size_t at = 0;
    for (std::size_t i = 0; i + 1 < current_a.size(); ++i) {
        const double step = std::abs(current_a[i + 1] - current_a[i]);
        if (step > best_step) {
            best_step = step;
            at = i;
        }
    }
    if (best_step < min_step_a) return std::nullopt;
    return std::abs(voltage_v[at + 1] - voltage_v[at]) / best_step;
}

}  // namespace argus_core
