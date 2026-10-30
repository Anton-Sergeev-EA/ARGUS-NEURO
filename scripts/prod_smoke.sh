#!/usr/bin/env bash
# Check the production stack from outside: TLS, login, open health, ingest token, metrics.
#   bash scripts/prod_smoke.sh https://localhost:8443 operator PASSWORD
# Uses -k so that Caddy's internal test CA is accepted; against a real domain remove it.
set -euo pipefail
BASE="${1:?base url}"; USER_NAME="${2:?user}"; PASS="${3:?password}"
fail=0
check() {  # description expected_code curl-args...
    local desc="$1" want="$2"; shift 2
    local got
    got=$(curl -sk -o /dev/null -w '%{http_code}' --max-time 15 "$@" || true)
    if [[ "$got" == "$want" ]]; then echo "ok   $desc ($got)"; else echo "FAIL $desc: wanted $want, got $got"; fail=1; fi
}
for _ in $(seq 1 40); do
    [[ "$(curl -sk -o /dev/null -w '%{http_code}' "$BASE/api/health" || true)" == 200 ]] && break
    sleep 3
done
check "health is open" 200 "$BASE/api/health"
check "dashboard needs a login" 401 "$BASE/"
check "api needs a login" 401 "$BASE/api/fleet"
check "wrong password is refused" 401 -u "$USER_NAME:wrong-$PASS" "$BASE/api/fleet"
check "dashboard with login" 200 -u "$USER_NAME:$PASS" "$BASE/"
check "fleet with login" 200 -u "$USER_NAME:$PASS" "$BASE/api/fleet"
check "ingest refuses a missing token" 401 -X POST -H 'Content-Type: application/json' -d '{}' "$BASE/api/ingest/equipment"
if ! curl -sk --max-time 15 -u "$USER_NAME:$PASS" "$BASE/api/metrics" | grep -q '^argus_up 1$'; then
    echo "FAIL metrics do not report argus_up 1"; fail=1
else
    echo "ok   metrics report argus_up 1"
fi
exit "$fail"
