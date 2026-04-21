# PS CORE Slice 301 — CORE-HABITUS-202-D Zone Presence Hold Contract

Date: 2026-04-21
Owner: PilotClaw
Status: landed

## Scope
Take one bounded Core slice on the existing presence ingress seam only:
- production seam: `addons/pilotsuite/app/copilot_core/api/v1/presence.py`
- proof ring: `tests/test_presence_zone_hold_api_contract.py`

Stay on `POST /api/v1/presence/zone/presence/<zone_id>/hold` only, without widening into automation, graph, config, or HA-owned surface work.

## What landed
- kept the existing auth-gated zone hold route and locked it with a dedicated contract ring
- normalized bare zone ids to canonical `zone:<id>` before storing and returning the hold payload
- stored zone hold state on the existing module-level `_ZONE_HOLD_MAP` truth path used by `get_zone_hold_state()`
- kept valid hold states bounded to `auto`, `force_on`, and `force_off`
- cleared `_ZONE_HOLD_MAP` inside `clear_presence_data()` so test/reset behavior stays honest on the same seam

## Proof ring
`tests/test_presence_zone_hold_api_contract.py` now locks:
1. unauthenticated POST returns the existing `401` auth-required payload
2. authenticated POST accepts valid hold states, normalizes bare ids, preserves prefixed ids, and returns `{ok, zone_id, hold}`
3. invalid hold states return `400` and do not mutate stored hold truth

## Verification
- `python3 -m py_compile addons/pilotsuite/app/copilot_core/api/v1/presence.py tests/test_presence_zone_hold_api_contract.py`
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_presence_zone_hold_api_contract.py`
  - result: `5 passed in 0.07s`

## Result
`CORE-HABITUS-202-D` is now clean on fresh repo truth. The zone-presence hold route has a dedicated contract ring, canonical zone-id normalization, bounded valid-state acceptance, and stored-response proof.

## Next exact pull
Stay on the same presence/habitus lane but stop widening here. The next exact pull should be a fresh queue-truth naming step for the next post-`CORE-HABITUS-202-D` Core slice, rather than pushing into end-to-end automation by assumption.
