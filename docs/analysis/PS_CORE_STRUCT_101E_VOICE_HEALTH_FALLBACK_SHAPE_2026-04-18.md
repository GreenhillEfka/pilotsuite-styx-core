# PS Core — CORE-STRUCT-101E Voice Health Fallback Shape

**Date:** 2026-04-18 14:52 Europe/Berlin
**Lane:** PilotClaw / Core
**Status:** ✅ DONE

## Why this slice exists

`CORE-STRUCT-101B/C/D` aligned the shared voice-health helper across `/health`, `/ready`, `/api/v1/status`, `/api/v1/capabilities`, and the monitoring layer, but the fully-unavailable fallback path still dropped `can_speak` from the public runtime block.

That meant the same surface family exposed two slightly different schemas depending on import/runtime failure state.

## Artifacts changed

- `addons/pilotsuite/app/copilot_core/voice/voice_health.py`
  - `_empty_block()` now keeps the full capability shape, including `can_speak: false`
- `addons/pilotsuite/app/copilot_core/api/voice_discovery.py`
  - fallback runtime payload now preserves the same stable `can_transcribe` / `can_synthesize` / `can_speak` / `available_backends` shape
- `tests/test_voice_health_block_contract.py`
  - proves the shared helper fallback keeps `can_speak`
  - proves `voice_capabilities_module()` preserves `can_speak` when the helper import path fails

## Blocker removed

Health/readiness/capability consumers no longer have to branch on a missing `can_speak` key when voice backends are unavailable or the shared helper import fails. The degraded voice-health schema now stays stable across both happy and fallback paths.

## Verification

```bash
python3 -m py_compile \
  addons/pilotsuite/app/copilot_core/voice/voice_health.py \
  addons/pilotsuite/app/copilot_core/api/voice_discovery.py \
  tests/test_voice_health_block_contract.py

/config/clawd/.venv_smoke_gate/bin/python -m pytest -q \
  tests/test_voice_health_block_contract.py \
  tests/test_voice_command_api.py \
  tests/test_voice_api_transcribe_synthesize_contract.py \
  tests/test_voice_api_endpoint_contracts.py \
  tests/test_voice_degraded_path_contract.py \
  tests/test_voice_discovery_surface_contract.py \
  tests/test_voice_ha_assist_bridge_contract.py \
  tests/test_voice_language_preference_slice402_contract.py
```

Result: `70 passed, 1 skipped`

## Next exact step

`CORE-STRUCT-101F / runtime-health consumer parity audit` — scan the remaining runtime/health consumers for any other voice-block schema drift between direct helper users and richer `/api/v1/voice/status` capability projections, then close the next smallest honest mismatch.
