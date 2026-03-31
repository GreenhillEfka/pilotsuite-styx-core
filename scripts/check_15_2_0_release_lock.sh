#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

LOCK_PATH="$REPO_ROOT/RELEASE_LOCK.md"
EXPECTED_VERSION="v15.2.0"
EXPECTED_PAIRED_REF="8b017a74"
EXPECTED_ANNOUNCE='mache v15.2.0'
CURRENT_HEAD="$(git rev-parse --short=8 HEAD)"

failures=0

printf 'Core 15.2.0 release-lock check\n'
printf 'Repo: %s\n' "$REPO_ROOT"

if [[ ! -f "$LOCK_PATH" ]]; then
  printf 'FAIL missing %s\n' "$LOCK_PATH"
  exit 1
fi

for expected in "$EXPECTED_VERSION" "$EXPECTED_PAIRED_REF" "$EXPECTED_ANNOUNCE" 'status: `active`'; do
  if grep -Fq "$expected" "$LOCK_PATH"; then
    printf 'PASS lock contains %s\n' "$expected"
  else
    printf 'FAIL lock missing %s\n' "$expected"
    failures=$((failures + 1))
  fi
done

LOCK_HEAD="$(sed -n 's/^- head_commit: `\([^`]*\)`/\1/p' "$LOCK_PATH" | head -n 1)"
if [[ -n "$LOCK_HEAD" && "$LOCK_HEAD" == "$CURRENT_HEAD" ]]; then
  printf 'PASS lock head matches current HEAD (%s)\n' "$CURRENT_HEAD"
else
  printf 'FAIL lock head=%s differs from current HEAD=%s\n' "${LOCK_HEAD:-<missing>}" "$CURRENT_HEAD"
  failures=$((failures + 1))
fi

python3 - <<'PY' "$LOCK_PATH"
from datetime import datetime, timezone, timedelta
from pathlib import Path
import re, sys
text = Path(sys.argv[1]).read_text(encoding='utf-8')
ann = re.search(r'- announcement_at_utc: `([^`]+)`', text)
created = re.search(r'- created_at_utc: `([^`]+)`', text)
if not ann:
    print('FAIL lock missing announcement_at_utc')
    raise SystemExit(2)
if not created:
    print('FAIL lock missing created_at_utc')
    raise SystemExit(2)
announced_at = datetime.fromisoformat(ann.group(1).replace('Z', '+00:00'))
created_at = datetime.fromisoformat(created.group(1).replace('Z', '+00:00'))
if announced_at > created_at:
    print('FAIL lock announcement_at_utc is later than created_at_utc')
    raise SystemExit(4)
now = datetime.now(timezone.utc)
remaining = announced_at + timedelta(minutes=5) - now
if remaining.total_seconds() <= 0:
    print('PASS lock wait window elapsed since announcement_at_utc')
else:
    print(f'FAIL lock wait window not elapsed since announcement_at_utc; remaining_seconds={int(remaining.total_seconds())}')
    raise SystemExit(3)
PY
rc=$?
if [[ $rc -ne 0 ]]; then
  failures=$((failures + 1))
fi

if [[ "$failures" -ne 0 ]]; then
  exit 1
fi
