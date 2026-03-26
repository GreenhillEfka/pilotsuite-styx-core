#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEAM_ROOT="$(cd "$ROOT/../.." && pwd)"
CORE_APP_ROOT="$ROOT/copilot_core/rootfs/usr/src/app"

pick_python() {
  local candidate
  for candidate in \
    "${WORKSPACE_TEST_PYTHON:-}" \
    "$ROOT/.venv/bin/python" \
    "$TEAM_ROOT/worktrees/pilotsuite-styx-ha-current/.venv/bin/python" \
    "$TEAM_ROOT/worktrees/pilotsuite-styx-core-release-prep-v14.7.3/.venv/bin/python" \
    "$(command -v python3 2>/dev/null || true)"
  do
    [ -n "$candidate" ] || continue
    [ -x "$candidate" ] || continue
    if "$candidate" -c "import pytest" >/dev/null 2>&1; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

PYTHON_BIN="$(pick_python || true)"
if [ -z "$PYTHON_BIN" ]; then
  echo "workspace test runner requires a python with pytest available" >&2
  echo "checked: WORKSPACE_TEST_PYTHON, core .venv, HA current worktree .venv, core release-prep .venv, system python3" >&2
  exit 2
fi

export PYTHONPATH="$CORE_APP_ROOT:${PYTHONPATH:-}"

cd "$ROOT"

"$PYTHON_BIN" -m pytest \
  tests/integration/test_workspace_ha_core_contract.py \
  -q \
  "$@"
