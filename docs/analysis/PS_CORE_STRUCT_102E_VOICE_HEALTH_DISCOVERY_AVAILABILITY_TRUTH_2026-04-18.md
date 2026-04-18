# PS CORE STRUCT 102E — voice health/discovery availability truth

## Context
After `CORE-STRUCT-102-D` kept `GET /api/v1/voice/status` truthful when proactive hints are offline, the next bounded follow-on stayed on the same public voice truth ring and checked the shared health/discovery helper used by readiness, health, and capabilities metadata.

## Exact defect removed
`addons/pilotsuite/app/copilot_core/voice/voice_health.py` still probed backend availability through legacy `can_transcribe` / `can_synthesize` methods.

The shipped Whisper/Piper compatibility engines do not expose those legacy methods. They expose `availability_payload()`, `is_available()`, and `available_backends()` instead. That meant the shared voice health block could silently report `can_transcribe=false`, `can_synthesize=false`, and `can_speak=false` even when the current runtime surface itself was healthy.

Because `voice_capabilities_module()` and the health/readiness surfaces reuse that helper, discovery and ops surfaces could drift away from the real public voice runtime truth.

## Bounded fix
- added `_resolve_backend_availability()` in `addons/pilotsuite/app/copilot_core/voice/voice_health.py`
- changed the shared health helper to prefer the shipped current engine surfaces in this order:
  1. `availability_payload()["available"]`
  2. `is_available()`
  3. legacy `can_*()` compatibility probes
  4. `available_backends()` as a final bounded fallback
- kept the existing shared health block shape unchanged, so downstream health/discovery consumers still read the same payload contract
- extended `tests/test_voice_health_block_contract.py` with a focused regression proving the helper now stays truthful for current engine-style availability surfaces instead of only the old legacy probe shape

## Result
Voice health, readiness, and discovery metadata no longer over-couple themselves to a stale legacy backend API. They now follow the shipped Whisper/Piper availability surfaces and preserve truthful partial availability when only one backend is up.

## Verification
```bash
cd /config/clawd/team/worktrees/pilotsuite-styx-core-current
python3 -m py_compile addons/pilotsuite/app/copilot_core/voice/voice_health.py tests/test_voice_health_block_contract.py
/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_voice_health_block_contract.py tests/test_voice_discovery_surface_contract.py tests/test_voice_health_surface_contract.py
# 11 passed in 4.59s
```

## Next single step
Inspect whether the remaining public voice discovery payload should also surface the dialog/NLU capability truth from the hardened status seam, or whether one smaller parity slice still exists first on the shared health/readiness path.
