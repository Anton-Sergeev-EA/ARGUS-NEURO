#!/usr/bin/env bash
# Smoke test of a running container (docker compose up -d). Exits non-zero on the first failure.
set -euo pipefail
BASE="${ARGUS_URL:-http://127.0.0.1:8000}"
fail() { echo "FAIL: $*" >&2; exit 1; }
for _ in $(seq 1 60); do
  if curl -fsS "$BASE/api/health" >/dev/null 2>&1; then break; fi
  sleep 2
done
curl -fsS "$BASE/api/health" | grep -q . || fail "health endpoint"
curl -fsS "$BASE/" | grep -qi "ARGUS" || fail "battery page"
curl -fsS "$BASE/equipment.html" | grep -qi "ARGUS" || fail "equipment page"
curl -fsS "$BASE/fleet.html" | grep -qi "ARGUS" || fail "fleet page"
curl -fsS "$BASE/api/battery/example" | grep -q . || fail "example request"
echo "smoke test passed: $BASE"
