#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SANDBOX_ROOT="$(cd "$ROOT/../.." && pwd)/workspaces/pilotsuite-stxy-sandbox"
HANDOFF_DIR="$SANDBOX_ROOT/handoff"
OUT="$HANDOFF_DIR/core_workspace_target.json"
PAIR_OUT="$HANDOFF_DIR/core_release_pairing.json"
EVIDENCE_OUT="$HANDOFF_DIR/core_workspace_harness_evidence.json"
BOOTSTRAP_HINT_OUT="$HANDOFF_DIR/core_workspace_bootstrap_hint.json"
RC_CHAIN_OUT="$HANDOFF_DIR/core_rc_input_chain.json"

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
STXY_ACCEPTANCE_DOC="$SANDBOX_ROOT/handoff/2026-03-26_core_harness_review_acceptance.md"
STXY_COMBINED_RC_DOC="$SANDBOX_ROOT/handoff/2026-03-26_combined_rc_handoff_checklist.md"
STXY_RELEASER_DOC="$SANDBOX_ROOT/handoff/2026-03-26_releaser_cutover_checklist.md"
RUNNER_PATH="$ROOT/scripts/run_workspace_ha_core_contract_tests.sh"
SYNC_CHECKER_PATH="$ROOT/scripts/check_15_2_0_sync_anchor_consistency.sh"
SYNC_ANCHOR_DOC="$ROOT/docs/CORE_15_2_0_SYNC_ANCHOR_2026-03-27.md"
CORE_BUILDER_HANDOFF_DOC="$ROOT/docs/CORE_BUILDER_HANDOFF_2026-03-27.md"
CORE_REVIEW_PACKET_DOC="$ROOT/docs/CORE_REVIEW_PACKET_2026-03-27.md"
CORE_RELEASE_INPUT_DOC="$ROOT/docs/CORE_RELEASE_INPUT_2026-03-27.md"
CORE_GITHUB_RELEASE_NOTES_DOC="$ROOT/docs/CORE_GITHUB_RELEASE_NOTES_INPUT_2026-03-27.md"
CORE_RELEASE_QUEUE_STATUS_DOC="$ROOT/docs/CORE_RELEASE_QUEUE_STATUS_2026-03-28.md"
CORE_RELEASE_GOVERNANCE_DOC="$ROOT/docs/CORE_RELEASE_GOVERNANCE_CHECKLIST_2026-03-28.md"
CORE_REAL_RELEASE_RUNBOOK_DOC="$ROOT/docs/CORE_REAL_RELEASE_RUNBOOK_2026-03-28.md"
CORE_POINTER_DOC="$ROOT/docs/CORE_15_2_0_RELEASER_PREP_POINTER_2026-03-27.md"
CORE_RELEASE_MANIFEST_DOC="$ROOT/docs/CORE_15_2_0_RELEASE_MANIFEST_2026-03-27.json"
WORKSPACE_RELEASE_ENTRYPOINT="$HANDOFF_DIR/core_release_entrypoint.json"
TEST_FILE_PATH="$ROOT/tests/integration/test_workspace_ha_core_contract.py"
EVIDENCE_LOG="$HANDOFF_DIR/core_workspace_harness_last_run.log"
PAIRED_CUTOVER_REF="$(sed -n 's/^EXPECTED_PAIRED_CORE_REF="\([^"]*\)"/\1/p' "$SYNC_CHECKER_PATH" | head -n 1)"

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

RC_INPUT_CHAIN_JSON='  [
    {"commit": "be2bcb1c", "role": "zone presence + neuron feeding surface exports"},
    {"commit": "f213b16e", "role": "workspace HA-core contract lane"},
    {"commit": "29a0a7b1", "role": "workspace HA contract runner hardening"},
    {"commit": "5d9b3837", "role": "zone sync bound into workspace harness"},
    {"commit": "e705646c", "role": "fallback-lane fixtures bound into ingest harness"},
    {"commit": "0b280672", "role": "workspace fixtures bound to events ingest endpoint"},
    {"commit": "6441ad0a", "role": "workspace handoff target export"},
    {"commit": "2faad979", "role": "release pairing input export"},
    {"commit": "274d52c1", "role": "workspace harness evidence status export"},
    {"commit": "5299a72a", "role": "workspace harness evidence writeback"},
    {"commit": "9bac0be7", "role": "harness auto-run evidence capture"},
    {"commit": "5863bb65", "role": "bootstrap hint attached to pairing exports"}
  ]'

HARNESS_LAST_RESULT_RAW="${WORKSPACE_HARNESS_LAST_RESULT:-}"
HARNESS_LAST_RESULT_SOURCE_RAW="${WORKSPACE_HARNESS_LAST_RESULT_SOURCE:-}"

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

if [[ "${WORKSPACE_HARNESS_AUTO_RUN:-0}" == "1" ]]; then
  if [[ "$PYTEST_AVAILABLE" == true ]]; then
    if "$RUNNER_PATH" >"$EVIDENCE_LOG" 2>&1; then
      HARNESS_LAST_RESULT_RAW="pass"
      HARNESS_LAST_RESULT_SOURCE_RAW="auto-run:$RUNNER_PATH"
      EVIDENCE_STATUS="passed"
      EVIDENCE_NEXT_ACTION="pair this passing workspace evidence with the next HA release candidate"
    else
      HARNESS_LAST_RESULT_RAW="fail"
      HARNESS_LAST_RESULT_SOURCE_RAW="auto-run:$RUNNER_PATH"
      EVIDENCE_STATUS="failed"
      EVIDENCE_NEXT_ACTION="inspect $EVIDENCE_LOG and fix the failing workspace harness"
    fi
  else
    : >"$EVIDENCE_LOG"
    printf '%s\n' 'auto-run blocked: pytest unavailable in workspace environment' >"$EVIDENCE_LOG"
    if [[ -z "$HARNESS_LAST_RESULT_RAW" ]]; then
      HARNESS_LAST_RESULT_RAW="auto-run blocked: pytest unavailable"
    fi
    if [[ -z "$HARNESS_LAST_RESULT_SOURCE_RAW" ]]; then
      HARNESS_LAST_RESULT_SOURCE_RAW="auto-run-guard"
    fi
  fi
fi

HARNESS_LAST_RESULT_JSON="$(json_string_or_null "$HARNESS_LAST_RESULT_RAW")"
HARNESS_LAST_RESULT_SOURCE_JSON="$(json_string_or_null "$HARNESS_LAST_RESULT_SOURCE_RAW")"

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
  "release_readiness": {
    "paired_cutover_ref": "$PAIRED_CUTOVER_REF",
    "single_entrypoint_doc": "$CORE_POINTER_DOC",
    "release_manifest_doc": "$CORE_RELEASE_MANIFEST_DOC",
    "workspace_release_entrypoint": "$WORKSPACE_RELEASE_ENTRYPOINT",
    "sync_anchor_doc": "$SYNC_ANCHOR_DOC",
    "sync_checker": "$SYNC_CHECKER_PATH",
    "core_builder_handoff": "$CORE_BUILDER_HANDOFF_DOC",
    "core_review_packet": "$CORE_REVIEW_PACKET_DOC",
    "core_release_input": "$CORE_RELEASE_INPUT_DOC",
    "core_github_release_notes_input": "$CORE_GITHUB_RELEASE_NOTES_DOC",
    "core_release_queue_status": "$CORE_RELEASE_QUEUE_STATUS_DOC",
    "core_release_governance_checklist": "$CORE_RELEASE_GOVERNANCE_DOC",
    "core_real_release_runbook": "$CORE_REAL_RELEASE_RUNBOOK_DOC",
    "contract_bundle_runner": "$ROOT/scripts/run_core_contract_bundle.sh",
    "release_queue_status_doc": "$CORE_RELEASE_QUEUE_STATUS_DOC",
    "release_governance_checklist_doc": "$CORE_RELEASE_GOVERNANCE_DOC",
    "real_release_runbook_doc": "$CORE_REAL_RELEASE_RUNBOOK_DOC"
  },
  "shared_sandbox_artifacts": {
    "fixtures": [
      "$SANDBOX_ROOT/fixtures/ha_events/canonical_state_changed.json",
      "$SANDBOX_ROOT/fixtures/ha_events/legacy_state_changed.json",
      "$SANDBOX_ROOT/fixtures/ha_events/call_service.json",
      "$SANDBOX_ROOT/fixtures/ha_events/zone_definitions.json"
    ],
    "handoff_note": "$SANDBOX_HANDOFF",
    "evidence_file": "$EVIDENCE_OUT",
    "evidence_log": "$EVIDENCE_LOG",
    "bootstrap_hint": "$BOOTSTRAP_HINT_OUT",
    "rc_input_chain": "$RC_CHAIN_OUT"
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
    "paired_cutover_ref": "$PAIRED_CUTOVER_REF",
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
    "core_release_entrypoint": "$WORKSPACE_RELEASE_ENTRYPOINT",
    "core_release_manifest": "$CORE_RELEASE_MANIFEST_DOC",
    "core_handoff_note": "$SANDBOX_HANDOFF",
    "core_harness_evidence": "$EVIDENCE_OUT",
    "core_harness_log": "$EVIDENCE_LOG",
    "core_bootstrap_hint": "$BOOTSTRAP_HINT_OUT",
    "core_rc_input_chain": "$RC_CHAIN_OUT",
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
  },
  "core_release_readiness": {
    "single_entrypoint_doc": "$CORE_POINTER_DOC",
    "release_manifest_doc": "$CORE_RELEASE_MANIFEST_DOC",
    "workspace_release_entrypoint": "$WORKSPACE_RELEASE_ENTRYPOINT",
    "sync_anchor_doc": "$SYNC_ANCHOR_DOC",
    "sync_checker": "$SYNC_CHECKER_PATH",
    "contract_bundle_runner": "$ROOT/scripts/run_core_contract_bundle.sh",
    "release_queue_status_doc": "$CORE_RELEASE_QUEUE_STATUS_DOC",
    "release_governance_checklist_doc": "$CORE_RELEASE_GOVERNANCE_DOC",
    "real_release_runbook_doc": "$CORE_REAL_RELEASE_RUNBOOK_DOC",
    "paired_cutover_ref": "$PAIRED_CUTOVER_REF"
  }
}
EOF

