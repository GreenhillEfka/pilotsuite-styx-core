# PS_CORE_P3_011F_DIALOG_STATE_FLOW_EXTRACTION_2026-04-18

## Task
Take the next bounded `P3-011 / Hexagonal Architecture Refactor` slice after `P3-011-E` by removing the remaining adapter-owned `/api/v1/voice/dialog/state` procedure from `api/v1/voice.py`.

## Why this slice
After `P3-011-E`, the command family already delegates through explicit flow/result boundaries, but the adjacent dialog-state route still owned timeout handling, dialog-state normalization, and HTTP payload shaping inline in the Flask adapter.

## Exact defect removed
`GET /api/v1/voice/dialog/state` no longer reads the dialog machine directly inside `addons/pilotsuite/app/copilot_core/api/v1/voice.py`.

Repo-truth change:
- added `copilot_core.voice.dialog_flow.VoiceDialogFlow`
- added bounded `DialogStateResult`
- extended `copilot_core.voice.runtime_access.VoiceRuntimeAccess` with `get_dialog_flow()`
- slimmed the HTTP route to `jsonify(_get_dialog_flow().get_state().to_dict())`
- removed now-dead route-local dialog-state serialization helpers from `voice.py`

## Files touched
- `addons/pilotsuite/app/copilot_core/voice/dialog_flow.py`
- `addons/pilotsuite/app/copilot_core/voice/runtime_access.py`
- `addons/pilotsuite/app/copilot_core/api/v1/voice.py`
- `tests/test_voice_command_api.py`

## Verification
- `python3 -m py_compile addons/pilotsuite/app/copilot_core/voice/dialog_flow.py addons/pilotsuite/app/copilot_core/voice/runtime_access.py addons/pilotsuite/app/copilot_core/api/v1/voice.py tests/test_voice_command_api.py`
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_voice_command_api.py tests/test_voice_api_transcribe_synthesize_contract.py tests/test_voice_api_endpoint_contracts.py tests/test_voice_degraded_path_contract.py tests/test_voice_discovery_surface_contract.py`
- result: `47 passed, 1 skipped`

## Blocker removed
The voice adapter no longer owns the dialog-state read procedure for timeout/decay plus payload normalization, so the next hex-boundary work can focus on the remaining dialog mutation routes instead of re-litigating state-read logic inside Flask.

## Next exact step
`P3-011-G / dialog mutation seam extraction`:
move `/api/v1/voice/dialog/activate`, `/dialog/confirm`, `/dialog/clarify`, and `/dialog/reset` behind the same application-facing dialog-flow seam so the adapter stops calling the dialog machine directly for state mutations too.
