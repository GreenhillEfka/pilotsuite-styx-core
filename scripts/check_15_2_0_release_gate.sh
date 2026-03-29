#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

EXPECTED_VERSION="15.2.9"
QUEUE_DOC="docs/CORE_RELEASE_QUEUE_STATUS_2026-03-28.md"
GOVERNANCE_DOC="docs/CORE_RELEASE_GOVERNANCE_CHECKLIST_2026-03-28.md"
MANIFEST_PATH="docs/CORE_15_2_0_RELEASE_MANIFEST_2026-03-27.json"
WORKSPACE_ENTRYPOINT="/config/clawd/team/workspaces/pilotsuite-stxy-sandbox/handoff/core_release_entrypoint.json"
WORKSPACE_STATUS="/config/clawd/team/workspaces/pilotsuite-stxy-sandbox/handoff/core_release_status.json"
RELEASE_LOCK_PATH="RELEASE_LOCK.md"
RELEASE_LOCK_CHECK="./scripts/check_15_2_0_release_lock.sh"
RELEASE_STATUS_EXPORT="./scripts/export_15_2_0_release_status.sh"
RELEASE_STATUS_CHECK="./scripts/check_15_2_0_release_status.sh"
CURRENT_HEAD="$(git rev-parse --short=8 HEAD)"

failures=0

printf 'Core 15.2.9 strict release gate\n'
printf 'Repo: %s\n' "$REPO_ROOT"
printf 'Current HEAD: %s\n' "$CURRENT_HEAD"

WORKTREE_STATUS="$(git status --porcelain)"
WORKTREE_STATUS_FILTERED="$(printf '%s\n' "$WORKTREE_STATUS" | grep -v '^?? RELEASE_LOCK.md$' || true)"

if [[ -n "$WORKTREE_STATUS_FILTERED" ]]; then
  printf 'FAIL worktree is not clean\n'
  failures=$((failures + 1))
else
  if [[ -f "$RELEASE_LOCK_PATH" ]]; then
    printf 'PASS worktree clean (release lock tolerated)\n'
  else
    printf 'PASS worktree clean\n'
  fi
fi

version_root="$(tr -d '[:space:]' < VERSION)"
version_core="$(tr -d '[:space:]' < copilot_core/VERSION)"
version_manifest="$(python3 - <<'PY'
import json
from pathlib import Path
print(json.loads(Path('copilot_core/manifest.json').read_text(encoding='utf-8'))['version'])
PY
)"

if [[ "$version_root" == "$EXPECTED_VERSION" && "$version_core" == "$EXPECTED_VERSION" && "$version_manifest" == "$EXPECTED_VERSION" ]]; then
  printf 'PASS version alignment=%s\n' "$EXPECTED_VERSION"
else
  printf 'FAIL version alignment root=%s core=%s manifest=%s expected=%s\n' "$version_root" "$version_core" "$version_manifest" "$EXPECTED_VERSION"
  failures=$((failures + 1))
fi

for path in "$QUEUE_DOC" "$GOVERNANCE_DOC" "$MANIFEST_PATH"; do
  if [[ -f "$path" ]]; then
    printf 'PASS present %s\n' "$path"
  else
    printf 'FAIL missing %s\n' "$path"
    failures=$((failures + 1))
  fi
done

if [[ -f "$RELEASE_LOCK_PATH" ]]; then
  if "$RELEASE_LOCK_CHECK"; then
    printf 'PASS release lock valid for coordinated cut window\n'
  else
    printf 'FAIL release lock present but invalid\n'
    failures=$((failures + 1))
  fi
else
  printf 'NOTE release lock absent (expected outside an active real-cut window)\n'
fi

./scripts/refresh_15_2_0_release_surfaces.sh >/dev/null
"$RELEASE_STATUS_EXPORT" >/dev/null

if [[ -f "$WORKSPACE_ENTRYPOINT" ]]; then
  printf 'PASS present %s\n' "$WORKSPACE_ENTRYPOINT"
else
  printf 'FAIL missing %s\n' "$WORKSPACE_ENTRYPOINT"
  failures=$((failures + 1))
fi

if [[ -f "$WORKSPACE_STATUS" ]]; then
  printf 'PASS present %s\n' "$WORKSPACE_STATUS"
else
  printf 'FAIL missing %s\n' "$WORKSPACE_STATUS"
  failures=$((failures + 1))
fi

./scripts/check_15_2_0_releaser_pointers.sh
./scripts/check_15_2_0_release_status.sh
./scripts/check_15_2_0_sync_anchor_consistency.sh
./scripts/run_core_contract_bundle.sh

workspace_head="$(python3 - <<'PY'
import json
from pathlib import Path
print(json.loads(Path('/config/clawd/team/workspaces/pilotsuite-stxy-sandbox/handoff/core_release_entrypoint.json').read_text(encoding='utf-8')).get('head_commit', ''))
PY
)"
manifest_head="$(python3 - <<'PY'
import json
from pathlib import Path
print(json.loads(Path('docs/CORE_15_2_0_RELEASE_MANIFEST_2026-03-27.json').read_text(encoding='utf-8')).get('head_commit', ''))
PY
)"

if [[ "$workspace_head" == "$CURRENT_HEAD" ]]; then
  printf 'PASS workspace release entrypoint head matches current HEAD (%s)\n' "$CURRENT_HEAD"
else
  printf 'FAIL workspace release entrypoint head=%s differs from current HEAD=%s\n' "$workspace_head" "$CURRENT_HEAD"
  failures=$((failures + 1))
fi

if [[ "$manifest_head" == "$CURRENT_HEAD" ]]; then
  printf 'PASS committed repo manifest head matches current HEAD (%s)\n' "$CURRENT_HEAD"
else
  printf 'NOTE committed repo manifest head=%s differs from current HEAD=%s; workspace entrypoint is the exact current-head surface for real handoff/cut discussion\n' "$manifest_head" "$CURRENT_HEAD"
fi

if [[ "$failures" -ne 0 ]]; then
  exit 1
fi

printf 'PASS strict release gate green\n'
printf 'NEXT real release governance step would still be: mache v15.2.9 -> wait 5 minutes -> export/check release status -> create/check release lock -> rerun this gate -> workflow dispatch -> clear lock\n'
