#!/usr/bin/env bash
# One-shot environment setup: Python dependencies + native core build.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> Installing Python dependencies"
pip install -r python/requirements.txt

echo "==> Installing pybind11 (build-time, CMake config package)"
pip install pybind11

echo "==> Building the C++ core"
bash scripts/build_cpp_core.sh

echo
echo "Setup complete. Next steps:"
echo "  export PYTHONPATH=\"\$PWD/python:\$PWD/build/cpp_core\""
echo "  python -m argus.training.train_anomaly"
echo "  python -m argus.training.train_rul"
echo "  python -m argus.export.export_onnx"
echo "  bash scripts/run_dashboard.sh"
