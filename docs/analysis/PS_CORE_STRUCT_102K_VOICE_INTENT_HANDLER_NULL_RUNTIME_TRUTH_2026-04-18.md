# PS CORE STRUCT 102K — voice intent-handler null-runtime truth

## Context
After `CORE-STRUCT-102J` closed the remaining shared/public component-visibility parity slice, the next bounded follow-on stayed on the same hardened voice/runtime seam and checked whether the shared helper still stayed truthful when an injected runtime returned a missing collaborator in a degraded path.

## Exact defect removed
`addons/pilotsuite/app/copilot_core/voice/voice_health.py` treated `runtime.get_intent_handler()` as available whenever the call returned without raising, even when the runtime explicitly returned `None`.

That reopened one degraded-path truth gap:
- shared health/readiness/discovery/status payloads could report `runtime.intent_handler.available = true` even though the injected runtime had no live intent handler
- `/api/v1/voice/status` component truth already fell back to `intent_handler = unavailable`, so the shared helper and the public status payload could drift again on the same degraded runtime seam

## Bounded fix
- tightened `_resolve_runtime_intent_handler_payload(...)` so a null injected handler now returns the same default unavailable payload as the other runtime-backed component helpers
- widened `tests/test_voice_health_block_contract.py` with a focused regression proving the shared helper keeps STT/TTS/NLU truth while marking a null injected intent handler unavailable
- widened `tests/test_voice_api_transcribe_synthesize_contract.py` so `/api/v1/voice/status` now locks the same null-handler degraded truth on the real injected-runtime path

## Result
The shared voice truth ring no longer flips `runtime.intent_handler.available` to `true` just because the runtime seam returned `None`. Status, health/readiness, and discovery stay aligned on the same degraded intent-handler truth while preserving the already-available STT/TTS/NLU runtime detail.

## Verification
```bash
cd /config/clawd/team/worktrees/pilotsuite-styx-core-current
python3 -m py_compile addons/pilotsuite/app/copilot_core/voice/voice_health.py tests/test_voice_health_block_contract.py tests/test_voice_api_transcribe_synthesize_contract.py
/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_voice_health_block_contract.py tests/test_voice_health_surface_contract.py tests/test_voice_discovery_surface_contract.py tests/test_voice_api_transcribe_synthesize_contract.py
```

## Next single step
Inspect whether one remaining bounded degraded-path packet still exists on the hardened voice/runtime seam where a partially broken injected runtime can reopen shared/public truth drift, or else close `CORE-STRUCT-102` cleanly and roll into `P3-011`.
