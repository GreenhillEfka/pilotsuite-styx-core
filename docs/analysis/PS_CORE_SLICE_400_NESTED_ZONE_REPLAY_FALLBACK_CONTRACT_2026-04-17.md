# PS Core — Slice 400: nested zone replay fallback contract

**Date:** 2026-04-17  
**Branch:** `pilotclaw/core-restore-runtime`  
**Status:** ✅ DONE

## Was

Aligned `POST /api/v1/voice/intent` and `POST /api/v1/voice/ha/assist` so both routes resolve the requested zone from the same replay authority chain:
1. explicit top-level `zone`
2. replayed `context.zone_name`
3. replayed nested `context.zone.zone_name`

## Why

Before this slice, nested replay payloads like:

```json
{
  "text": "Status",
  "context": {
    "zone": {"zone_name": "Schlafzimmer"}
  }
}
```

silently fell back to the default `wohnzimmer`, even though the caller had already provided valid zone authority inside the public replay shape.

That created drift between caller-visible replay data and the rebuilt runtime context, especially on the new HA Assist bridge.

## Change

Added `_resolve_requested_zone(...)` in `addons/pilotsuite/app/copilot_core/api/v1/voice.py` and reused it in both routes.

Behavior now is:
- nested replayed `context.zone.zone_name` is honored when no top-level `zone` or `context.zone_name` exists
- canonical lowercase zone names are still returned
- explicit `context.zone_name` still wins over nested `context.zone.zone_name`

## Verification

- `python3 -m py_compile addons/pilotsuite/app/copilot_core/api/v1/voice.py tests/test_voice_ha_assist_bridge_contract.py tests/test_voice_intent_slice400_nested_zone_replay_contract.py`
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_voice_ha_assist_bridge_contract.py tests/test_voice_intent_slice400_nested_zone_replay_contract.py` → `9 passed in 0.20s`
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_voice_intent_slice396_contract.py tests/test_voice_intent_slice398_active_devices_replay_contract.py tests/test_voice_ha_assist_bridge_contract.py tests/test_voice_intent_slice400_nested_zone_replay_contract.py` → `14 passed in 0.22s`

## Files touched

- `addons/pilotsuite/app/copilot_core/api/v1/voice.py`
- `tests/test_voice_ha_assist_bridge_contract.py`
- `tests/test_voice_intent_slice400_nested_zone_replay_contract.py`

## Blocker removed

Nested replayed zone authority no longer collapses to the default room on `/intent` or `/ha/assist` when the caller only provides `context.zone.zone_name`.

## Next single step

Keep the HA Assist bridge on parity with the main voice route by hardening the next adjacent public replay seam, starting with whether replayed `context.user_preferences` should also drive `language_preference` consistently when callers send `preferred_language` rather than `language`.
