#!/usr/bin/env bash
# Isolated environment for the tested CPython 3.12 dependency set.
set -euo pipefail
cd "$(dirname "$0")/.."
ARGUS_PYTHON="${ARGUS_PYTHON:-python3}"
if [[ ! -x .venv/bin/python ]]; then "$ARGUS_PYTHON" -m venv .venv; fi
.venv/bin/python -m pip install -r python/requirements-dev.txt
export PATH="$PWD/.venv/bin:$PATH"
bash scripts/build_cpp_core.sh
printf '%s\n' 'Next: bash scripts/train_all.sh, then bash scripts/run_dashboard.sh'
