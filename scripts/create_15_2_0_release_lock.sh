#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

VERSION="15.2.0"
PAIRED_REF="8b017a74"
ANNOUNCE_TEXT="mache v15.2.0"
LOCK_PATH="$REPO_ROOT/RELEASE_LOCK.md"
OWNER="${1:-${OPENCLAW_AGENT_ID:-${USER:-unknown}}}"
ANNOUNCED_AT_UTC="${2:-${RELEASE_ANNOUNCED_AT_UTC:-}}"
CREATED_AT_UTC="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
HEAD_COMMIT="$(git rev-parse --short=8 HEAD)"
BRANCH="$(git rev-parse --abbrev-ref HEAD)"

if [[ -z "$ANNOUNCED_AT_UTC" ]]; then
  printf 'Usage: %s <owner> <announcement_at_utc>\n' "$(basename "$0")" >&2
  printf 'Example: %s pilotclaw 2026-03-28T03:45:00Z\n' "$(basename "$0")" >&2
  printf 'Or set RELEASE_ANNOUNCED_AT_UTC in the environment.\n' >&2
  exit 2
fi

python3 - <<'PY' "$LOCK_PATH" "$REPO_ROOT" "$VERSION" "$OWNER" "$ANNOUNCE_TEXT" "$ANNOUNCED_AT_UTC" "$CREATED_AT_UTC" "$BRANCH" "$HEAD_COMMIT" "$PAIRED_REF"
from datetime import datetime
from pathlib import Path
import sys

(lock_path, repo_root, version, owner, announce_text, announced_at_utc,
 created_at_utc, branch, head_commit, paired_ref) = sys.argv[1:11]

try:
    announced = datetime.fromisoformat(announced_at_utc.replace('Z', '+00:00'))
    created = datetime.fromisoformat(created_at_utc.replace('Z', '+00:00'))
except Exception as exc:
    print(f'Invalid timestamp: {exc}', file=sys.stderr)
    raise SystemExit(2)

if announced > created:
    print('announcement_at_utc cannot be later than created_at_utc', file=sys.stderr)
    raise SystemExit(2)

content = f"""# Core Release Lock

- repo: `{repo_root}`
- version: `v{version}`
- owner: `{owner}`
- announcement_text: `{announce_text}`
- announcement_at_utc: `{announced_at_utc}`
- created_at_utc: `{created_at_utc}`
- branch: `{branch}`
- head_commit: `{head_commit}`
- paired_cutover_ref: `{paired_ref}`
- required_group_thread_announcement: `{announce_text}`
- wait_rule: `5 minutes after announcement before any real release attempt`
- status: `active`

## Intent
This file marks the Core lane/repo as release-locked for the coordinated `v{version}` cut window.

## Non-claims
- no release has been cut by creating this file
- no install has been performed
- no live-test has been claimed
"""
Path(lock_path).write_text(content, encoding='utf-8')
PY

printf '%s\n' "$LOCK_PATH"