cat > "$EVIDENCE_OUT" <<EOF
{
  "generated_at_utc": "$TIMESTAMP",
  "owner_lane": "PilotClaw",
  "core_target_commit": "$HEAD_COMMIT",
  "paired_cutover_ref": "$PAIRED_CUTOVER_REF",
  "runner": "$RUNNER_PATH",
  "sync_checker": "$SYNC_CHECKER_PATH",
  "sync_anchor_doc": "$SYNC_ANCHOR_DOC",
  "test_file": "$TEST_FILE_PATH",
  "log_file": "$EVIDENCE_LOG",
  "rc_input_chain": "$RC_CHAIN_OUT",
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
    "optional writeback via WORKSPACE_HARNESS_LAST_RESULT and WORKSPACE_HARNESS_LAST_RESULT_SOURCE",
    "uses the same canonical core_rc_input_chain.json as target and pairing exports"
  ],
  "release_readiness": {
    "single_entrypoint_doc": "$CORE_POINTER_DOC",
    "release_manifest_doc": "$CORE_RELEASE_MANIFEST_DOC",
    "workspace_release_entrypoint": "$WORKSPACE_RELEASE_ENTRYPOINT",
    "sync_anchor_doc": "$SYNC_ANCHOR_DOC",
    "sync_checker": "$SYNC_CHECKER_PATH",
    "contract_bundle_runner": "$ROOT/scripts/run_core_contract_bundle.sh",
    "release_queue_status_doc": "$CORE_RELEASE_QUEUE_STATUS_DOC",
    "release_governance_checklist_doc": "$CORE_RELEASE_GOVERNANCE_DOC",
    "real_release_runbook_doc": "$CORE_REAL_RELEASE_RUNBOOK_DOC"
  }
}
EOF

