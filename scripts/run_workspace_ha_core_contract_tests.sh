#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CORE_APP_ROOT="$ROOT/copilot_core/rootfs/usr/src/app"
HA_ROOT="$(cd "$ROOT/../pilotsuite-styx-ha" && pwd)"

export PYTHONPATH="$CORE_APP_ROOT:$HA_ROOT:${PYTHONPATH:-}"

cd "$ROOT"

if ! python3 -c "import pytest" >/dev/null 2>&1; then
  echo "workspace test runner requires pytest in the local python3 environment" >&2
  echo "smallest unblock step: provide python3+pytest in workspace (system package or prebuilt venv)" >&2
  exit 2
fi

python3 -m pytest \
  tests/integration/test_workspace_ha_core_contract.py \
  "$HA_ROOT/custom_components/copilot_ha/tests/test_habitat_adapter.py" \
  -q \
  "$@"
