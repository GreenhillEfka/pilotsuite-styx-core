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

python3 - <<'PY' "$ANNOUNCED_AT_UTC"
from datetime import datetime
import sys
try:
    datetime.fromisoformat(sys.argv[1].replace('Z', '+00:00'))
except Exception as exc:
    print(f'Invalid announcement_at_utc: {sys.argv[1]} ({exc})', file=sys.stderr)
    raise SystemExit(2)
PY

cat > "$LOCK_PATH" <<EOF
# Core Release Lock

- repo: `$REPO_ROOT`
- version: `v$VERSION`
- owner: `$OWNER`
- announcement_text: `$ANNOUNCE_TEXT`
- announcement_at_utc: `$ANNOUNCED_AT_UTC`
- created_at_utc: `$CREATED_AT_UTC`
- branch: `$BRANCH`
- head_commit: `$HEAD_COMMIT`
- paired_cutover_ref: `$PAIRED_REF`
- required_group_thread_announcement: `$ANNOUNCE_TEXT`
- wait_rule: `5 minutes after announcement before any real release attempt`
- status: `active`

## Intent
This file marks the Core lane/repo as release-locked for the coordinated `v$VERSION` cut window.

## Non-claims
- no release has been cut by creating this file
- no install has been performed
- no live-test has been claimed
EOF

printf '%s\n' "$LOCK_PATH"
