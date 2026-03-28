#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
SANDBOX_ROOT="$(cd "$ROOT/../.." && pwd)/workspaces/pilotsuite-stxy-sandbox"
HANDOFF_DIR="$SANDBOX_ROOT/handoff"
REPO_OUT="$ROOT/docs/CORE_15_2_0_RELEASE_MANIFEST_2026-03-27.json"
STATUS_DOC="$ROOT/docs/CORE_15_2_0_RELEASE_STATUS_2026-03-28.json"
WORKSPACE_OUT="$HANDOFF_DIR/core_release_entrypoint.json"
WORKSPACE_STATUS="$HANDOFF_DIR/core_release_status.json"
SYNC_CHECKER="$ROOT/scripts/check_15_2_0_sync_anchor_consistency.sh"
POINTER_DOC="$ROOT/docs/CORE_15_2_0_RELEASER_PREP_POINTER_2026-03-27.md"
SYNC_ANCHOR_DOC="$ROOT/docs/CORE_15_2_0_SYNC_ANCHOR_2026-03-27.md"
BUILDER_HANDOFF_DOC="$ROOT/docs/CORE_15_2_0_BUILDER_HANDOFF_2026-03-27.md"
REVIEW_PACKET_DOC="$ROOT/docs/CORE_REVIEW_PACKET_2026-03-27.md"
RELEASE_INPUT_DOC="$ROOT/docs/CORE_RELEASE_INPUT_2026-03-27.md"
GITHUB_RELEASE_NOTES_DOC="$ROOT/docs/CORE_GITHUB_RELEASE_NOTES_INPUT_2026-03-27.md"
QUEUE_STATUS_DOC="$ROOT/docs/CORE_RELEASE_QUEUE_STATUS_2026-03-28.md"
GOVERNANCE_CHECKLIST_DOC="$ROOT/docs/CORE_RELEASE_GOVERNANCE_CHECKLIST_2026-03-28.md"
REAL_RELEASE_RUNBOOK_DOC="$ROOT/docs/CORE_REAL_RELEASE_RUNBOOK_2026-03-28.md"
HA_CONTRACT_HANDOFF_DOC="$ROOT/docs/HA_RELEASE_CONTRACT_HANDOFF_2026-03-27.md"
POINTER_CHECKER="$ROOT/scripts/check_15_2_0_releaser_pointers.sh"
BUNDLE_RUNNER="$ROOT/scripts/run_core_contract_bundle.sh"
STRICT_RELEASE_GATE="$ROOT/scripts/check_15_2_0_release_gate.sh"
RELEASE_STATUS_EXPORT="$ROOT/scripts/export_15_2_0_release_status.sh"
RELEASE_LOCK_CREATE="$ROOT/scripts/create_15_2_0_release_lock.sh"
RELEASE_LOCK_CHECK="$ROOT/scripts/check_15_2_0_release_lock.sh"
RELEASE_LOCK_CLEAR="$ROOT/scripts/clear_15_2_0_release_lock.sh"
EXPORT_CHAIN="$ROOT/scripts/export_workspace_core_handoff.sh"
WORKSPACE_TARGET="$HANDOFF_DIR/core_workspace_target.json"
WORKSPACE_PAIRING="$HANDOFF_DIR/core_release_pairing.json"
WORKSPACE_EVIDENCE="$HANDOFF_DIR/core_workspace_harness_evidence.json"
WORKSPACE_RC_CHAIN="$HANDOFF_DIR/core_rc_input_chain.json"

mkdir -p "$HANDOFF_DIR"

HEAD_COMMIT="$(git -C "$ROOT" rev-parse --short=8 HEAD)"
HEAD_BRANCH="$(git -C "$ROOT" rev-parse --abbrev-ref HEAD)"
VERSION="$(tr -d '[:space:]' < "$ROOT/VERSION")"
TIMESTAMP="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
PAIRED_CUTOVER_REF="$(sed -n 's/^EXPECTED_PAIRED_CORE_REF="\([^"]*\)"/\1/p' "$SYNC_CHECKER" | head -n 1)"

cat > "$REPO_OUT" <<EOF
{
  "generated_at_utc": "$TIMESTAMP",
  "kind": "core_release_readiness_manifest",
  "repo": "$ROOT",
  "branch": "$HEAD_BRANCH",
  "head_commit": "$HEAD_COMMIT",
  "candidate_version": "$VERSION",
  "paired_cutover_ref": "$PAIRED_CUTOVER_REF",
  "single_entrypoint_doc": "$POINTER_DOC",
  "primary_docs": {
    "release_status": "$STATUS_DOC",
    "sync_anchor": "$SYNC_ANCHOR_DOC",
    "builder_handoff": "$BUILDER_HANDOFF_DOC",
    "review_packet": "$REVIEW_PACKET_DOC",
    "release_input": "$RELEASE_INPUT_DOC",
    "github_release_notes_input": "$GITHUB_RELEASE_NOTES_DOC",
    "queue_status": "$QUEUE_STATUS_DOC",
    "governance_checklist": "$GOVERNANCE_CHECKLIST_DOC",
    "real_release_runbook": "$REAL_RELEASE_RUNBOOK_DOC",
    "ha_contract_handoff": "$HA_CONTRACT_HANDOFF_DOC"
  },
  "validation_commands": {
    "releaser_pointer_check": "$POINTER_CHECKER",
    "sync_anchor_check": "$SYNC_CHECKER",
    "contract_bundle": "$BUNDLE_RUNNER",
    "release_status_export": "$RELEASE_STATUS_EXPORT",
    "strict_release_gate": "$STRICT_RELEASE_GATE",
    "release_lock_create": "$RELEASE_LOCK_CREATE",
    "release_lock_check": "$RELEASE_LOCK_CHECK",
    "release_lock_clear": "$RELEASE_LOCK_CLEAR"
  },
  "workspace_exports": {
    "workspace_target": "$WORKSPACE_TARGET",
    "release_status": "$WORKSPACE_STATUS",
    "release_pairing": "$WORKSPACE_PAIRING",
    "harness_evidence": "$WORKSPACE_EVIDENCE",
    "rc_input_chain": "$WORKSPACE_RC_CHAIN"
  },
  "export_chain": {
    "workspace_handoff_exporter": "$EXPORT_CHAIN",
    "release_status_exporter": "$RELEASE_STATUS_EXPORT",
    "workspace_release_entrypoint": "$WORKSPACE_OUT",
    "workspace_release_status": "$WORKSPACE_STATUS"
  },
  "non_claims": [
    "no release",
    "no install",
    "no live-test"
  ]
}
EOF

cp "$REPO_OUT" "$WORKSPACE_OUT"

echo "$REPO_OUT"
echo "$WORKSPACE_OUT"
