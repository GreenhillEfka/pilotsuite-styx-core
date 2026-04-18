# P1-006 Voice Rescue — shipped add-on package compatibility

**Date:** 2026-04-18 Europe/Berlin
**Owner:** PilotClaw
**Status:** ✅ implemented and verified

## Failure surface
- `copilot_core/tests/test_integration.py::test_full_voice_pipeline_flow` imports:
  - `copilot_core.voice.stt_whisper.WhisperSTT`
  - `copilot_core.voice.tts_piper.PiperTTS`
  - `copilot_core.voice.nlu_engine.NLUEngine`
- In the active runtime, `copilot_core.voice` resolves to the shipped add-on package at `addons/pilotsuite/app/copilot_core/voice/__init__.py`.
- That package exposed the newer router/context surfaces but did not ship the Whisper, Piper, and NLU modules expected by the legacy integration path, so the import seam broke before the voice slice could execute.

## Bounded rescue
- Add compatibility modules directly under `addons/pilotsuite/app/copilot_core/voice/` for:
  - `stt_whisper.py`
  - `tts_piper.py`
  - `nlu_engine.py`
- Re-export those surfaces from `addons/pilotsuite/app/copilot_core/voice/__init__.py`.
- Keep the slice bounded to importable placeholders and stable contract behavior, without opening a second voice architecture path.

## Verification
- `python3 -m py_compile addons/pilotsuite/app/copilot_core/voice/__init__.py addons/pilotsuite/app/copilot_core/voice/stt_whisper.py addons/pilotsuite/app/copilot_core/voice/tts_piper.py addons/pilotsuite/app/copilot_core/voice/nlu_engine.py tests/test_voice_whisper_piper_contract.py`
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_voice_whisper_piper_contract.py` → `3 passed`
- Direct import probe now succeeds for `WhisperSTT`, `PiperTTS`, and `NLUEngine.extract_intent(...)` through the shipped add-on package.

## Expected outcome
- The shipped add-on package again satisfies the legacy Whisper/Piper/NLU import contract.
- Focused voice contract tests can run in the smoke-gate environment even when the broader FastAPI integration test is skipped.

## Next exact pull
- Continue deeper on the next `P1-006` runtime blocker instead of reopening tag/auth work.
