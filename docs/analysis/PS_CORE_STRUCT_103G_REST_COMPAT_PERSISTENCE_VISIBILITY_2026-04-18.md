# PS CORE STRUCT 103G — repo-root compatibility persistence visibility

## Context
After `CORE-STRUCT-103F`, the shipped Flask surfaces and the lightweight add-on compatibility surfaces all exposed runtime file-backed persistence truth for shopping/reminders, conversation memory, and vector storage.

One smaller compatibility gap still remained in the repo-root FastAPI server at `copilot_core/api/rest_server.py`.

Its `/health` and `/api/v1/status` responses still returned static operational metadata only, so restore/debug callers hitting the repo-root compatibility server could not see which runtime persistence seams were actually reachable.

## Decision
Land one bounded additive parity fix in the repo-root compatibility server instead of widening readiness or auth semantics.

## Changes
- added `_get_runtime_persistence_summary()` in `copilot_core/api/rest_server.py`
- extended repo-root `/health` to include additive persistence truth for:
  - `conversation_memory_db_*`
  - `vector_store_db_*`
  - `shopping_db_*`
- extended repo-root `/api/v1/status` with the same additive persistence block
- updated the FastAPI response models so the persistence block is part of the documented compatibility contract
- added focused contract coverage in `copilot_core/api/tests/test_rest_server.py`

## Result
The repo-root FastAPI compatibility surfaces no longer hide runtime file-backed persistence state behind the Flask-only paths. Operators and compatibility callers now get the same bounded persistence visibility across all shipped status and health surfaces used during restore/debug work.

## Verification
- `python3 -m py_compile copilot_core/api/rest_server.py copilot_core/api/tests/test_rest_server.py`
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q copilot_core/api/tests/test_rest_server.py`

## Next step
Close out `CORE-STRUCT-103` by refreshing the shared queue/ledger truth and transition the Core lane to `CORE-STRUCT-102 / Voice-Memory hardening`, unless the verification ring finds one real remaining persistence regression.
