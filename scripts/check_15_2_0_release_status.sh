#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

DOC_STATUS_PATH="docs/CORE_15_2_0_RELEASE_STATUS_2026-03-28.json"
WORKSPACE_STATUS_PATH="/config/clawd/team/workspaces/pilotsuite-stxy-sandbox/handoff/core_release_status.json"
CURRENT_HEAD="$(git rev-parse --short=8 HEAD)"
EXPECTED_VERSION="$(tr -d '[:space:]' < VERSION)"
EXPECTED_PAIRED_REF="8b017a74"

failures=0

printf 'Core 15.2.9 release-status check\n'
printf 'Repo: %s\n' "$REPO_ROOT"
printf 'Current HEAD: %s\n' "$CURRENT_HEAD"

for path in "$DOC_STATUS_PATH" "$WORKSPACE_STATUS_PATH"; do
  if [[ -f "$path" ]]; then
    printf 'PASS present %s\n' "$path"
  else
    printf 'FAIL missing %s\n' "$path"
    failures=$((failures + 1))
  fi
done

if python3 - <<'PY'
import json
from pathlib import Path
root_status = json.loads(Path('docs/CORE_15_2_0_RELEASE_STATUS_2026-03-28.json').read_text(encoding='utf-8'))
workspace_status = json.loads(Path('/config/clawd/team/workspaces/pilotsuite-stxy-sandbox/handoff/core_release_status.json').read_text(encoding='utf-8'))
assert root_status.get('kind') == 'core_release_status'
assert workspace_status.get('kind') == 'core_release_status'
assert workspace_status.get('candidate_version') == Path('VERSION').read_text(encoding='utf-8').strip()
assert workspace_status.get('paired_cutover_ref') == '8b017a74'
assert isinstance(workspace_status.get('commands'), dict)
assert isinstance(workspace_status.get('docs'), dict)
assert 'strict_release_gate' in workspace_status['commands']
assert 'create_release_lock' in workspace_status['commands']
assert 'check_release_lock' in workspace_status['commands']
assert 'clear_release_lock' in workspace_status['commands']
assert 'runbook' in workspace_status['docs']
assert 'queue_status' in workspace_status['docs']
assert 'queue_state' in workspace_status
assert 'next_visible_step' in workspace_status
lock = workspace_status.get('release_lock', {})
queue_state = workspace_status.get('queue_state')
next_step = workspace_status.get('next_visible_step')
if not lock.get('present'):
    assert queue_state == 'unlocked'
    assert next_step == 'mache v15.2.9'
elif not lock.get('valid'):
    assert queue_state == 'locked-invalid'
    assert next_step == 'fix or clear RELEASE_LOCK.md before any cut discussion'
elif lock.get('wait_elapsed'):
    assert queue_state == 'locked-ready-for-gate'
    assert next_step == 'rerun strict release gate and decide on workflow dispatch'
else:
    assert queue_state == 'locked-waiting'
    assert next_step == 'continue waiting until the 5-minute post-announcement window elapses'
PY
then
  printf 'PASS release-status json shape/version/pairing/state-machine checks\n'
else
  printf 'FAIL release-status json shape/version/pairing/state-machine checks\n'
  failures=$((failures + 1))
fi

workspace_head="$(python3 - <<'PY'
import json
from pathlib import Path
print(json.loads(Path('/config/clawd/team/workspaces/pilotsuite-stxy-sandbox/handoff/core_release_status.json').read_text(encoding='utf-8')).get('head_commit', ''))
PY
)"
workspace_version="$(python3 - <<'PY'
import json
from pathlib import Path
print(json.loads(Path('/config/clawd/team/workspaces/pilotsuite-stxy-sandbox/handoff/core_release_status.json').read_text(encoding='utf-8')).get('candidate_version', ''))
PY
)"
workspace_pairing="$(python3 - <<'PY'
import json
from pathlib import Path
print(json.loads(Path('/config/clawd/team/workspaces/pilotsuite-stxy-sandbox/handoff/core_release_status.json').read_text(encoding='utf-8')).get('paired_cutover_ref', ''))
PY
)"
workspace_next_step="$(python3 - <<'PY'
import json
from pathlib import Path
print(json.loads(Path('/config/clawd/team/workspaces/pilotsuite-stxy-sandbox/handoff/core_release_status.json').read_text(encoding='utf-8')).get('next_visible_step', ''))
PY
)"
doc_head="$(python3 - <<'PY'
import json
from pathlib import Path
print(json.loads(Path('docs/CORE_15_2_0_RELEASE_STATUS_2026-03-28.json').read_text(encoding='utf-8')).get('head_commit', ''))
PY
)"

if [[ "$workspace_head" == "$CURRENT_HEAD" ]]; then
  printf 'PASS workspace release-status head matches current HEAD (%s)\n' "$CURRENT_HEAD"
else
  printf 'FAIL workspace release-status head=%s differs from current HEAD=%s\n' "$workspace_head" "$CURRENT_HEAD"
  failures=$((failures + 1))
fi

if [[ "$workspace_version" == "$EXPECTED_VERSION" ]]; then
  printf 'PASS workspace release-status version=%s\n' "$EXPECTED_VERSION"
else
  printf 'FAIL workspace release-status version=%s expected=%s\n' "$workspace_version" "$EXPECTED_VERSION"
  failures=$((failures + 1))
fi

if [[ "$workspace_pairing" == "$EXPECTED_PAIRED_REF" ]]; then
  printf 'PASS workspace release-status paired-ref=%s\n' "$EXPECTED_PAIRED_REF"
else
  printf 'FAIL workspace release-status paired-ref=%s expected=%s\n' "$workspace_pairing" "$EXPECTED_PAIRED_REF"
  failures=$((failures + 1))
fi

if [[ -n "$workspace_next_step" ]]; then
  printf 'PASS workspace release-status next_visible_step=%s\n' "$workspace_next_step"
else
  printf 'FAIL workspace release-status missing next_visible_step\n'
  failures=$((failures + 1))
fi

if [[ "$doc_head" == "$CURRENT_HEAD" ]]; then
  printf 'PASS committed doc release-status head matches current HEAD (%s)\n' "$CURRENT_HEAD"
else
  printf 'NOTE committed doc release-status head=%s differs from current HEAD=%s; workspace release-status is the exact current-head status surface\n' "$doc_head" "$CURRENT_HEAD"
fi

if [[ "$failures" -ne 0 ]]; then
  exit 1
fi
