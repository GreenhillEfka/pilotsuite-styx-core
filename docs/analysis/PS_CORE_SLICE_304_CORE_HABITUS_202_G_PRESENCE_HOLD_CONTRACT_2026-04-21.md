# PS CORE SLICE 304 — CORE-HABITUS-202-G Presence Hold Contract

Date: 2026-04-21
Owner: PilotClaw
Status: done

## Scope
Land one bounded Core slice only on `POST /api/v1/presence/hold` with a dedicated proof ring, and stop before widening into `DELETE /hold`, `/update`, timeout handling, automation, graph, or HA-owned config work.

## Files
- `addons/pilotsuite/app/copilot_core/api/v1/presence.py`
- `tests/test_presence_hold_api_contract.py`

## What landed
- Added the dedicated contract ring `tests/test_presence_hold_api_contract.py` for the already-shipped person-hold route.
- Locked the front-door auth gate: unauthenticated `POST /api/v1/presence/hold` returns `401` with the existing auth-required payload.
- Locked the bounded validation path: authenticated requests without `person_id` return `400` with the canonical missing-field payload.
- Locked the canonical create path: a new held person returns `{ok, hold_set, person_id, reason, hold_until}` and stores the same normalized hold truth in `_presence_map`.
- Locked the canonical update path: an existing person updates to the normalized hold state, preserves stored source data, and records the expected hold-driven history event.

## Verification
- `python3 -m py_compile tests/test_presence_hold_api_contract.py` ✅
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_presence_hold_api_contract.py` → `4 passed in 0.06s` ✅

## Result
- `CORE-HABITUS-202-G` is now file-backed on fresh repo truth without widening the seam.
- The next exact pull should stay on the same bounded presence lane and target `DELETE /api/v1/presence/hold` only, with one dedicated `tests/test_presence_hold_clear_api_contract.py` proof ring for the `401` auth gate, `400` on missing `person_id`, `404` on unknown person, and canonical `{ok, hold_cleared, current_state}` response after recompute.
- Routine bounded surfacing belongs in `topic:13196`.
