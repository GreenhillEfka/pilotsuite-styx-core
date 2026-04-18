# PS CORE STRUCT 102F — voice discovery dialog capability truth

## Context
After `CORE-STRUCT-102-E` restored truthful Whisper/Piper availability probing on the shared voice health helper, the next bounded follow-on stayed on the same public voice truth ring and checked whether shared health/readiness/discovery consumers still omitted dialog capability truth already exposed on `GET /api/v1/voice/status`.

## Exact defect removed
`addons/pilotsuite/app/copilot_core/voice/voice_health.py` still returned only `can_transcribe`, `can_synthesize`, and `can_speak`.

That meant health/readiness payloads plus `voice_capabilities_module()` could report backend availability while still hiding whether the bounded public dialog path was actually usable. The hardened status seam already computed `can_dialog` from STT, TTS, NLU, and intent-handler availability, but the shared helper reused by ops/discovery surfaces stopped short of that last capability gate.

## Bounded fix
- extended `addons/pilotsuite/app/copilot_core/voice/voice_health.py` to project additive `can_dialog` truth
- when a Flask app context is available, the helper now prefers the injected runtime seam for STT, TTS, NLU, and intent-handler availability so health/readiness/discovery surfaces follow the same bounded runtime authority as `/api/v1/voice/status`
- kept the existing STT/TTS fallback probing for non-Flask callers and added lightweight fallback checks for `NLUEngine` and `VoiceIntentHandler` so standalone discovery metadata still keeps a stable capability shape
- extended `addons/pilotsuite/app/copilot_core/api/voice_discovery.py` fallback metadata with the same additive `can_dialog` field
- widened the focused regression ring in `tests/test_voice_health_block_contract.py`, `tests/test_voice_health_surface_contract.py`, and `tests/test_voice_discovery_surface_contract.py`

## Result
Shared health, readiness, and voice discovery metadata no longer stop at backend-only truth. They now surface whether the public dialog path is actually available, and the Flask-backed surfaces derive that signal from the same runtime seam already hardened for `/api/v1/voice/status`.

## Verification
```bash
cd /config/clawd/team/worktrees/pilotsuite-styx-core-current
python3 -m py_compile addons/pilotsuite/app/copilot_core/voice/voice_health.py addons/pilotsuite/app/copilot_core/api/voice_discovery.py tests/test_voice_health_block_contract.py tests/test_voice_health_surface_contract.py tests/test_voice_discovery_surface_contract.py
/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_voice_api_transcribe_synthesize_contract.py tests/test_voice_health_block_contract.py tests/test_voice_health_surface_contract.py tests/test_voice_discovery_surface_contract.py
# 18 passed in 2.84s
```

## Next single step
Inspect whether one remaining bounded public voice parity slice still exists around NLU/runtime detail visibility on health-readiness-discovery surfaces, or move to the next visible degraded-path packet on the hardened voice/runtime seam.
