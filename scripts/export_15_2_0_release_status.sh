#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
SANDBOX_ROOT="$(cd "$ROOT/../.." && pwd)/workspaces/pilotsuite-stxy-sandbox"
HANDOFF_DIR="$SANDBOX_ROOT/handoff"
DOC_OUT_REL="docs/CORE_15_2_0_RELEASE_STATUS_2026-03-28.json"
DOC_OUT="$ROOT/$DOC_OUT_REL"
WORKSPACE_OUT="$HANDOFF_DIR/core_release_status.json"
LOCK_PATH="$ROOT/RELEASE_LOCK.md"
PAIRING_REF="8b017a74"
VERSION="$(tr -d '[:space:]' < "$ROOT/VERSION")"
HEAD_COMMIT="$(git -C "$ROOT" rev-parse --short=8 HEAD)"
HEAD_BRANCH="$(git -C "$ROOT" rev-parse --abbrev-ref HEAD)"
TIMESTAMP="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
STRICT_GATE="$ROOT/scripts/check_15_2_0_release_gate.sh"
CREATE_LOCK="$ROOT/scripts/create_15_2_0_release_lock.sh"
CHECK_LOCK="$ROOT/scripts/check_15_2_0_release_lock.sh"
CLEAR_LOCK="$ROOT/scripts/clear_15_2_0_release_lock.sh"
RUNBOOK_DOC="$ROOT/docs/CORE_REAL_RELEASE_RUNBOOK_2026-03-28.md"
QUEUE_DOC="$ROOT/docs/CORE_RELEASE_QUEUE_STATUS_2026-03-28.md"

mkdir -p "$HANDOFF_DIR"

WORKTREE_STATUS="$(git -C "$ROOT" status --porcelain)"
WORKTREE_STATUS_FILTERED="$(printf '%s\n' "$WORKTREE_STATUS" | grep -v '^?? RELEASE_LOCK.md$' || true)"
if [[ -n "$WORKTREE_STATUS_FILTERED" ]]; then
  WORKTREE_CLEAN=false
else
  WORKTREE_CLEAN=true
fi

python3 - <<'PY' "$DOC_OUT" "$WORKSPACE_OUT" "$ROOT" "$HEAD_BRANCH" "$HEAD_COMMIT" "$VERSION" "$PAIRING_REF" "$TIMESTAMP" "$LOCK_PATH" "$WORKTREE_CLEAN" "$STRICT_GATE" "$CREATE_LOCK" "$CHECK_LOCK" "$CLEAR_LOCK" "$RUNBOOK_DOC" "$QUEUE_DOC"
from datetime import datetime, timezone, timedelta
from pathlib import Path
import json, re, sys
(
    doc_out, workspace_out, root, branch, head_commit, version, pairing_ref, timestamp,
    lock_path, worktree_clean_raw, strict_gate, create_lock, check_lock, clear_lock,
    runbook_doc, queue_doc,
) = sys.argv[1:17]

worktree_clean = worktree_clean_raw.lower() == 'true'
lock_file = Path(lock_path)
status = {
    "generated_at_utc": timestamp,
    "kind": "core_release_status",
    "repo": root,
    "branch": branch,
    "head_commit": head_commit,
    "candidate_version": version,
    "paired_cutover_ref": pairing_ref,
    "worktree_clean_excluding_lock": worktree_clean,
    "commands": {
        "strict_release_gate": strict_gate,
        "create_release_lock": create_lock,
        "check_release_lock": check_lock,
        "clear_release_lock": clear_lock,
    },
    "docs": {
        "runbook": runbook_doc,
        "queue_status": queue_doc,
    },
}

lock = {
    "present": lock_file.exists(),
    "valid": False,
    "owner": None,
    "announcement_text": None,
    "announcement_at_utc": None,
    "created_at_utc": None,
    "head_commit": None,
    "wait_elapsed": False,
    "remaining_seconds": None,
}

if lock_file.exists():
    text = lock_file.read_text(encoding='utf-8')
    def extract(pattern):
        m = re.search(pattern, text)
        return m.group(1) if m else None
    lock["owner"] = extract(r'- owner: `([^`]+)`')
    lock["announcement_text"] = extract(r'- announcement_text: `([^`]+)`')
    lock["announcement_at_utc"] = extract(r'- announcement_at_utc: `([^`]+)`')
    lock["created_at_utc"] = extract(r'- created_at_utc: `([^`]+)`')
    lock["head_commit"] = extract(r'- head_commit: `([^`]+)`')
    try:
        announced = datetime.fromisoformat(lock["announcement_at_utc"].replace('Z', '+00:00')) if lock["announcement_at_utc"] else None
        created = datetime.fromisoformat(lock["created_at_utc"].replace('Z', '+00:00')) if lock["created_at_utc"] else None
        now = datetime.now(timezone.utc)
        if announced and created and announced <= created:
            remaining = int((announced + timedelta(minutes=5) - now).total_seconds())
            lock["remaining_seconds"] = max(0, remaining)
            lock["wait_elapsed"] = remaining <= 0
        else:
            lock["remaining_seconds"] = None
            lock["wait_elapsed"] = False
    except Exception:
        lock["remaining_seconds"] = None
        lock["wait_elapsed"] = False
    lock["valid"] = (
        lock["announcement_text"] == 'mache v15.2.0'
        and lock["head_commit"] == head_commit
        and lock["announcement_at_utc"] is not None
        and lock["created_at_utc"] is not None
    )

status["release_lock"] = lock

if not lock["present"]:
    status["queue_state"] = "unlocked"
    status["next_visible_step"] = "mache v15.2.0"
elif lock["present"] and not lock["valid"]:
    status["queue_state"] = "locked-invalid"
    status["next_visible_step"] = "fix or clear RELEASE_LOCK.md before any cut discussion"
elif lock["wait_elapsed"]:
    status["queue_state"] = "locked-ready-for-gate"
    status["next_visible_step"] = "rerun strict release gate and decide on workflow dispatch"
else:
    status["queue_state"] = "locked-waiting"
    status["next_visible_step"] = "continue waiting until the 5-minute post-announcement window elapses"

Path(doc_out).write_text(json.dumps(status, indent=2) + "\n", encoding='utf-8')
Path(workspace_out).write_text(json.dumps(status, indent=2) + "\n", encoding='utf-8')
PY

if git -C "$ROOT" ls-files --error-unmatch "$DOC_OUT_REL" >/dev/null 2>&1; then
  git -C "$ROOT" checkout -- "$DOC_OUT_REL"
fi

printf '%s\n' "$DOC_OUT"
printf '%s\n' "$WORKSPACE_OUT"
