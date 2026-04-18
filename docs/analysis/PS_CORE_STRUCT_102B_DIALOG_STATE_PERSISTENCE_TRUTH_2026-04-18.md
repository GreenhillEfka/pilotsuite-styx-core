# PS CORE STRUCT 102B — dialog-state persistence truth

## Context
After `CORE-STRUCT-102-A` closed the voice context cache replay leak, the next bounded `CORE-STRUCT-102 / Voice-Memory hardening` slice moved to the shipped dialog-state persistence seam.

The dialog state machine already claimed restart-safe persistence, but the live runtime helper still defaulted to a hardcoded `/data/dialog_state.json` path instead of following the add-on's runtime `DATA_DIR` seam.

## Exact defect removed
`copilot_core.voice.dialog_state.get_dialog_machine()` and `DialogStateMachine()` behaved as if the dialog state always lived under `/data`.

That meant a relocated add-on data directory could leave the voice dialog runtime writing and reloading state from the wrong place, even though the rest of the shipped runtime already treated `DATA_DIR` as the persistence authority.

In practice, dialog-state restart truth could drift from the actual runtime storage seam, so a restarted voice runtime could silently miss previously persisted session state.

## Decision
Keep the existing dialog-state file format and singleton behavior, but resolve the default persistence directory through `DATA_DIR` whenever callers do not pass an explicit `data_dir`.

This is the smallest truthful hardening step because it preserves the current dialog-state contract while aligning restart persistence with the same runtime storage seam the shipped add-on already uses elsewhere.

## Changes
- updated `addons/pilotsuite/app/copilot_core/voice/dialog_state.py`
- added one small runtime data-dir resolver for the dialog-state machine default path
- switched the default dialog-state persistence path from hardcoded `/data/dialog_state.json` to `$DATA_DIR/dialog_state.json`
- refreshed the module/class persistence docs so they describe the runtime-backed seam instead of the stale fixed path
- extended `tests/test_voice_command_api.py` with a restart contract proving `/api/v1/voice/dialog/activate` persists state into the runtime data dir and `/api/v1/voice/dialog/state` reloads it after a fresh runtime construction

## Result
The shipped voice dialog runtime no longer hardcodes `/data/dialog_state.json` when the add-on relocates persistent storage. Dialog-state restart truth now follows the runtime `DATA_DIR` seam, so persisted session state survives the same storage relocation path as the rest of the add-on's file-backed state.

## Verification
- `python3 -m py_compile addons/pilotsuite/app/copilot_core/voice/dialog_state.py tests/test_voice_command_api.py tests/test_voice_ha_assist_bridge_contract.py`
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_voice_command_api.py tests/test_voice_ha_assist_bridge_contract.py`
- result: `37 passed`

## Next step
Continue `CORE-STRUCT-102` with the next bounded voice-memory seam, likely a closeout sweep for any remaining dialog/command consumers that still bypass the runtime-backed dialog-state persistence seam or assume stale fixed-path storage truth.
