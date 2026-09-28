// pybind11 bindings exposing the C++20 signal-processing core to Python as
// the `argus_core` extension module. This is the seam between the
// performance-critical native layer and the Python ML/orchestration layer.

#include <pybind11/complex.h>
#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <cstring>
#include <vector>

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
}
