# PS_CORE_P3_011A_VOICE_RUNTIME_ACCESS_SEAM_2026-04-18

## Task
Land the first bounded `P3-011 / Hexagonal Architecture Refactor` slice by extracting the voice route layer off ad-hoc service construction and onto one shared runtime access seam.

## Why this slice
`addons/pilotsuite/app/copilot_core/api/v1/voice.py` was still constructing and caching concrete voice collaborators directly in the HTTP adapter. That kept object lifecycle, dependency selection, and route logic collapsed into one file.

## Landed change
Introduced `addons/pilotsuite/app/copilot_core/voice/runtime_access.py` as the single service-access seam for voice routes.

What moved behind the seam:
- `VoiceIntentHandler`
- `VoiceContextBuilder`
- `WhisperSTT`
- `PiperTTS`
- `NLUEngine`
- `ProactiveVoiceHints`
- generated-audio cache

Route-layer effect:
- `api/v1/voice.py` now resolves shared collaborators through `get_voice_runtime()` helper accessors instead of constructing them on `current_app`
- `core_setup.register_blueprints(...)` now installs the voice runtime seam from `COPILOT_SERVICES` before voice routes run
- the lightweight add-on app factory also installs the same seam early for parity

## Proof
Focused verification ring:
- `python3 -m py_compile addons/pilotsuite/app/copilot_core/voice/runtime_access.py addons/pilotsuite/app/copilot_core/api/v1/voice.py addons/pilotsuite/app/copilot_core/core_setup.py addons/pilotsuite/app/copilot_core/app.py tests/test_voice_api_transcribe_synthesize_contract.py` ✅
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_voice_api_transcribe_synthesize_contract.py tests/test_voice_api_endpoint_contracts.py tests/test_voice_degraded_path_contract.py tests/test_voice_discovery_surface_contract.py` → `28 passed, 1 skipped in 0.33s` ✅

New contract coverage:
- `tests/test_voice_api_transcribe_synthesize_contract.py::test_voice_status_prefers_injected_runtime_seam`
  proves the route consumes an injected runtime seam and does not fall back to ad-hoc `VoiceRuntimeAccess` construction when a runtime is already installed.

## Blocker removed
`P3-011` is no longer a vague architecture intention. The first concrete hex-boundary defect is now code-landed: the voice HTTP adapter no longer owns the primary construction path for its concrete voice services.

## Next exact step
`P3-011-B / Command-router runtime extraction`:
move the remaining in-route `VoiceCommandRouter(handler)` bootstrap behind the same seam so `/api/v1/voice/intent` stops constructing the command-routing collaborator in the adapter layer too.
