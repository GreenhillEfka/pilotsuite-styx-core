# PS CORE STRUCT 102I — voice status runtime parity

## Context
After the shared voice health/discovery helper grew additive `intent_handler` runtime detail, the canonical `GET /api/v1/voice/status` surface still rebuilt its own runtime and capability payload instead of reusing that shared truth ring.

## Exact defect removed
`addons/pilotsuite/app/copilot_core/api/v1/voice.py` still serialized status runtime truth through a route-local builder that only projected `stt`, `tts`, and `nlu`.

That left one live parity gap on the dialog gate:
- `/api/v1/voice/status` omitted the additive `runtime.intent_handler` block already exposed on shared health/readiness/discovery surfaces
- status and shared helper logic could drift again on fallback runtime payloads and capability booleans because both surfaces rebuilt adjacent truth independently

## Bounded fix
- replaced the route-local runtime/capability builders in `addons/pilotsuite/app/copilot_core/api/v1/voice.py` with one thin `_get_voice_health_block()` wrapper plus `_extract_voice_capabilities(...)`
- made `GET /api/v1/voice/status` reuse the shared health/discovery truth ring for `runtime` and `capabilities` while preserving its additive `components` and `config` blocks
- widened `tests/test_voice_api_transcribe_synthesize_contract.py` so the status route now locks the shared runtime shape, including `runtime.intent_handler.default_language`, on both the direct and injected-runtime paths

## Result
`GET /api/v1/voice/status`, health/readiness payloads, and discovery now project the same bounded runtime/capability truth ring for the dialog gate instead of drifting on separate serializers. Callers can see `intent_handler` runtime detail everywhere the public/shared voice status surface already exposes STT/TTS/NLU truth.

## Verification
```bash
cd /config/clawd/team/worktrees/pilotsuite-styx-core-current
python3 -m py_compile addons/pilotsuite/app/copilot_core/api/v1/voice.py tests/test_voice_api_transcribe_synthesize_contract.py
/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_voice_api_transcribe_synthesize_contract.py tests/test_voice_health_block_contract.py tests/test_voice_health_surface_contract.py tests/test_voice_discovery_surface_contract.py
# 19 passed in 2.93s
```

## Next single step
Inspect whether one remaining bounded component-visibility parity slice still exists for shared voice ops surfaces beyond the dialog gate, or move to the next visible degraded-path packet on the hardened voice/runtime seam.
