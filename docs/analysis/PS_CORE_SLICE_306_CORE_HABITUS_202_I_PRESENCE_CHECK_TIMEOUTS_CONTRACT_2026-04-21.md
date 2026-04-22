# PS CORE SLICE 306 — CORE-HABITUS-202-I Presence Check Timeouts Contract (2026-04-21)

## Scope
One bounded Core proof slice only on `POST /api/v1/presence/check_timeouts`, staying on the existing `addons/pilotsuite/app/copilot_core/api/v1/presence.py` seam and stopping before any wider follow-on.

## Landed
- added dedicated contract ring `tests/test_presence_check_timeouts_api_contract.py`
- locked the front-door `401` auth gate on `POST /api/v1/presence/check_timeouts`
- locked the canonical no-op `200` payload `{ok, timed_out, state_changed}` when no source has expired
- locked one timeout-driven recompute path where an expired `home` source is flipped to `not_home`, the person recomputes to `not_home`, `timed_out` returns the person id, and the history ring records the timeout-driven `departed` event

## Verification
- `python3 -m py_compile tests/test_presence_check_timeouts_api_contract.py`
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_presence_check_timeouts_api_contract.py`
- result: `3 passed in 0.05s`

## Result
`CORE-HABITUS-202-I` is now file-backed on fresh repo truth without widening into `/update`, automation, config, graph-service, or `/styx` work.

## Next exact pull
Checkpoint the presence chain as clean through `CORE-HABITUS-202-I`, then take one bounded fresh-truth naming slice only for the first post-`CORE-HABITUS-202` Core pull before any wider follow-on.
