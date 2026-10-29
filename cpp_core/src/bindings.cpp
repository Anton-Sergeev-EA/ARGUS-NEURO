// pybind11 bindings exposing the C++20 signal-processing core to Python as
// the `argus_core` extension module. This is the seam between the
// performance-critical native layer and the Python ML/orchestration layer.

#include <pybind11/complex.h>
#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <cstring>
#include <vector>

#include "argus_core/battery_curves.hpp"
#include "argus_core/signal_features.hpp"

namespace py = pybind11;

namespace {

using SampleArray = py::array_t<double, py::array::c_style | py::array::forcecast>;

std::vector<double> ndarray_to_vector(const SampleArray& arr) {
    py::buffer_info info = arr.request();
    if (info.ndim != 1) {
        throw std::invalid_argument("expected a 1-D array of samples");
    }
    // c_style materializes strided/reversed arrays before taking this pointer.
    // Own a copy before releasing the GIL: Python may then mutate the source.
    if (info.shape[0] == 0) return {};
    std::vector<double> result(static_cast<std::size_t>(info.shape[0]));
    // NumPy permits contiguous views with unaligned data pointers. memcpy
    // avoids dereferencing an unaligned double on stricter CPU architectures.
    std::memcpy(result.data(), info.ptr, result.size() * sizeof(double));
    return result;
}

}  // namespace

PYBIND11_MODULE(argus_core, m) {
    m.doc() =
        "ARGUS-NEURO native core: fast statistical and spectral feature "
        "extraction for power-electronics telemetry (C++20, exposed via "
        "pybind11).";

    py::class_<argus_core::FeatureVector>(m, "FeatureVector")
        .def_readonly("mean", &argus_core::FeatureVector::mean)
        .def_readonly("rms", &argus_core::FeatureVector::rms)
        .def_readonly("std_dev", &argus_core::FeatureVector::std_dev)
        .def_readonly("peak", &argus_core::FeatureVector::peak)
        .def_readonly("crest_factor", &argus_core::FeatureVector::crest_factor)
        .def_readonly("kurtosis", &argus_core::FeatureVector::kurtosis)
        .def_readonly("skewness", &argus_core::FeatureVector::skewness)
        .def_readonly("zero_crossing_rate",
                       &argus_core::FeatureVector::zero_crossing_rate)
        .def_readonly("dominant_frequency_hz",
                       &argus_core::FeatureVector::dominant_frequency_hz)
        .def_readonly("spectral_centroid_hz",
                       &argus_core::FeatureVector::spectral_centroid_hz)
        .def_readonly("spectral_energy",
                       &argus_core::FeatureVector::spectral_energy)
        .def("to_array",
             [](const argus_core::FeatureVector& f) {
                 const auto arr = f.to_array();
                 return std::vector<double>(arr.begin(), arr.end());
             })
        .def_static("field_names", &argus_core::FeatureVector::field_names)
        .def("__repr__", [](const argus_core::FeatureVector& f) {
            return "<FeatureVector rms=" + std::to_string(f.rms) +
                   " crest_factor=" + std::to_string(f.crest_factor) +
                   " dominant_frequency_hz=" +
                   std::to_string(f.dominant_frequency_hz) + ">";
        });

    m.def(
        "extract_features",
        [](const SampleArray& samples, double sample_rate_hz) {
            const auto vec = ndarray_to_vector(samples);
            py::gil_scoped_release release;
            return argus_core::extract_features(vec, sample_rate_hz);
        },
        py::arg("samples"), py::arg("sample_rate_hz"),
        "Extract the full statistical + spectral FeatureVector from a 1-D "
        "array of telemetry samples.");

    m.def(
        "magnitude_spectrum",
        [](const SampleArray& samples) {
            const auto vec = ndarray_to_vector(samples);
            py::gil_scoped_release release;
            return argus_core::magnitude_spectrum(vec);
        },
        py::arg("samples"),
        "Return the single-sided FFT magnitude spectrum of the input "
        "(zero-padded to the next power of two).");

    py::class_<argus_core::IncrementalCapacity>(m, "IncrementalCapacity")
        .def_readonly("voltage_v", &argus_core::IncrementalCapacity::voltage_v)
        .def_readonly("dq_dv_ah_per_v",
                       &argus_core::IncrementalCapacity::dq_dv_ah_per_v)
        .def_readonly("peak_voltage_v",
                       &argus_core::IncrementalCapacity::peak_voltage_v)
        .def_readonly("peak_height_ah_per_v",
                       &argus_core::IncrementalCapacity::peak_height_ah_per_v)
        .def_readonly("peak_width_v",
                       &argus_core::IncrementalCapacity::peak_width_v)
        .def_readonly("area_ah", &argus_core::IncrementalCapacity::area_ah);

    m.def(
        "incremental_capacity",
        [](const SampleArray& voltage, const SampleArray& capacity,
           std::size_t bins, std::size_t smooth_window) {
            const auto v = ndarray_to_vector(voltage);
            const auto q = ndarray_to_vector(capacity);
            py::gil_scoped_release release;
            return argus_core::incremental_capacity(v, q, bins, smooth_window);
        },
        py::arg("voltage_v"), py::arg("capacity_ah"), py::arg("bins") = 160,
        py::arg("smooth_window") = 5,
        "Incremental-capacity (dQ/dV) curve and dominant-peak features of a "
        "charge record.");

    m.def(
        "time_between_voltages",
        [](const SampleArray& time, const SampleArray& voltage, double v_low,
           double v_high) {
            const auto t = ndarray_to_vector(time);
            const auto v = ndarray_to_vector(voltage);
            py::gil_scoped_release release;
            return argus_core::time_between_voltages(t, v, v_low, v_high);
        },
        py::arg("time_s"), py::arg("voltage_v"), py::arg("v_low"),
        py::arg("v_high"),
        "Seconds for the voltage to rise from v_low to v_high, or None.");

    m.def(
        "estimate_dcir",
        [](const SampleArray& current, const SampleArray& voltage,
           double min_step_a) {
            const auto i = ndarray_to_vector(current);
            const auto v = ndarray_to_vector(voltage);
            py::gil_scoped_release release;
            return argus_core::estimate_dcir(i, v, min_step_a);
        },
        py::arg("current_a"), py::arg("voltage_v"), py::arg("min_step_a") = 0.5,
        "DC internal resistance (ohm) from the largest current step, or None.");
}
