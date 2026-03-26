#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SANDBOX_ROOT="$(cd "$ROOT/../.." && pwd)/workspaces/pilotsuite-stxy-sandbox"
HANDOFF_DIR="$SANDBOX_ROOT/handoff"
OUT="$HANDOFF_DIR/core_workspace_target.json"

mkdir -p "$HANDOFF_DIR"

HEAD_COMMIT="$(git -C "$ROOT" rev-parse --short=8 HEAD)"
HEAD_BRANCH="$(git -C "$ROOT" rev-parse --abbrev-ref HEAD)"
AHEAD_STATUS="$(git -C "$ROOT" status --short --branch | head -n 1 | sed 's/^## //')"
RECENT_COMMITS="$(git -C "$ROOT" log --oneline -6 | sed 's/"/\\"/g')"
TIMESTAMP="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

cat > "$OUT" <<EOF
{
  "generated_at_utc": "$TIMESTAMP",
  "repo": "$ROOT",
  "branch": "$HEAD_BRANCH",
  "head_commit": "$HEAD_COMMIT",
  "status": "$AHEAD_STATUS",
  "workspace_harness": {
    "runner": "$ROOT/scripts/run_workspace_ha_core_contract_tests.sh",
    "test_file": "$ROOT/tests/integration/test_workspace_ha_core_contract.py",
    "requirements_note": "python3 + pytest in workspace environment",
    "coverage": [
      "ha_to_core state_changed canonical",
      "ha_to_core state_changed legacy fallback lane",
      "ha_to_core call_service",
      "ha_to_core zone sync",
      "core_to_ha suggestion normalization",
      "endpoint-level POST /api/v1/events harness"
    ]
  },
  "shared_sandbox_artifacts": {
    "fixtures": [
      "$SANDBOX_ROOT/fixtures/ha_events/canonical_state_changed.json",
      "$SANDBOX_ROOT/fixtures/ha_events/legacy_state_changed.json",
      "$SANDBOX_ROOT/fixtures/ha_events/call_service.json",
      "$SANDBOX_ROOT/fixtures/ha_events/zone_definitions.json"
    ],
    "handoff_note": "$SANDBOX_ROOT/handoff/2026-03-26_core_contract_harness_handoff.md"
  },
  "recent_commits": [
$(printf '%s
' "$RECENT_COMMITS" | awk '{printf "    \"%s\"", $0; if (NR < lines) printf ","; printf "\n"}' lines="$(printf '%s
' "$RECENT_COMMITS" | wc -l)")
  ]
}
EOF

echo "$OUT"
