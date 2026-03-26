#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SANDBOX_ROOT="$(cd "$ROOT/../.." && pwd)/workspaces/pilotsuite-stxy-sandbox"
HANDOFF_DIR="$SANDBOX_ROOT/handoff"
OUT="$HANDOFF_DIR/core_workspace_target.json"
PAIR_OUT="$HANDOFF_DIR/core_release_pairing.json"

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

RECENT_COMMITS_JSON="$({
  printf '%s\n' "$RECENT_COMMITS" | awk '{printf "    \"%s\"", $0; if (NR < lines) printf ","; printf "\n"}' lines="$(printf '%s\n' "$RECENT_COMMITS" | wc -l)"
})"

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
    "handoff_note": "$SANDBOX_HANDOFF"
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
    "pairing_rule": "HA release candidate should reference this Core target plus shared sandbox harness surfaces; no live-install claim implied"
  }
}
EOF

echo "$OUT"
echo "$PAIR_OUT"
