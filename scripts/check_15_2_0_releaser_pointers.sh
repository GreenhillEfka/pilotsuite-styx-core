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
  "docs/CORE_RELEASE_QUEUE_STATUS_2026-03-28.md"
  "docs/CORE_RELEASE_GOVERNANCE_CHECKLIST_2026-03-28.md"
  "docs/CORE_REAL_RELEASE_RUNBOOK_2026-03-28.md"
  "docs/HA_RELEASE_CONTRACT_HANDOFF_2026-03-27.md"
)

SCRIPT_PATHS=(
  "scripts/export_15_2_0_release_manifest.sh"
  "scripts/refresh_15_2_0_release_surfaces.sh"
  "scripts/check_15_2_0_sync_anchor_consistency.sh"
  "scripts/run_core_contract_bundle.sh"
  "scripts/check_15_2_0_releaser_pointers.sh"
  "scripts/check_15_2_0_release_gate.sh"
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

CURRENT_HEAD="$(git rev-parse --short=8 HEAD)"
MANIFEST_HEAD="$(python3 - <<'PY'
import json
from pathlib import Path
path = Path('docs/CORE_15_2_0_RELEASE_MANIFEST_2026-03-27.json')
try:
    print(json.loads(path.read_text(encoding='utf-8')).get('head_commit', ''))
except Exception:
    print('')
PY
)"

if python3 - <<'PY'
import json
from pathlib import Path
entry = Path('/config/clawd/team/workspaces/pilotsuite-stxy-sandbox/handoff/core_release_entrypoint.json')
target = Path('/config/clawd/team/workspaces/pilotsuite-stxy-sandbox/handoff/core_workspace_target.json')
rc = Path('/config/clawd/team/workspaces/pilotsuite-stxy-sandbox/handoff/core_rc_input_chain.json')
entry_data = json.loads(entry.read_text(encoding='utf-8'))
target_data = json.loads(target.read_text(encoding='utf-8'))
rc_data = json.loads(rc.read_text(encoding='utf-8'))
assert 'queue_status' in entry_data['primary_docs']
assert 'governance_checklist' in entry_data['primary_docs']
assert 'real_release_runbook' in entry_data['primary_docs']
assert 'strict_release_gate' in entry_data['validation_commands']
rr = target_data['release_readiness']
assert 'core_release_queue_status' in rr
assert 'core_release_governance_checklist' in rr
assert 'core_real_release_runbook' in rr
rc_commands = rc_data['release_readiness_commands']
assert 'releaser_pointer_check' in rc_commands
assert 'strict_release_gate' in rc_commands
rc_docs = rc_data['release_readiness_docs']
assert 'release_queue_status' in rc_docs
assert 'release_governance_checklist' in rc_docs
assert 'real_release_runbook' in rc_docs
PY
then
  printf 'PASS workspace release surfaces expose queue/governance/runbook + strict-gate metadata\n'
else
  printf 'FAIL workspace release surfaces missing queue/governance/runbook or strict-gate metadata\n'
  failures=$((failures + 1))
fi

if [[ -n "$MANIFEST_HEAD" && "$MANIFEST_HEAD" == "$CURRENT_HEAD" ]]; then
  printf 'PASS manifest head matches current HEAD (%s)\n' "$CURRENT_HEAD"
else
  printf 'NOTE manifest snapshot head=%s differs from current HEAD=%s; use ./scripts/check_15_2_0_release_gate.sh and the refreshed workspace release entrypoint as the exact real-cut surface\n' "${MANIFEST_HEAD:-<missing>}" "$CURRENT_HEAD"
fi

if [[ "$failures" -ne 0 ]]; then
  exit 1
fi
