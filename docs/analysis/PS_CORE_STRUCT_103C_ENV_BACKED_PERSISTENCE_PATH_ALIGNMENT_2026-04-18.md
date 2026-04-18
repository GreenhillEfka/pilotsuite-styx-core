# PS CORE STRUCT 103C — env-backed persistence path alignment in deep health

## Context
After `CORE-STRUCT-103A` fixed the shopping/reminders persistence drift and `CORE-STRUCT-103B` exposed the shopping persistence seam on `/api/v1/status`, one real drift still remained inside `/api/v1/health/deep`.

The deep-health route still checked `conversation_memory_db` and `vector_store_db` against hardcoded default paths only:
- `/data/conversation_memory.db`
- `/data/vector_store.db`

That no longer matched the shipped runtime seams, because those storage layers already allow relocation through:
- `CONVERSATION_MEMORY_DB`
- `COPILOT_VECTOR_DB_PATH`

## Change
- added one shared runtime persistence map in `addons/pilotsuite/app/main.py` for:
  - `conversation_memory_db`
  - `vector_store_db`
  - `shopping_db`
- rewired `/api/v1/health/deep` to read the current accessibility booleans from that env-backed map instead of hardcoded default paths
- kept `/api/v1/status` additive-only and limited to the compact shopping/reminders summary introduced in `103B`
- added focused contract coverage proving deep-health now follows custom `CONVERSATION_MEMORY_DB` and `COPILOT_VECTOR_DB_PATH` values

## Result
`/api/v1/health/deep` now reports persistence truth against the same runtime-configurable storage locations the shipped services actually use, across shopping/reminders, conversation memory, and vector storage.

## Verification
```bash
python3 -m py_compile \
  addons/pilotsuite/app/main.py \
  tests/test_state_persistence_shopping_health_contract.py

/config/clawd/.venv_smoke_gate/bin/python -m pytest -q \
  tests/test_state_persistence_shopping_health_contract.py
```

## Next single step
Stay on `CORE-STRUCT-103` and audit the next bounded persistence truth edge, likely whether any remaining health or status surfaces still omit or misstate file-backed runtime state that operators actually depend on during restore/debug flows.
