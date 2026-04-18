# PS_CORE_P3_011B_COMMAND_FLOW_RUNTIME_EXTRACTION_2026-04-18

## Task
Advance `P3-011` with the next bounded voice hex-boundary slice after the runtime/service seam landed.

## Landed change
Extended `copilot_core.voice.runtime_access` so the command-flow adapter resolves these collaborators through the same seam:
- `VoiceCommandRouter`
- dialog state machine

`addons/pilotsuite/app/copilot_core/api/v1/voice.py` no longer constructs `VoiceCommandRouter(handler)` inline and no longer imports `get_dialog_machine()` directly in the adapter helper.

## Why this matters
The `POST /api/v1/voice/command` adapter still owned command-routing lifecycle even after `P3-011-A`. That meant the HTTP layer was still choosing and constructing part of the command-flow collaborator graph itself.

This slice keeps the route focused on request/response translation while the runtime seam owns collaborator selection.

## Verification
- `python3 -m py_compile addons/pilotsuite/app/copilot_core/voice/runtime_access.py addons/pilotsuite/app/copilot_core/api/v1/voice.py tests/test_voice_command_api.py` ✅
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_voice_command_api.py tests/test_voice_api_transcribe_synthesize_contract.py tests/test_voice_api_endpoint_contracts.py tests/test_voice_degraded_path_contract.py tests/test_voice_discovery_surface_contract.py` → `41 passed, 1 skipped in 0.46s` ✅

New proof point:
- `tests/test_voice_command_api.py::test_voice_command_prefers_injected_runtime_seam`
  verifies the command route prefers an injected runtime seam and does not fall back to `VoiceRuntimeAccess` construction when a runtime is already installed.

## Blocker removed
The command-flow adapter no longer constructs its own router or dialog machine path. The remaining `P3-011` work can now keep shrinking around smaller adapter-to-core boundaries instead of reopening the same command collaborator ownership defect.

## Next exact step
`P3-011-C / Voice command-flow port shaping`:
extract the remaining command route orchestration into a narrower application-facing service/port so the HTTP adapter stops coordinating context build + route + state mutation as one large inline procedure.
