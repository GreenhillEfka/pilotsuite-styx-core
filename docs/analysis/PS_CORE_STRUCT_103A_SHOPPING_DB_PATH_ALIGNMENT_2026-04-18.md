# PS CORE STRUCT 103A — shopping/reminders persistence path alignment

## Context
After `CORE-STRUCT-101` closed the `/api/v1/capabilities` parity chain, the next prepared structural hardening seam was `CORE-STRUCT-103 / State-Persistence hardening`.

The smallest live persistence drift in the shipped production app was still in `addons/pilotsuite/app/main.py`: `/api/v1/health/deep` checked `shopping_db` against the hardcoded path `/data/shopping_reminders.db`, while the actual shopping/reminders runtime uses `SHOPPING_DB_PATH` with the same default.

That meant deep-health could report a false negative whenever the shipped runtime used a non-default database path override.

## Change
- replaced the hardcoded deep-health shopping DB path with `os.environ.get("SHOPPING_DB_PATH", "/data/shopping_reminders.db")`
- added focused contract coverage proving the production app's deep-health surface now follows the runtime shopping DB path override instead of the stale hardcoded default

## Result
`/api/v1/health/deep` now reflects the same shopping/reminders persistence path the runtime actually uses. The persistence surface no longer drifts when operators relocate the shopping/reminders SQLite file via `SHOPPING_DB_PATH`.

## Verification
```bash
python3 -m py_compile \
  addons/pilotsuite/app/main.py \
  tests/test_state_persistence_shopping_health_contract.py

/config/clawd/.venv_smoke_gate/bin/python -m pytest -q \
  tests/test_state_persistence_shopping_health_contract.py

/config/clawd/.venv_smoke_gate/bin/python -m pytest -q \
  tests/test_state_persistence_shopping_health_contract.py \
  tests/test_voice_discovery_surface_contract.py
```

## Next single step
Continue `CORE-STRUCT-103` with the next bounded persistence truth edge, likely deciding whether the same shopping/reminders persistence truth should also be surfaced on `/api/v1/status` or whether deep-health-only visibility is the correct final boundary.
