#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

LOCK_PATH="$REPO_ROOT/RELEASE_LOCK.md"

if [[ -f "$LOCK_PATH" ]]; then
  rm -f "$LOCK_PATH"
  printf 'Cleared %s\n' "$LOCK_PATH"
else
  printf 'No active release lock at %s\n' "$LOCK_PATH"
fi
