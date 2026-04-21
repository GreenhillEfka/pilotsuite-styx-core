# PS CORE SLICE 300 — CORE-HABITUS-202-C Zone Presence State Contract

## Scope
Land one bounded proof slice on `POST /api/v1/presence/zone/presence/<zone_id>/state` only.

## Files
- `tests/test_presence_zone_state_api_contract.py`

## Landed contract
- unauthenticated POST returns `401` with the existing auth-required payload
- authenticated POST normalizes bare zone ids to `zone:<id>`
- authenticated POST stores `occupied`, `primary_source`, `confidence`, `hold_state`, and `updated_at`
- authenticated POST keeps already-prefixed zone ids unchanged and defaults optional fields to `occupied=false`, `primary_source=null`, `confidence=0.0`, `hold_state=auto`

## Verification
- `python3 -m py_compile tests/test_presence_zone_state_api_contract.py`
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_presence_zone_state_api_contract.py`
- Result: `3 passed in 0.05s`

## Next exact pull
Stay on the same seam and take `CORE-HABITUS-202-D` only on `POST /api/v1/presence/zone/presence/<zone_id>/hold`, locking auth, valid hold states, bare-zone normalization, and the stored hold response without widening into automation.
