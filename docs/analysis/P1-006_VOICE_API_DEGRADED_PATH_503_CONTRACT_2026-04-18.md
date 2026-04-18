# P1-006 Voice API degraded-path 503 contract

Date: 2026-04-18 07:41 Europe/Berlin  
Owner: PilotClaw

## Scope
Bounded hardening of the shipped add-on voice compatibility surface so missing Whisper/Piper backends degrade cleanly instead of pretending success or collapsing into generic 500 responses.

## Files touched
- `addons/pilotsuite/app/copilot_core/api/v1/voice.py`
- `addons/pilotsuite/app/copilot_core/voice/stt_whisper.py`
- `addons/pilotsuite/app/copilot_core/voice/tts_piper.py`
- `tests/test_voice_api_transcribe_synthesize_contract.py`
- `tests/test_voice_degraded_path_contract.py`
- `tests/test_voice_whisper_piper_contract.py`

## Problem removed
Two runtime ambiguities existed on the shipped compatibility routes:
1. bootstrap failures in `_get_stt_engine()` / `_get_tts_engine()` still fell through to generic 500 behavior,
2. Piper compatibility could still fabricate a success path even when no backend was actually available.

That meant clients could not reliably distinguish "backend missing" from "code bug".

## Contract now
### `POST /api/v1/voice/transcribe`
If Whisper is unavailable:
- returns `503`
- payload includes:
  - `status: error`
  - `message: Voice transcription unavailable`
  - `error: service_unavailable`
  - `code: backend_missing`
  - `backend: whisper`
  - `available_backends: [] | [...]`
  - `retry_after_seconds: null`

### `POST /api/v1/voice/synthesize`
If Piper is unavailable:
- returns `503`
- payload includes the same degraded-path shape with `backend: piper`

### `POST /api/v1/voice/speak`
Uses the same degraded-path contract as `/synthesize`.

## Implementation notes
- `WhisperSTT` and `PiperTTS` now expose small availability helpers for API/runtime truth.
- `PiperTTS.synthesize()` now honestly returns `None` when the backend cannot be loaded instead of creating placeholder success artifacts.
- `/api/v1/voice/status` now reports backend availability from the engine status surface instead of assuming availability from construction alone.
- true engine crashes during a request still surface as `500`, which keeps code bugs distinguishable from expected degraded mode.

## Verification
```bash
cd /config/clawd/team/worktrees/pilotsuite-styx-core-current
/config/clawd/.venv_smoke_gate/bin/python -m py_compile addons/pilotsuite/app/copilot_core/api/v1/voice.py addons/pilotsuite/app/copilot_core/voice/stt_whisper.py addons/pilotsuite/app/copilot_core/voice/tts_piper.py tests/test_voice_api_transcribe_synthesize_contract.py tests/test_voice_degraded_path_contract.py tests/test_voice_whisper_piper_contract.py
/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_voice_api_transcribe_synthesize_contract.py tests/test_voice_degraded_path_contract.py tests/test_voice_whisper_piper_contract.py tests/test_voice_api_endpoint_contracts.py
```

## Next single step
`CORE-RESCUE-004-C` — expose the same truthful voice capability gate to the HA consumer path so HA can branch on backend availability without probing route failures first.
