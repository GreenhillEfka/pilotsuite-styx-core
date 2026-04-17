# PS Core — Slice 401: status query context rendering contract

**Date:** 2026-04-17  
**Branch:** `pilotclaw/core-restore-runtime`  
**Status:** ✅ DONE

## Was

Hardened the status-query response path used by both:
- `POST /api/v1/voice/intent`
- `POST /api/v1/voice/ha/assist`

## Why

After Slice 398 and Slice 400, replayed `active_devices` correctly entered `VoiceContext` as `DeviceContext` objects. But `_handle_status_query(...)` in `voice_handler.py` still tried to do:

```python
', '.join(context.active_devices[:3])
```

That crashes with:

```text
TypeError: sequence item 0: expected str instance, DeviceContext found
```

The same code path also rendered the zone as the raw `ZoneContext(...)` repr instead of the canonical zone name.

## Change

Updated `addons/pilotsuite/app/copilot_core/voice/voice_handler.py` so status queries now:
- render `context.zone_name` instead of the raw `ZoneContext(...)` repr
- extract human-readable device names from replayed `DeviceContext` / dict items before joining them into TTS output
- skip the device phrase if no readable names are present

## Verification

- `python3 -m py_compile addons/pilotsuite/app/copilot_core/voice/voice_handler.py tests/test_voice_status_query_slice401_context_rendering_contract.py`
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_voice_status_query_slice401_context_rendering_contract.py tests/test_voice_ha_assist_bridge_contract.py tests/test_voice_intent_slice398_active_devices_replay_contract.py tests/test_voice_intent_slice400_nested_zone_replay_contract.py` → `14 passed in 0.26s`

## Files touched

- `addons/pilotsuite/app/copilot_core/voice/voice_handler.py`
- `tests/test_voice_status_query_slice401_context_rendering_contract.py`

## Blocker removed

Status queries with replayed `active_devices` no longer 500 on `/intent` or `/ha/assist`, and the spoken zone text no longer leaks the internal `ZoneContext(...)` repr.

## Next single step

Audit whether the `VoiceContextBuilder` cache incorrectly reuses stale context across repeated requests for the same zone, which would silently drop newer replayed `user_preferences` or `active_devices` in real multi-request sessions.
