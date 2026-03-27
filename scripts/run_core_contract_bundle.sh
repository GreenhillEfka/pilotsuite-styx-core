#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEAM_ROOT="$(cd "$ROOT/../.." && pwd)"
CORE_APP_ROOT="$ROOT/copilot_core/rootfs/usr/src/app"

pick_pytest() {
  local candidate python_bin
  local candidates=(
    "${WORKSPACE_TEST_PYTEST:-}"
    "$ROOT/.venv/bin/pytest"
    "$(command -v pytest 2>/dev/null || true)"
    "$TEAM_ROOT/worktrees/pilotsuite-styx-ha-current/.venv/bin/pytest"
    "$TEAM_ROOT/worktrees/pilotsuite-styx-core-release-prep-v14.7.3/.venv/bin/pytest"
  )

  # Prefer an environment that has the full contract test stack available
  for candidate in "${candidates[@]}"; do
    [ -n "$candidate" ] || continue
    [ -x "$candidate" ] || continue
    python_bin="$(head -n 1 "$candidate" | sed 's/^#!//')"
    [ -n "$python_bin" ] || continue
    [ -x "$python_bin" ] || continue
    if "$python_bin" -c "import pytest, flask, pytest_asyncio" >/dev/null 2>&1; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done

  # Fallback: at least the Flask-backed contract suites must run
  for candidate in "${candidates[@]}"; do
    [ -n "$candidate" ] || continue
    [ -x "$candidate" ] || continue
    python_bin="$(head -n 1 "$candidate" | sed 's/^#!//')"
    [ -n "$python_bin" ] || continue
    [ -x "$python_bin" ] || continue
    if "$python_bin" -c "import pytest, flask" >/dev/null 2>&1; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done

  return 1
}

PYTEST_BIN="$(pick_pytest || true)"
if [ -z "$PYTEST_BIN" ]; then
  echo "core contract bundle requires a pytest executable backed by a python with pytest + flask available" >&2
  echo "preferred: pytest + flask + pytest_asyncio" >&2
  echo "checked: WORKSPACE_TEST_PYTEST, core .venv, system pytest, HA current worktree .venv, core release-prep .venv" >&2
  exit 2
fi

export PYTHONPATH="$CORE_APP_ROOT:${PYTHONPATH:-}"

cd "$ROOT"

# Ensure workspace contract fixtures run against a clean tmp store
rm -f \
  "$ROOT/tmp/workspace-contract-events.jsonl" \
  "$ROOT/tmp/workspace-contract-events-call.jsonl" \
  "$ROOT/tmp/workspace-endpoint-events.jsonl" \
  "$ROOT/tmp/workspace-endpoint-call-service.jsonl"

"$PYTEST_BIN" \
  tests/test_dashboard_read_models_contract.py \
  tests/test_zone_dashboard_contract.py \
  tests/test_brain_read_model_contract.py \
  tests/test_metrics_blueprint_contract.py \
  tests/test_taxonomy_contract.py \
  tests/test_zone_truth_sync_contract.py \
  tests/test_core_wiring_contract.py \
  tests/test_event_processor_import_contract.py \
  tests/integration/test_workspace_ha_core_contract.py \
  -q \
  "$@"

# Clean workspace contract tmp artifacts again after the run and drop empty tmp dir
rm -f \
  "$ROOT/tmp/workspace-contract-events.jsonl" \
  "$ROOT/tmp/workspace-contract-events-call.jsonl" \
  "$ROOT/tmp/workspace-endpoint-events.jsonl" \
  "$ROOT/tmp/workspace-endpoint-call-service.jsonl"
rmdir "$ROOT/tmp" 2>/dev/null || true
