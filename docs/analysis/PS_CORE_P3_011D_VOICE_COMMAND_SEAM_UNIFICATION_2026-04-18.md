# PS_CORE_P3_011D_VOICE_COMMAND_SEAM_UNIFICATION_2026-04-18

## Task
Advance `P3-011` by removing the remaining inline command follow-through procedure from the HTTP adapter.

## Landed change
`/api/v1/voice/command/state`, `/api/v1/voice/command/confirm`, and `/api/v1/voice/command/reject` now delegate through `copilot_core.voice.command_flow.VoiceCommandFlow` instead of owning dialog-machine procedure directly inside `api/v1/voice.py`.

### What moved behind the seam
- pending-confirmation validation
- session-scoped command-state projection
- confirm follow-through response assembly
- reject follow-through state clearing

## Why this matters
After `P3-011-C`, the main `/command` route already delegated through `VoiceCommandFlow`, but the adjacent follow-up routes still held dialog-state procedure in the adapter layer. This slice makes the command family consistent: the Flask route now handles HTTP validation/shape only, while the application-facing command-flow service owns command procedure.

## Proof
Focused verification ring:
- `python3 -m py_compile addons/pilotsuite/app/copilot_core/api/v1/voice.py addons/pilotsuite/app/copilot_core/voice/command_flow.py addons/pilotsuite/app/copilot_core/voice/runtime_access.py tests/test_voice_command_api.py` ✅
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_voice_command_api.py tests/test_voice_api_transcribe_synthesize_contract.py tests/test_voice_api_endpoint_contracts.py tests/test_voice_degraded_path_contract.py tests/test_voice_discovery_surface_contract.py` → `45 passed, 1 skipped in 0.57s` ✅

New proof points:
- `tests/test_voice_command_api.py::test_voice_command_state_route_delegates_to_command_flow_service`
- `tests/test_voice_command_api.py::test_voice_command_confirm_route_delegates_to_command_flow_service`
- `tests/test_voice_command_api.py::test_voice_command_reject_route_delegates_to_command_flow_service`

## Blocker removed
The voice command follow-through family no longer has a split architecture where `/command` used the seam but `/command/state|confirm|reject` still bypassed it. The adapter-side command procedure is now consolidated behind one application-facing flow seam.

## Next exact step
`P3-011-E / command-flow result object shaping`:
shrink the remaining dict-shaped route contract inside `VoiceCommandFlow` into one explicit result object or serializer boundary so the seam stops returning raw HTTP-oriented payload dictionaries.
