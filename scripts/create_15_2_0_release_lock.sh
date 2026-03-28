#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

VERSION="15.2.0"
PAIRED_REF="8b017a74"
LOCK_PATH="$REPO_ROOT/RELEASE_LOCK.md"
OWNER="${1:-${OPENCLAW_AGENT_ID:-${USER:-unknown}}}"
CREATED_AT_UTC="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
HEAD_COMMIT="$(git rev-parse --short=8 HEAD)"
BRANCH="$(git rev-parse --abbrev-ref HEAD)"

cat > "$LOCK_PATH" <<EOF
# Core Release Lock

- repo: `$REPO_ROOT`
- version: `v$VERSION`
- owner: `$OWNER`
- created_at_utc: `$CREATED_AT_UTC`
- branch: `$BRANCH`
- head_commit: `$HEAD_COMMIT`
- paired_cutover_ref: `$PAIRED_REF`
- required_group_thread_announcement: `mache v$VERSION`
- wait_rule: `5 minutes before any real release attempt`
- status: `active`

## Intent
This file marks the Core lane/repo as release-locked for the coordinated `v$VERSION` cut window.

## Non-claims
- no release has been cut by creating this file
- no install has been performed
- no live-test has been claimed
EOF

printf '%s\n' "$LOCK_PATH"
