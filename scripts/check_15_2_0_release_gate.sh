#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

EXPECTED_VERSION="15.2.0"
QUEUE_DOC="docs/CORE_RELEASE_QUEUE_STATUS_2026-03-28.md"
GOVERNANCE_DOC="docs/CORE_RELEASE_GOVERNANCE_CHECKLIST_2026-03-28.md"
MANIFEST_PATH="docs/CORE_15_2_0_RELEASE_MANIFEST_2026-03-27.json"
CURRENT_HEAD="$(git rev-parse --short=8 HEAD)"

failures=0

printf 'Core 15.2.0 strict release gate\n'
printf 'Repo: %s\n' "$REPO_ROOT"
printf 'Current HEAD: %s\n' "$CURRENT_HEAD"

if [[ -n "$(git status --porcelain)" ]]; then
  printf 'FAIL worktree is not clean\n'
  failures=$((failures + 1))
else
  printf 'PASS worktree clean\n'
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

./scripts/check_15_2_0_releaser_pointers.sh
./scripts/check_15_2_0_sync_anchor_consistency.sh
./scripts/run_core_contract_bundle.sh

manifest_head="$(python3 - <<'PY'
import json
from pathlib import Path
print(json.loads(Path('docs/CORE_15_2_0_RELEASE_MANIFEST_2026-03-27.json').read_text(encoding='utf-8')).get('head_commit', ''))
PY
)"

if [[ "$manifest_head" == "$CURRENT_HEAD" ]]; then
  printf 'PASS release manifest head matches current HEAD (%s)\n' "$CURRENT_HEAD"
else
  printf 'FAIL release manifest head=%s differs from current HEAD=%s\n' "$manifest_head" "$CURRENT_HEAD"
  printf 'HINT run ./scripts/refresh_15_2_0_release_surfaces.sh and commit/amend the refreshed manifest before a real cut\n'
  failures=$((failures + 1))
fi

if [[ "$failures" -ne 0 ]]; then
  exit 1
fi

printf 'PASS strict release gate green\n'
printf 'NEXT real release governance step would still be: mache v15.2.0 -> wait 5 minutes -> release lock -> rerun this gate\n'
