# PS Core — Slice 402: language preference replay parity

**Date:** 2026-04-17  
**Branch:** `pilotclaw/core-restore-runtime`  
**Status:** ✅ DONE

## Was

Aligned replayed language preference handling for both:
- `POST /api/v1/voice/intent`
- `POST /api/v1/voice/ha/assist`

## Why

The public voice routes already accepted replayed `context.user_preferences`, but `VoiceContextBuilder` only derived `language_preference` from `user_preferences.language`.

That meant callers who sent the already-used replay shape:

```json
{
  "context": {
    "user_preferences": {
      "preferred_language": "EN"
    }
  }
}
```

still got `context.language_preference = "de"` in the rebuilt context, even though the accepted replay data clearly carried a language preference.

## Change

Added `_resolve_language_preference(...)` in `addons/pilotsuite/app/copilot_core/voice/context_builder.py`.

Resolution order is now:
1. `user_preferences.language`
2. `user_preferences.preferred_language`
3. default `de`

Returned `language_preference` is normalized to lowercase, while the original replayed `user_preferences` payload remains unchanged.

## Verification

- `python3 -m py_compile addons/pilotsuite/app/copilot_core/voice/context_builder.py tests/test_voice_language_preference_slice402_contract.py`
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_voice_language_preference_slice402_contract.py tests/test_voice_status_query_slice401_context_rendering_contract.py tests/test_voice_ha_assist_bridge_contract.py tests/test_voice_intent_slice400_nested_zone_replay_contract.py` → `14 passed in 0.22s`

## Files touched

- `addons/pilotsuite/app/copilot_core/voice/context_builder.py`
- `tests/test_voice_language_preference_slice402_contract.py`

## Blocker removed

Replayed voice context no longer silently reports `language_preference = de` when callers send only `user_preferences.preferred_language`.

## Next single step

Check whether the rebuilt `context.language_preference` is actually respected by the voice response path, or whether `VoiceIntentHandler` still speaks using only parsed intent language and ignores the replayed preference.
