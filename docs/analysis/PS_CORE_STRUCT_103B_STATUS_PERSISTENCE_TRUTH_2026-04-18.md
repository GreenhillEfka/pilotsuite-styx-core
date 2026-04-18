# PS CORE STRUCT 103B — status persistence truth for shopping/reminders

## Context
After `CORE-STRUCT-103A` aligned `/api/v1/health/deep` with the runtime `SHOPPING_DB_PATH` override, the remaining small observability gap was `/api/v1/status` in `addons/pilotsuite/app/main.py`.

That status surface still returned only `ok/time/version/port`, so operators and HA-side connectivity checks could not see whether the shopping/reminders persistence path currently resolved to a reachable database without dropping to the deeper diagnostics endpoint.

## Change
- added one shared helper in `addons/pilotsuite/app/main.py` that resolves the runtime shopping/reminders DB path and its current accessibility
- extended `/api/v1/status` with an additive `persistence` block containing:
  - `shopping_db_path`
  - `shopping_db_accessible`
- reused the same helper in `/api/v1/health/deep` so status and deep-health now read from the same runtime seam instead of duplicating shopping path lookup logic
- kept the change non-authoritative for readiness, additive-only for status, and limited to shopping/reminders persistence truth

## Result
`/api/v1/status` now exposes a compact shopping/reminders persistence summary that follows the same `SHOPPING_DB_PATH` override already used by the shipped runtime and by `/api/v1/health/deep`.

## Verification
```bash
python3 -m py_compile \
  addons/pilotsuite/app/main.py \
  tests/test_state_persistence_shopping_health_contract.py

/config/clawd/.venv_smoke_gate/bin/python -m pytest -q \
  tests/test_state_persistence_shopping_health_contract.py
```

## Next single step
Continue `CORE-STRUCT-103` with the next bounded persistence truth edge, likely auditing whether `/api/v1/health/deep` still hardcodes default persistence paths for `CONVERSATION_MEMORY_DB` or `COPILOT_VECTOR_DB_PATH` instead of following the runtime overrides already used by those storage layers.
