# PS_CORE_P3_011J_CONTEXT_RUNTIME_SEAM_2026-04-18

## Task
Land the next bounded `P3-011 / Hexagonal Architecture Refactor` slice after `P3-011-I` by removing the remaining route-owned context dependency sourcing from the voice context build path.

## Why this slice
After `P3-011-I`, the public voice routes already resolved command and dialog collaborators through `runtime_access`, but the context build path still reached back into the intent handler for `mood_engine` and `habitus_service` every time `/api/v1/voice/intent`, `/api/v1/voice/ha/assist`, `/api/v1/voice/context`, `/api/v1/voice/hints`, or `VoiceCommandFlow` built context.

## Exact defect removed
The active voice context build path no longer sources habitus and mood collaborators directly from route-local handler access.

Repo-truth change:
- added `VoiceContextRuntime` as the narrow dependency bundle for context enrichment
- extended `VoiceRuntimeAccess` with `get_context_runtime()` so mood/pattern sourcing now resolves behind the same injected runtime seam as the rest of the voice stack
- rewired `api/v1/voice.py` context-building call sites to pass `context_runtime` instead of pulling `handler.mood_engine` and `handler.habitus_service` into the adapter path
- rewired `VoiceCommandFlow` to consume the same context-runtime seam for command-context assembly, with legacy fallback only when no runtime bundle is injected
- added focused contract coverage proving `/voice/intent` and `/voice/ha/assist` still enrich `relevant_patterns` even when the handler itself does not own a habitus service

## Files touched
- `addons/pilotsuite/app/copilot_core/voice/context_builder.py`
- `addons/pilotsuite/app/copilot_core/voice/runtime_access.py`
- `addons/pilotsuite/app/copilot_core/voice/command_flow.py`
- `addons/pilotsuite/app/copilot_core/api/v1/voice.py`
- `tests/test_voice_ha_assist_bridge_contract.py`
- `tests/test_voice_language_preference_slice402_contract.py`

## Verification
- `python3 -m py_compile addons/pilotsuite/app/copilot_core/voice/context_builder.py addons/pilotsuite/app/copilot_core/voice/runtime_access.py addons/pilotsuite/app/copilot_core/voice/command_flow.py addons/pilotsuite/app/copilot_core/api/v1/voice.py tests/test_voice_ha_assist_bridge_contract.py tests/test_voice_language_preference_slice402_contract.py`
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_voice_ha_assist_bridge_contract.py tests/test_voice_language_preference_slice402_contract.py tests/test_voice_command_api.py`
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_voice_command_api.py tests/test_voice_api_transcribe_synthesize_contract.py tests/test_voice_api_endpoint_contracts.py tests/test_voice_degraded_path_contract.py tests/test_voice_discovery_surface_contract.py tests/test_voice_ha_assist_bridge_contract.py tests/test_voice_language_preference_slice402_contract.py`
- result: `68 passed, 1 skipped`

## Blocker removed
The voice adapter and command-flow path no longer re-open direct context dependency sourcing outside `runtime_access`, so the remaining `P3-011` work can be decided from a smaller residual audit instead of another obvious route/runtime ownership leak.

## Next exact step
`P3-011-K / residual context-runtime closeout audit`:
check the remaining non-route `build_context(...)` callers (`voice_handler.py`, `voice/proactive.py`, and examples/docs) and decide whether one final runtime-side extraction is still needed or whether `P3-011` is functionally closed and the queue should move to the next visible Core landing.
