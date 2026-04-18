# PS_CORE_P3_011H_DIALOG_SNAPSHOT_BOUNDARY_CONSOLIDATION_2026-04-18

## Task
Land the next bounded `P3-011 / Hexagonal Architecture Refactor` slice after `P3-011-G` by removing the duplicate dialog-state projection logic still split between `VoiceDialogFlow` and `VoiceCommandFlow`.

## Why this slice
After `P3-011-G`, both the dialog routes and the command routes already ran through explicit application seams, but they still shaped the same dialog state in two different places.

## Exact defect removed
`copilot_core.voice.command_flow.VoiceCommandFlow` and `copilot_core.voice.dialog_flow.VoiceDialogFlow` no longer maintain separate normalization and serialization rules for dialog-state snapshots.

Repo-truth change:
- added one shared snapshot boundary in `copilot_core.voice.dialog_snapshot.DialogSnapshot`
- moved last-status normalization, pending-confirmation truth, command-state timestamp formatting, and shared projection fields into that one boundary
- rewired `VoiceDialogFlow` to project dialog read and mutation payloads from the shared snapshot
- rewired `VoiceCommandFlow` to project command `session_state` and `/command/state` payloads from the same shared snapshot surface
- added focused tests proving the shared snapshot can drive both dialog and command projections without divergence

## Files touched
- `addons/pilotsuite/app/copilot_core/voice/dialog_snapshot.py`
- `addons/pilotsuite/app/copilot_core/voice/dialog_flow.py`
- `addons/pilotsuite/app/copilot_core/voice/command_flow.py`
- `tests/test_voice_command_api.py`

## Verification
- `python3 -m py_compile addons/pilotsuite/app/copilot_core/voice/dialog_snapshot.py addons/pilotsuite/app/copilot_core/voice/dialog_flow.py addons/pilotsuite/app/copilot_core/voice/command_flow.py tests/test_voice_command_api.py`
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_voice_command_api.py tests/test_voice_api_transcribe_synthesize_contract.py tests/test_voice_api_endpoint_contracts.py tests/test_voice_degraded_path_contract.py tests/test_voice_discovery_surface_contract.py`
- result: `54 passed, 1 skipped`

## Blocker removed
The Core voice lane no longer has two drifting dialog-state serializers. Command and dialog seams now project one shared application-facing dialog snapshot boundary, so the next pull can target remaining confirmation-transition ownership instead of snapshot drift.

## Next exact step
`P3-011-I / confirmation transition seam tightening`:
move the remaining confirm/reject dialog-transition mechanics behind one narrower dialog-facing application helper so `VoiceCommandFlow` stops owning raw confirm/cancel state transition details too.
