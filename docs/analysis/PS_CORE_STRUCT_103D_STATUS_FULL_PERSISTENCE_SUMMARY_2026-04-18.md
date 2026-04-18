# PS CORE STRUCT 103D — status surface full persistence summary

## Context
After `CORE-STRUCT-103A/B/C`, the shipped production app had one smaller remaining persistence observability omission in `addons/pilotsuite/app/main.py`.

`/api/v1/health/deep` already reflected the runtime-configurable persistence paths for:
- `SHOPPING_DB_PATH`
- `CONVERSATION_MEMORY_DB`
- `COPILOT_VECTOR_DB_PATH`

But `/api/v1/status` still exposed only the shopping/reminders subset. That left restore/debug callers without the same compact status visibility for conversation memory and vector-store persistence truth.

## Change
- replaced the shopping-only status helper with `_get_status_persistence_summary()`
- extended `/api/v1/status` to publish additive persistence fields for all three shipped file-backed SQLite seams:
  - `shopping_db_path`
  - `shopping_db_accessible`
  - `conversation_memory_db_path`
  - `conversation_memory_db_accessible`
  - `vector_store_db_path`
  - `vector_store_db_accessible`
- kept the surface additive-only and non-readiness-authoritative

## Result
`/api/v1/status` now gives operators one compact truthful persistence summary for the same runtime-configurable storage locations already checked by `/api/v1/health/deep`, instead of exposing only shopping/reminders and omitting the other active SQLite seams.

## Verification
```bash
python3 -m py_compile \
  addons/pilotsuite/app/main.py \
  tests/test_state_persistence_shopping_health_contract.py

/config/clawd/.venv_smoke_gate/bin/python -m pytest -q \
  tests/test_state_persistence_shopping_health_contract.py
```

Observed: `3 passed in 6.02s`

## Next
Stay on `CORE-STRUCT-103` and inspect whether the next bounded persistence truth edge is outside the production status surface, likely in another remaining compatibility or readiness surface that still omits runtime file-backed state operators need during restore/debug flows.
