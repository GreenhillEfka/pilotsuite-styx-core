# PS CORE STRUCT 102A — voice context cache replay isolation

## Context
After the `CORE-STRUCT-103` persistence closeout, the next active Core seam moved to `CORE-STRUCT-102 / Voice-Memory hardening`.

The first bounded audit target was the shared voice context builder, because it sits at the convergence point for runtime mood/habitus enrichment and request-replayed voice context.

## Exact defect removed
`VoiceContextBuilder.build_context()` cached contexts only by zone name.

That meant request-replayed data such as:
- `user_preferences`
- `active_devices`
- `sensor_data`

could be stored under the shared zone cache and then bleed into the next same-zone request for up to the builder TTL.

In practice, one voice request could replay `preferred_language=en` or a device list and the next request for the same zone could incorrectly inherit that stale per-request context.

## Decision
Keep the existing short-lived zone cache for runtime-built contexts, but do not reuse or store cache entries when the caller passes request-replayed context inputs.

This is the smallest bounded hardening step because it preserves the intended cache for ordinary runtime lookups while restoring per-request truth for voice-memory replay surfaces.

## Changes
- updated `addons/pilotsuite/app/copilot_core/voice/context_builder.py`
- request-replayed inputs now bypass the shared zone cache
- replayed contexts are no longer written back into the shared cache
- added focused contract coverage in `tests/test_voice_context_cache_replay_isolation_contract.py`
- verified existing language/device replay surfaces still hold on the shipped voice endpoints

## Result
The shared voice context builder no longer lets one same-zone request leak replayed language/device context into the next one. Voice-memory replay stays request-scoped, while runtime-built contexts keep the existing bounded cache.

## Verification
- `python3 -m py_compile addons/pilotsuite/app/copilot_core/voice/context_builder.py tests/test_voice_context_cache_replay_isolation_contract.py`
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_voice_context_cache_replay_isolation_contract.py tests/test_voice_language_preference_slice402_contract.py tests/test_voice_intent_slice398_active_devices_replay_contract.py tests/test_voice_ha_assist_bridge_contract.py`
- result: `20 passed`

## Next step
Continue `CORE-STRUCT-102` with the next bounded voice/memory seam, likely dialog-state persistence truth (`102-B`) unless a fresher voice-context regression appears first.
