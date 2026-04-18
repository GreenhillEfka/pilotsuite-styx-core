# PS CORE STRUCT 103F — readiness persistence visibility

## Context
After `CORE-STRUCT-103E`, the lightweight add-on compatibility app exposed runtime persistence truth on `/api/v1/status`.

One readiness-surface omission still remained in `addons/pilotsuite/app/copilot_core/api/v1/metrics.py`.

`GET /api/v1/ready` still returned only readiness state plus voice details, so restore/debug callers could not see which runtime file-backed persistence seams were currently reachable without pivoting back to status or deeper diagnostics.

## Decision
Keep readiness semantics unchanged for now and add persistence visibility only.

## Changes
- added a small runtime persistence summary helper in `addons/pilotsuite/app/copilot_core/api/v1/metrics.py`
- extended `/api/v1/ready` to include additive persistence fields for:
  - `conversation_memory_db_*`
  - `vector_store_db_*`
  - `shopping_db_*`
- kept the existing readiness behavior and auth expectations intact
- added focused contract coverage proving lightweight `/api/v1/ready` now follows `SHOPPING_DB_PATH`, `CONVERSATION_MEMORY_DB`, and `COPILOT_VECTOR_DB_PATH`

## Result
The lightweight readiness surface now publishes the same runtime-configurable file-backed persistence truth operators need during restore/debug work, without silently hiding those seams behind a separate status or deep-health call.

## Verification
- `python3 -m py_compile addons/pilotsuite/app/copilot_core/app.py addons/pilotsuite/app/copilot_core/api/v1/metrics.py tests/test_state_persistence_shopping_health_contract.py`
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_state_persistence_shopping_health_contract.py` → `5 passed in 3.99s`

## Next step
Stay on `CORE-STRUCT-103` and inspect the remaining repo-root compatibility surfaces, especially whether the FastAPI compatibility server still omits runtime file-backed persistence truth on its health or status paths.
