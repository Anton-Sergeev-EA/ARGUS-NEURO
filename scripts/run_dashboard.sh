#!/usr/bin/env bash
# Launches the FastAPI/WebSocket backend and serves the dashboard at
# http://localhost:8000/.
set -euo pipefail
cd "$(dirname "$0")/.."

export PYTHONPATH="${PWD}/python:${PWD}/build/cpp_core:${PYTHONPATH:-}"
exec python3 -m uvicorn argus.api.server:app --host 0.0.0.0 --port 8000
