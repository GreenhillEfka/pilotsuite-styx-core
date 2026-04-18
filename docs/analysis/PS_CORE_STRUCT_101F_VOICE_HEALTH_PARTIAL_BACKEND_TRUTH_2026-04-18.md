# PS Core — CORE-STRUCT-101F Voice Health Partial Backend Truth

**Date:** 2026-04-18 14:50 Europe/Berlin
**Lane:** PilotClaw / Core
**Status:** ✅ DONE

## Why this slice exists

After `CORE-STRUCT-101E` stabilized the fallback schema, one runtime-truth defect still remained in the shared helper: `get_voice_health_block()` imported Whisper and Piper in one coupled step.

That meant a missing Whisper import could incorrectly collapse Piper/TTS truth to `false`, and a missing Piper import could incorrectly collapse Whisper/STT truth to `false`, even though `/api/v1/voice/status` probes those backends independently.

## Artifacts changed

- `addons/pilotsuite/app/copilot_core/voice/voice_health.py`
  - now probes `WhisperSTT` and `PiperTTS` independently via small backend-loader helpers
  - preserves partial backend truth instead of collapsing to the all-false block when only one import path fails
- `tests/test_voice_health_block_contract.py`
  - added proof that TTS truth survives a Whisper import failure
  - added proof that STT truth survives a Piper import failure

## Blocker removed

Shared health/readiness/capability consumers now report honest partial voice availability. A single missing backend import no longer hides the other healthy backend behind the all-false fallback block.

## Verification

```bash
python3 -m py_compile \
  addons/pilotsuite/app/copilot_core/voice/voice_health.py \
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

Result: `72 passed, 1 skipped`

## Next exact step

`CORE-STRUCT-101G / health-surface contract proof` — add focused endpoint-level coverage for `/health`, `/ready`, and `/api/v1/status` so the shared helper’s partial-backend truth is locked at the HTTP surface, not only at the helper level.
