# PS CORE STRUCT 103E — lightweight status persistence parity

## Context
After `CORE-STRUCT-103D`, the shipped production Flask app exposed a compact truthful `persistence` block on `/api/v1/status` for shopping/reminders, conversation memory, and vector storage.

One smaller compatibility drift still remained in `addons/pilotsuite/app/copilot_core/app.py`.

The lightweight add-on app factory still served `/api/v1/status` with only `ok/time/version/port/voice`, which meant test and compatibility callers using that app factory could still miss the same runtime file-backed persistence truth already restored on the production status surface.

## Decision
Land the smallest additive parity fix on the lightweight compatibility status surface instead of changing readiness semantics.

## Changes
- added `_get_runtime_persistence_summary()` in `addons/pilotsuite/app/copilot_core/app.py`
- extended lightweight `/api/v1/status` to publish the same additive persistence fields:
  - `conversation_memory_db_path`
  - `conversation_memory_db_accessible`
  - `vector_store_db_path`
  - `vector_store_db_accessible`
  - `shopping_db_path`
  - `shopping_db_accessible`
- preserved the existing `voice` block and unauthenticated status behavior
- added focused contract coverage proving the lightweight app factory follows `SHOPPING_DB_PATH`, `CONVERSATION_MEMORY_DB`, and `COPILOT_VECTOR_DB_PATH`

## Result
The remaining lightweight compatibility status surface now reports the same runtime-configurable file-backed persistence truth operators and tests already get from the production status surface, instead of silently omitting it.

## Verification
- `python3 -m py_compile addons/pilotsuite/app/copilot_core/app.py tests/test_state_persistence_shopping_health_contract.py`
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_state_persistence_shopping_health_contract.py` → `4 passed in 4.04s`

## Next step
Stay on `CORE-STRUCT-103` and inspect the next bounded readiness/compatibility edge, likely whether any remaining `/ready` or repo-root compatibility surface still omits runtime file-backed persistence truth during restore/debug flows.
