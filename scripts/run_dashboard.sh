#!/usr/bin/env bash
# Local synthetic demonstration. Use a trusted reverse proxy for deployment.
set -euo pipefail
cd "$(dirname "$0")/.."
ARGUS_PYTHON="${ARGUS_PYTHON:-$PWD/.venv/bin/python}"
if [[ ! -x "$ARGUS_PYTHON" ]]; then ARGUS_PYTHON=python3; fi
export PYTHONPATH="${PWD}/python:${PWD}/build/cpp_core:${PYTHONPATH:-}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-1}"
exec "$ARGUS_PYTHON" -m uvicorn argus.api.server:app --host "${ARGUS_HOST:-127.0.0.1}" --port "${ARGUS_PORT:-8000}"
