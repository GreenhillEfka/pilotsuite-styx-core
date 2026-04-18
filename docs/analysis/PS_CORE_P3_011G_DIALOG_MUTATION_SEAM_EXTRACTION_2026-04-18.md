# PS_CORE_P3_011G_DIALOG_MUTATION_SEAM_EXTRACTION_2026-04-18

## Task
Take the next bounded `P3-011 / Hexagonal Architecture Refactor` slice after `P3-011-F` by removing the remaining adapter-owned dialog mutation procedure from `api/v1/voice.py`.

## Why this slice
After `P3-011-F`, `GET /api/v1/voice/dialog/state` already delegated through `VoiceDialogFlow`, but the adjacent mutation family still called the dialog machine directly from the Flask adapter.

## Exact defect removed
`POST /api/v1/voice/dialog/activate`, `/dialog/confirm`, `/dialog/clarify`, and `/dialog/reset` no longer mutate dialog state directly inside `addons/pilotsuite/app/copilot_core/api/v1/voice.py`.

Repo-truth change:
- extended `copilot_core.voice.dialog_flow.VoiceDialogFlow` with bounded mutation methods for activate, confirm/cancel, clarify, and reset
- added explicit result objects `DialogActivateResult`, `DialogConfirmResult`, `DialogClarifyResult`, and `DialogResetResult`
- slimmed the four HTTP routes down to validation plus `jsonify(_get_dialog_flow()....to_dict())`
- added focused route coverage proving the dialog mutation routes delegate to the dialog-flow seam and do not fall back to direct dialog-machine mutation in the adapter

## Files touched
- `addons/pilotsuite/app/copilot_core/voice/dialog_flow.py`
- `addons/pilotsuite/app/copilot_core/api/v1/voice.py`
- `tests/test_voice_command_api.py`

## Verification
- `python3 -m py_compile addons/pilotsuite/app/copilot_core/voice/dialog_flow.py addons/pilotsuite/app/copilot_core/api/v1/voice.py tests/test_voice_command_api.py`
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_voice_command_api.py tests/test_voice_api_transcribe_synthesize_contract.py tests/test_voice_api_endpoint_contracts.py tests/test_voice_degraded_path_contract.py tests/test_voice_discovery_surface_contract.py`
- result: `52 passed, 1 skipped`

## Blocker removed
The voice adapter no longer owns any direct dialog mutation path on the public `/api/v1/voice/dialog/*` family, so the remaining hex-boundary work can focus on shared serializer/runtime cleanup instead of route-local state transition code.

## Next exact step
`P3-011-H / dialog-flow serializer boundary consolidation`:
remove the remaining duplicate dialog-state serialization logic between `VoiceDialogFlow` and `VoiceCommandFlow` so the command and dialog seams project one shared application-facing dialog snapshot boundary.
