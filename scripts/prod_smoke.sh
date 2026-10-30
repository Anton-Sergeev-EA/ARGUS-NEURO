#!/usr/bin/env bash
# Check the production stack from outside: TLS, login, open health, ingest token, metrics.
#   bash scripts/prod_smoke.sh https://localhost:8443 operator PASSWORD [INGEST_TOKEN]
# Without INGEST_TOKEN the ingest checks accept a refusal either way (401 with a token
# configured, 503 while ingest is disabled).
# Uses -k so that Caddy's internal test CA is accepted; against a real domain remove it.
set -euo pipefail
BASE="${1:?base url}"; USER_NAME="${2:?user}"; PASS="${3:?password}"; TOKEN="${4:-}"
fail=0
check() {  # description expected_code curl-args...
    local desc="$1" want="$2"; shift 2
    local got
    got=$(curl -sk -o /dev/null -w '%{http_code}' --max-time 15 "$@" || true)
    if [[ "$got" =~ ^($want)$ ]]; then echo "ok   $desc ($got)"; else echo "FAIL $desc: wanted $want, got $got"; fail=1; fi
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
check "ingest refuses a missing token" "401|503" -X POST -H 'Content-Type: application/json' -d '{}' "$BASE/api/ingest/equipment"
if [[ -n "$TOKEN" ]]; then
    check "ingest accepts the token (schema error on an empty body)" 422 -X POST \
        -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{}' "$BASE/api/ingest/equipment"
    check "ingest refuses a wrong token" 401 -X POST \
        -H "Authorization: Bearer wrong-$TOKEN" -H 'Content-Type: application/json' -d '{}' "$BASE/api/ingest/equipment"
fi
if ! curl -sk --max-time 15 -u "$USER_NAME:$PASS" "$BASE/api/metrics" | grep -q '^argus_up 1$'; then
    echo "FAIL metrics do not report argus_up 1"; fail=1
else
    echo "ok   metrics report argus_up 1"
fi
exit "$fail"
