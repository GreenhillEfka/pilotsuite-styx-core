# PS CORE STRUCT 102G — shared voice runtime detail visibility

## Context
After `CORE-STRUCT-102-F` restored additive `can_dialog` truth on the shared voice health/discovery helper, the next bounded parity sweep checked whether health/readiness/discovery consumers still hid the underlying runtime detail already exposed on `GET /api/v1/voice/status`.

## Exact defect removed
`addons/pilotsuite/app/copilot_core/voice/voice_health.py` still collapsed shared health/readiness/discovery truth down to capability booleans plus a thin `available_backends` list.

That meant callers could see `can_dialog=false` or a partially available backend state, but could not see the bounded STT/TTS/NLU runtime payload already exposed on `/api/v1/voice/status`. Shared ops and discovery surfaces stayed one step behind the canonical status seam exactly where degraded-path diagnosis needed more than booleans.

## Bounded fix
- extended `addons/pilotsuite/app/copilot_core/voice/voice_health.py` with additive nested `runtime` detail for `stt`, `tts`, and `nlu`
- when a Flask app context is available, the helper now projects those nested runtime payloads from the injected voice runtime seam instead of rebuilding a second truth source
- kept the existing boolean capability fields and `available_backends` contract intact, while making backend labels follow injected runtime engine identifiers when present
- aligned `addons/pilotsuite/app/copilot_core/api/voice_discovery.py` fallback metadata with the same additive nested runtime shape
- widened focused regression coverage in `tests/test_voice_health_block_contract.py`, `tests/test_voice_health_surface_contract.py`, and `tests/test_voice_discovery_surface_contract.py`

## Result
Shared health, readiness, and voice discovery payloads no longer force consumers back to `/api/v1/voice/status` just to diagnose bounded STT/TTS/NLU runtime state. They now preserve the same thin runtime detail ring while keeping the existing capability-first contract stable.

## Verification
```bash
cd /config/clawd/team/worktrees/pilotsuite-styx-core-current
python3 -m py_compile addons/pilotsuite/app/copilot_core/voice/voice_health.py addons/pilotsuite/app/copilot_core/api/voice_discovery.py tests/test_voice_health_block_contract.py tests/test_voice_health_surface_contract.py tests/test_voice_discovery_surface_contract.py
/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_voice_health_block_contract.py tests/test_voice_health_surface_contract.py tests/test_voice_discovery_surface_contract.py tests/test_voice_api_transcribe_synthesize_contract.py
# 19 passed in 2.79s
```

## Next single step
Inspect whether one remaining bounded shared/public voice parity slice still exists around component-detail visibility for the dialog gate, or move to the next visible degraded-path packet on the hardened voice/runtime seam.
