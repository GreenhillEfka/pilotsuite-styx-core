#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SANDBOX_ROOT="$(cd "$ROOT/../.." && pwd)/workspaces/pilotsuite-stxy-sandbox"
HANDOFF_DIR="$SANDBOX_ROOT/handoff"
OUT="$HANDOFF_DIR/core_workspace_target.json"
PAIR_OUT="$HANDOFF_DIR/core_release_pairing.json"
EVIDENCE_OUT="$HANDOFF_DIR/core_workspace_harness_evidence.json"

mkdir -p "$HANDOFF_DIR"

HEAD_COMMIT="$(git -C "$ROOT" rev-parse --short=8 HEAD)"
HEAD_BRANCH="$(git -C "$ROOT" rev-parse --abbrev-ref HEAD)"
AHEAD_STATUS="$(git -C "$ROOT" status --short --branch | head -n 1 | sed 's/^## //')"
RECENT_COMMITS="$(git -C "$ROOT" log --oneline -6 | sed 's/"/\\"/g')"
TIMESTAMP="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
APPROVED_CONCEPTS="/config/clawd/team/PILOTSUITE_APPROVED_CONCEPTS_2026-03-23.md"
CORE_DIRECTIVE="$ROOT/docs/CORE_CONCEPT_DIRECTIVE.md"
CORE_HANDOFF="$ROOT/docs/CORE_CONCEPT_HANDOFF.md"
HA_REVIEW_GATE="/config/clawd/team/repos/pilotsuite-styx-ha/scripts/release_review_gate.sh"
HA_HANDOFF_SUMMARY="/config/clawd/team/repos/pilotsuite-styx-ha/scripts/release_handoff_summary.sh"
SANDBOX_HANDOFF="$SANDBOX_ROOT/handoff/2026-03-26_core_contract_harness_handoff.md"
RUNNER_PATH="$ROOT/scripts/run_workspace_ha_core_contract_tests.sh"
TEST_FILE_PATH="$ROOT/tests/integration/test_workspace_ha_core_contract.py"

json_string_or_null() {
  local value="${1-}"
  if [[ -z "$value" ]]; then
    printf 'null'
  else
    value="$(printf '%s' "$value" | sed 's/\\/\\\\/g; s/"/\\"/g')"
    printf '"%s"' "$value"
  fi
}

RECENT_COMMITS_JSON="$({
  printf '%s\n' "$RECENT_COMMITS" | awk '{printf "    \"%s\"", $0; if (NR < lines) printf ","; printf "\n"}' lines="$(printf '%s\n' "$RECENT_COMMITS" | wc -l)"
})"

HARNESS_LAST_RESULT_JSON="$(json_string_or_null "${WORKSPACE_HARNESS_LAST_RESULT:-}")"
HARNESS_LAST_RESULT_SOURCE_JSON="$(json_string_or_null "${WORKSPACE_HARNESS_LAST_RESULT_SOURCE:-}")"

if command -v python3 >/dev/null 2>&1; then
  PYTHON3_AVAILABLE=true
else
  PYTHON3_AVAILABLE=false
fi

if python3 -c "import pytest" >/dev/null 2>&1 2>/dev/null; then
  PYTEST_AVAILABLE=true
  EVIDENCE_STATUS="runnable"
  EVIDENCE_NEXT_ACTION="run workspace harness and capture result in this file"
else
  PYTEST_AVAILABLE=false
  EVIDENCE_STATUS="awaiting_workspace_pytest"
  EVIDENCE_NEXT_ACTION="provide python3+pytest in workspace environment, then run $RUNNER_PATH"
fi

cat > "$OUT" <<EOF
{
  "generated_at_utc": "$TIMESTAMP",
  "repo": "$ROOT",
  "branch": "$HEAD_BRANCH",
  "head_commit": "$HEAD_COMMIT",
  "status": "$AHEAD_STATUS",
  "workspace_harness": {
    "runner": "$RUNNER_PATH",
    "test_file": "$TEST_FILE_PATH",
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
    "handoff_note": "$SANDBOX_HANDOFF",
    "evidence_file": "$EVIDENCE_OUT"
  },
  "recent_commits": [
$RECENT_COMMITS_JSON
  ]
}
EOF

cat > "$PAIR_OUT" <<EOF
{
  "generated_at_utc": "$TIMESTAMP",
  "pairing_kind": "workspace_release_pairing_input",
  "owner_lane": "PilotClaw",
  "core_target": {
    "repo": "$ROOT",
    "branch": "$HEAD_BRANCH",
    "head_commit": "$HEAD_COMMIT",
    "status": "$AHEAD_STATUS"
  },
  "binding_context": {
    "approved_concepts": "$APPROVED_CONCEPTS",
    "core_concept_directive": "$CORE_DIRECTIVE",
    "core_concept_handoff": "$CORE_HANDOFF",
    "older_research_integrated": [
      "fallback lane remains mandatory",
      "Core = semantic truth, HA/HACS = sensorium/runtime shell",
      "zone sync and event ingest stay contract-first"
    ]
  },
  "shared_workspace_inputs": {
    "core_workspace_target": "$OUT",
    "core_handoff_note": "$SANDBOX_HANDOFF",
    "core_harness_evidence": "$EVIDENCE_OUT",
    "fixtures": [
      "$SANDBOX_ROOT/fixtures/ha_events/canonical_state_changed.json",
      "$SANDBOX_ROOT/fixtures/ha_events/legacy_state_changed.json",
      "$SANDBOX_ROOT/fixtures/ha_events/call_service.json",
      "$SANDBOX_ROOT/fixtures/ha_events/zone_definitions.json"
    ]
  },
  "ha_release_pairing_expectations": {
    "review_gate": "$HA_REVIEW_GATE",
    "handoff_summary": "$HA_HANDOFF_SUMMARY",
    "pairing_rule": "HA release candidate should reference this Core target plus shared sandbox harness surfaces and evidence file; no live-install claim implied"
  }
}
EOF

cat > "$EVIDENCE_OUT" <<EOF
{
  "generated_at_utc": "$TIMESTAMP",
  "owner_lane": "PilotClaw",
  "core_target_commit": "$HEAD_COMMIT",
  "runner": "$RUNNER_PATH",
  "test_file": "$TEST_FILE_PATH",
  "environment": {
    "python3_available": $PYTHON3_AVAILABLE,
    "pytest_available": $PYTEST_AVAILABLE
  },
  "status": "$EVIDENCE_STATUS",
  "coverage_expectation": [
    "ha_to_core canonical state_changed",
    "ha_to_core legacy state_changed fallback lane",
    "ha_to_core call_service",
    "ha_to_core zone sync",
    "core_to_ha suggestion normalization",
    "events endpoint /api/v1/events workspace harness"
  ],
  "last_result": $HARNESS_LAST_RESULT_JSON,
  "last_result_source": $HARNESS_LAST_RESULT_SOURCE_JSON,
  "next_exact_action": "$EVIDENCE_NEXT_ACTION",
  "notes": [
    "workspace-only evidence lane",
    "not a live-install verification signal",
    "approved concepts and older research are already folded into the harness surfaces",
    "optional writeback via WORKSPACE_HARNESS_LAST_RESULT and WORKSPACE_HARNESS_LAST_RESULT_SOURCE"
  ]
}
EOF

echo "$OUT"
echo "$PAIR_OUT"
echo "$EVIDENCE_OUT"
