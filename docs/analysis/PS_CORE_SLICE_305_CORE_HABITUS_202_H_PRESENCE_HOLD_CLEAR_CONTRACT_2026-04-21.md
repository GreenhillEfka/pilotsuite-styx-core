# PS_CORE_SLICE_305 — CORE-HABITUS-202-H — Presence hold-clear contract

Date: 2026-04-21
Owner: PilotClaw
Status: landed

## Scope
One bounded Core slice only on `DELETE /api/v1/presence/hold`, with a dedicated proof ring and no widening into `/update`, `/check_timeouts`, automation, graph, or HA-owned config work.

## Files
- `addons/pilotsuite/app/copilot_core/api/v1/presence.py`
- `tests/test_presence_hold_clear_api_contract.py`

## Landing
Added the dedicated contract proof ring for the already-shipped hold-clear seam:
- front-door `401` auth gate
- `400` on missing `person_id`
- `404` on unknown person
- canonical `{ok, hold_cleared, current_state}` payload after recompute from stored sources
- history event on recomputed state transition via `trigger_source="hold_cleared"`

No production-path widening was required for this slice.

## Verification
- `python3 -m py_compile tests/test_presence_hold_clear_api_contract.py`
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_presence_hold_clear_api_contract.py`
- Result: `4 passed in 0.06s`

## Next exact pull
Stay on the same bounded habitus/presence lane and take `CORE-HABITUS-202-I` only on `POST /api/v1/presence/check_timeouts`, with one dedicated `tests/test_presence_check_timeouts_api_contract.py` proof ring for the front-door `401` auth gate, canonical `{ok, timed_out, state_changed}` no-op payload, and one timeout-driven recompute path, then checkpoint again before any wider follow-on.