cat > "$RC_CHAIN_OUT" <<EOF
{
  "generated_at_utc": "$TIMESTAMP",
  "owner_lane": "PilotClaw",
  "current_head_commit": "$HEAD_COMMIT",
  "paired_cutover_ref": "$PAIRED_CUTOVER_REF",
  "current_status": "$AHEAD_STATUS",
  "accepted_rc_input_chain": $RC_INPUT_CHAIN_JSON,
  "reviewer_acceptance": {
    "core_harness_review_acceptance": "$STXY_ACCEPTANCE_DOC",
    "combined_rc_handoff_checklist": "$STXY_COMBINED_RC_DOC",
    "releaser_cutover_checklist": "$STXY_RELEASER_DOC"
  },
  "notes": [
    "machine-readable core commit chain for HomeClaw/Stxy pairing",
    "shared sandbox reviewer lane has accepted this chain as RC input",
    "no live-install claim implied"
  ],
  "release_readiness_commands": {
    "sync_checker": "$SYNC_CHECKER_PATH",
    "contract_bundle": "$ROOT/scripts/run_core_contract_bundle.sh"
  },
  "release_readiness_docs": {
    "pointer": "$CORE_POINTER_DOC",
    "manifest": "$CORE_RELEASE_MANIFEST_DOC",
    "sync_anchor": "$SYNC_ANCHOR_DOC",
    "builder_handoff": "$CORE_BUILDER_HANDOFF_DOC",
    "review_packet": "$CORE_REVIEW_PACKET_DOC",
    "release_input": "$CORE_RELEASE_INPUT_DOC",
    "github_release_notes_input": "$CORE_GITHUB_RELEASE_NOTES_DOC",
    "release_queue_status": "$CORE_RELEASE_QUEUE_STATUS_DOC",
    "release_governance_checklist": "$CORE_RELEASE_GOVERNANCE_DOC",
    "real_release_runbook": "$CORE_REAL_RELEASE_RUNBOOK_DOC"
  }
}
EOF

echo "$OUT"
echo "$PAIR_OUT"
echo "$EVIDENCE_OUT"
echo "$RC_CHAIN_OUT"
