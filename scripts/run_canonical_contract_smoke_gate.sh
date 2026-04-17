#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python}"

contract_tests=(
  tests/test_runtime_health_contract.py
  tests/test_runtime_option_inventory_contract.py
  tests/test_voice_memory_contract.py
  tests/test_voice_dialog_state.py
  tests/test_voice_session_memory.py
  tests/test_voice_dialog_api_contract.py
  tests/test_core_setup_init_services_contract.py
  tests/test_module_health_authority_contract.py
  tests/test_module_router_authority_contract.py
  tests/test_module_control_authority_contract.py
  tests/test_styx_dashboard_module_authority_contract.py
)

"$PYTHON_BIN" -m compileall -q addons/pilotsuite/app
"$PYTHON_BIN" -m py_compile addons/pilotsuite/app/main.py
"$PYTHON_BIN" -m pytest -q "${contract_tests[@]}" "$@"
