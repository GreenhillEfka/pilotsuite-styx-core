# P1-006 Voice Rescue — transcribe/synthesize API compatibility surface

**Date:** 2026-04-18 Europe/Berlin  
**Owner:** PilotClaw  
**Status:** ✅ implemented and verified

## Failure surface
- `copilot_core/api/rest_api.py` already advertises `POST /api/v1/voice/transcribe` and `POST /api/v1/voice/synthesize` as public voice routes.
- The active add-on voice blueprint only exposed intent/context/hints/speak/status surfaces, so the runtime truth lagged behind the published REST contract.
- After the earlier `P1-006` import rescue restored `WhisperSTT` and `PiperTTS`, the next concrete blocker was the missing route seam that kept callers from reaching those shipped compatibility engines.

## Bounded rescue
- Wire shared `_get_stt_engine()` and `_get_tts_engine()` usage into real `POST /api/v1/voice/transcribe` and `POST /api/v1/voice/synthesize` routes inside `addons/pilotsuite/app/copilot_core/api/v1/voice.py`.
- Return stable bounded payloads from the shipped compatibility wrappers instead of opening a second voice runtime path.
- Extend `GET /api/v1/voice/status` with one thin `runtime` section plus `stt_engine` / `tts_engine` component markers so callers can see whether the restored voice surfaces are actually available.

## Verification
- `python3 -m py_compile addons/pilotsuite/app/copilot_core/api/v1/voice.py tests/test_voice_api_transcribe_synthesize_contract.py`
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_voice_api_transcribe_synthesize_contract.py` → `3 passed`

## Expected outcome
- The published REST contract and the shipped add-on blueprint are aligned again for the bounded Whisper/Piper compatibility path.
- Voice callers can now hit real `transcribe` and `synthesize` endpoints instead of 404ing behind the restored import seam.
- Status consumers can distinguish the restored STT/TTS surface from the rest of the voice stack without scraping internal objects.

## Next exact pull
- Deepen `P1-006` on the next bounded runtime seam by adding one explicit degraded-path contract for unavailable STT/TTS backends, so callers get stable 503 behavior when Whisper or Piper is missing instead of generic route-level failure.
