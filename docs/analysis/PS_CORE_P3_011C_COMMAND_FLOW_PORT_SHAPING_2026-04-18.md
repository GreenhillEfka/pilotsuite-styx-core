# PS_CORE_P3_011C_COMMAND_FLOW_PORT_SHAPING_2026-04-18

## Task
Advance `P3-011` with the next bounded voice hex-boundary slice after the runtime seam already absorbed router and dialog-machine resolution.

## Landed change
Added `copilot_core.voice.command_flow.VoiceCommandFlow` as the application-facing command-flow service behind `POST /api/v1/voice/command`.

The service now owns the bounded procedure that used to live inline in the Flask adapter:
- build voice context
- route the utterance
- apply dialog-state transitions
- merge command status metadata
- assemble the stable public payload

`addons/pilotsuite/app/copilot_core/api/v1/voice.py` now keeps only request validation, zone normalization, HTTP error shaping, and `jsonify(...)` translation.
`addons/pilotsuite/app/copilot_core/voice/runtime_access.py` resolves the command-flow service through the same runtime seam already used for the other voice collaborators.

## Why this matters
After `P3-011-B`, the route no longer constructed its own router or dialog machine, but it still owned the whole command execution procedure. That kept the adapter too knowledgeable about application sequencing.

This slice moves procedure ownership behind one narrower Core port so the HTTP layer stops coordinating context build, routing, state mutation, and payload composition inline.

## Verification
- `python3 -m py_compile addons/pilotsuite/app/copilot_core/api/v1/voice.py addons/pilotsuite/app/copilot_core/voice/runtime_access.py addons/pilotsuite/app/copilot_core/voice/command_flow.py tests/test_voice_command_api.py` ✅
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_voice_command_api.py tests/test_voice_api_transcribe_synthesize_contract.py tests/test_voice_api_endpoint_contracts.py tests/test_voice_degraded_path_contract.py tests/test_voice_discovery_surface_contract.py` → `42 passed, 1 skipped in 0.50s` ✅

New proof points:
- `tests/test_voice_command_api.py::test_voice_command_route_delegates_to_command_flow_service`
- `tests/test_voice_command_api.py::test_voice_command_prefers_injected_runtime_seam`

## Blocker removed
`POST /api/v1/voice/command` no longer owns the end-to-end command-flow procedure in the adapter layer. The remaining `P3-011` follow-through can now focus on the adjacent confirm/reject/state endpoints instead of revisiting the primary command route.

## Next exact step
Check whether `/api/v1/voice/command/confirm`, `/api/v1/voice/command/reject`, and `/api/v1/voice/command/state` should consume the same application-facing command-flow seam instead of keeping adjacent dialog-state procedure in the adapter.
