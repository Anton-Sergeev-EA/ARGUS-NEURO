#!/usr/bin/env bash
# Train into a fresh bundle; activate only after validation. Preserve old weights.
set -euo pipefail
cd "$(dirname "$0")/.."
ARGUS_PYTHON="${ARGUS_PYTHON:-$PWD/.venv/bin/python}"
if [[ ! -x "$ARGUS_PYTHON" ]]; then ARGUS_PYTHON=python3; fi
export PYTHONPATH="${PWD}/python:${PWD}/build/cpp_core:${PYTHONPATH:-}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-1}"
mkdir -p artifacts
ARGUS_BUNDLE="$(mktemp -d "$PWD/artifacts/run-$(date +%Y%m%d-%H%M%S)-XXXXXX")"
"$ARGUS_PYTHON" -m argus.training.train_anomaly --artifacts-dir "$ARGUS_BUNDLE"
"$ARGUS_PYTHON" -m argus.training.train_rul --artifacts-dir "$ARGUS_BUNDLE"
"$ARGUS_PYTHON" -m argus.export.export_onnx --artifacts-dir "$ARGUS_BUNDLE"
"$ARGUS_PYTHON" - "$ARGUS_BUNDLE" <<'PY'
import json
import sys
from pathlib import Path
from argus.inference.engine import HealthInferenceEngine
bundle = Path(sys.argv[1]).resolve()
if not HealthInferenceEngine(bundle).model_backed:
    raise RuntimeError("New bundle did not load; previous active bundle preserved")
manifest = bundle.parent / "active.json"
staged = manifest.with_suffix(".json.tmp")
staged.write_text(json.dumps({"directory": bundle.name}, indent=2) + "\n")
staged.replace(manifest)
print(f"Validated bundle activated: {bundle}. Restart the server to load it.")
PY
