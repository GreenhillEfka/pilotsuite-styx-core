#!/usr/bin/env bash
set -euo pipefail

# Quick E2E check for Onyx -> Styx -> HA loop.
# Usage:
#   TOKEN="..." ./tools/onyx_styx_e2e.sh
# Optional env:
#   STYX_BASE_URL (default: http://192.168.30.18:8909)
#   TEST_ENTITY   (default: light.retrolampe)

BASE_URL="${STYX_BASE_URL:-http://192.168.30.18:8909}"
TEST_ENTITY="${TEST_ENTITY:-light.retrolampe}"

if [[ -z "${TOKEN:-}" ]]; then
  echo "ERROR: TOKEN env var missing"
  echo "Example: TOKEN='<styx_auth_token>' ./tools/onyx_styx_e2e.sh"
  exit 1
fi

auth_header=("Authorization: Bearer ${TOKEN}")
json_header=("Content-Type: application/json")

call_json() {
  local method="$1"
  local url="$2"
  local body="${3:-}"
  local code
  local tmp
  tmp="$(mktemp)"
  if [[ -n "${body}" ]]; then
    code="$(
      curl -sS -o "${tmp}" -w "%{http_code}" \
        -X "${method}" "${url}" \
        -H "${auth_header[0]}" -H "${json_header[0]}" \
        -d "${body}"
    )"
  else
    code="$(
      curl -sS -o "${tmp}" -w "%{http_code}" \
        -X "${method}" "${url}" \
        -H "${auth_header[0]}"
    )"
  fi
  echo "[$method] $url -> HTTP ${code}"
  cat "${tmp}"
  echo
  rm -f "${tmp}"
  [[ "${code}" =~ ^2 ]]
}

echo "== Onyx/Styx E2E =="
echo "BASE_URL=${BASE_URL}"
echo "TEST_ENTITY=${TEST_ENTITY}"
echo

call_json GET "${BASE_URL}/api/v1/onyx/status"
call_json POST "${BASE_URL}/api/v1/onyx/ha/service-call" \
  "{\"domain\":\"light\",\"service\":\"turn_on\",\"entity_id\":\"${TEST_ENTITY}\",\"service_data\":{\"brightness_pct\":40},\"readback\":true}"
call_json POST "${BASE_URL}/mcp" \
  '{"jsonrpc":"2.0","id":"init-1","method":"initialize","params":{}}'
call_json POST "${BASE_URL}/v1/chat/completions" \
  '{"model":"pilotsuite","messages":[{"role":"user","content":"Antworte nur mit OK: pipeline test"}]}'

echo
echo "E2E checks finished."
