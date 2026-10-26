// ARGUS-NEURO :: cpp_core
// Voltage-curve health indicators for lithium-ion cells.
//
// Capacity alone falls late in a cell's life. The shape of the charge curve and the
// voltage response to a current step change earlier, so these functions turn one
// charge or discharge record into a handful of numbers a model can track.

#pragma once

#include <cstddef>
#include <optional>
#include <span>
#include <vector>

namespace argus_core {

/// Incremental-capacity (dQ/dV) curve of a monotonic charge record and the
/// features of its dominant peak. Peak position drifts and peak height shrinks
/// as active material is lost, which is why ICA is a standard ageing indicator.
struct IncrementalCapacity {
    std::vector<double> voltage_v;   // bin centres
    std::vector<double> dq_dv_ah_per_v;
    double peak_voltage_v = 0.0;
    double peak_height_ah_per_v = 0.0;
    double peak_width_v = 0.0;       // full width at half maximum
    double area_ah = 0.0;            // charge covered by the voltage range
};

/// @param voltage_v     Cell voltage during a charge; small decreases (sensor noise,
///                      relaxation) are flattened by a running maximum.
/// @param capacity_ah   Cumulative charge in Ah, same length as `voltage_v`.
/// @param bins          Uniform voltage bins (>= 8).
/// @param smooth_window Odd moving-average width in bins (>= 1, <= bins).
/// @throws std::invalid_argument on mismatched, non-finite or degenerate input.
IncrementalCapacity incremental_capacity(std::span<const double> voltage_v,
                                         std::span<const double> capacity_ah,
                                         std::size_t bins,
                                         std::size_t smooth_window);

/// Seconds the voltage takes to rise from `v_low` to `v_high` (linear
/// interpolation between samples). `std::nullopt` when the record does not cover
/// the whole window. `time_s` must be strictly increasing.
std::optional<double> time_between_voltages(std::span<const double> time_s,
                                            std::span<const double> voltage_v,
                                            double v_low, double v_high);

/// Direct-current internal resistance in ohm from the largest current step in the
/// record: |dV| / |dI| across that step. `std::nullopt` when no step reaches
/// `min_step_a`. This is a screening estimate: it includes diffusion and sampling
/// effects and is not a replacement for a pulse test at a fixed state of charge.
std::optional<double> estimate_dcir(std::span<const double> current_a,
                                    std::span<const double> voltage_v,
                                    double min_step_a);

}  // namespace argus_core
