#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

POINTER_DOC="docs/CORE_15_2_0_RELEASER_PREP_POINTER_2026-03-27.md"
EXPECTED_CORE_SOURCE="/config/clawd/team/repos/pilotsuite-styx-core"
EXPECTED_PAIRED_REF="8b017a74"

DOC_PATHS=(
  "docs/CORE_15_2_0_RELEASE_MANIFEST_2026-03-27.json"
  "docs/CORE_15_2_0_SYNC_ANCHOR_2026-03-27.md"
  "docs/CORE_15_2_0_BUILDER_HANDOFF_2026-03-27.md"
  "docs/CORE_REVIEW_PACKET_2026-03-27.md"
  "docs/CORE_RELEASE_INPUT_2026-03-27.md"
  "docs/CORE_GITHUB_RELEASE_NOTES_INPUT_2026-03-27.md"
  "docs/HA_RELEASE_CONTRACT_HANDOFF_2026-03-27.md"
)

SCRIPT_PATHS=(
  "scripts/export_15_2_0_release_manifest.sh"
  "scripts/check_15_2_0_sync_anchor_consistency.sh"
  "scripts/run_core_contract_bundle.sh"
  "scripts/check_15_2_0_releaser_pointers.sh"
)

EXPORT_PATHS=(
  "/config/clawd/team/workspaces/pilotsuite-stxy-sandbox/handoff/core_workspace_target.json"
  "/config/clawd/team/workspaces/pilotsuite-stxy-sandbox/handoff/core_release_pairing.json"
  "/config/clawd/team/workspaces/pilotsuite-stxy-sandbox/handoff/core_workspace_harness_evidence.json"
  "/config/clawd/team/workspaces/pilotsuite-stxy-sandbox/handoff/core_rc_input_chain.json"
)

failures=0

printf 'Core 15.2.0 releaser-pointer check\n'
printf 'Repo: %s\n' "$REPO_ROOT"

if [[ ! -f "$POINTER_DOC" ]]; then
  printf 'FAIL missing %s\n' "$POINTER_DOC"
  exit 1
fi

if grep -Fq "$EXPECTED_CORE_SOURCE" "$POINTER_DOC"; then
  printf 'PASS pointer authoritative source\n'
else
  printf 'FAIL pointer missing authoritative source\n'
  failures=$((failures + 1))
fi

if grep -Fq "$EXPECTED_PAIRED_REF" "$POINTER_DOC"; then
  printf 'PASS pointer paired-ref=%s\n' "$EXPECTED_PAIRED_REF"
else
  printf 'FAIL pointer missing paired-ref %s\n' "$EXPECTED_PAIRED_REF"
  failures=$((failures + 1))
fi

for path in "${DOC_PATHS[@]}"; do
  if grep -Fq "$path" "$POINTER_DOC"; then
    printf 'PASS pointer doc-ref %s\n' "$path"
  else
    printf 'FAIL pointer missing doc-ref %s\n' "$path"
    failures=$((failures + 1))
  fi
  [[ -f "$path" ]] || { printf 'FAIL missing %s\n' "$path"; failures=$((failures + 1)); }
done

for path in "${SCRIPT_PATHS[@]}"; do
  if grep -Fq "$path" "$POINTER_DOC"; then
    printf 'PASS pointer script-ref %s\n' "$path"
  else
    printf 'FAIL pointer missing script-ref %s\n' "$path"
    failures=$((failures + 1))
  fi
  [[ -f "$path" ]] || { printf 'FAIL missing %s\n' "$path"; failures=$((failures + 1)); }
done

for path in "${EXPORT_PATHS[@]}"; do
  if grep -Fq "$path" "$POINTER_DOC"; then
    printf 'PASS pointer export-ref %s\n' "$path"
  else
    printf 'FAIL pointer missing export-ref %s\n' "$path"
    failures=$((failures + 1))
  fi
  [[ -f "$path" ]] || { printf 'FAIL missing %s\n' "$path"; failures=$((failures + 1)); }
done

if [[ "$failures" -ne 0 ]]; then
  exit 1
fi
