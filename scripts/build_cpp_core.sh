#!/usr/bin/env bash
# Configures and builds the C++20 native core (static lib + native unit
# tests + pybind11 Python extension) into ./build.
set -euo pipefail
cd "$(dirname "$0")/.."

PYBIND11_CMAKE_DIR="$(python3 -m pybind11 --cmakedir)"

mkdir -p build
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -Dpybind11_DIR="${PYBIND11_CMAKE_DIR}"
cmake --build build -j"$(nproc)"

echo
echo "Build complete."
echo "Native unit tests:  ./build/cpp_core/argus_core_tests"
echo "Python extension:   build/cpp_core/argus_core*.so"
echo "Add it to PYTHONPATH, e.g.:"
echo "  export PYTHONPATH=\"\$PWD/python:\$PWD/build/cpp_core\""
