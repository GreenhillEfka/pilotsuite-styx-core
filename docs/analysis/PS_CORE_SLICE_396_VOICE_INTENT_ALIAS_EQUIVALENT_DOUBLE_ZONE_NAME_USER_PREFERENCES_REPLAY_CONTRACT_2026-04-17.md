# PS Core Slice 396 — Voice intent alias-equivalent double zone-name user_preferences replay contract

## What changed
`POST /api/v1/voice/intent` now has focused regression proof that alias-equivalent same-zone replay carrying both `context.zone_name` and `context.zone.zone_name` still preserves accepted `context.user_preferences` replay on the existing same-zone non-retarget path.

## Why
After Slice 395, the bounded gap check for remaining accepted replay fields after `context.language_preference` on the double zone-name seam showed that `context.user_preferences` was accepted by the route but not yet file-backed on the combined alias-equivalent double zone-name shape.

## Implementation
- kept `addons/pilotsuite/app/copilot_core/api/v1/voice.py` unchanged because the existing double-zone-name same-zone non-retarget path already preserves object fields via `_apply_request_context_overrides(...)` without authority conflict
- added focused regression coverage in `tests/test_voice_intent_contract.py` for both alias directions, `context.zone_name="Wohnzimmer"` with nested `context.zone.zone_name="wohnzimmer"` and the inverse canonical/alias pair, while replaying accepted public `context.user_preferences`
- proved both requests stay on the accepted single-authority path by asserting `build_context(zone_name=None)` is preserved, the canonical returned zone identity remains `wohnzimmer`, the returned `context.user_preferences` keys are preserved verbatim, and source-backed zone metadata stays stable

## Verification
- `python3 -m py_compile addons/pilotsuite/app/copilot_core/api/v1/voice.py tests/test_voice_intent_contract.py`
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_voice_intent_contract.py`
  - result: `143 passed in 1.27s`

## Outcome
- blocker removed: alias-equivalent double zone-name replay now has explicit file-backed proof that accepted `context.user_preferences` replay is preserved without widening into a retarget path
- next single step: bounded rescan of the `/api/v1/voice/intent` context surface at the next remaining accepted replay field on the same double-authority seam, starting with `context.active_devices`
