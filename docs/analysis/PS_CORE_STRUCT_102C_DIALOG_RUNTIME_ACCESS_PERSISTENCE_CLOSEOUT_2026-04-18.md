# PS CORE STRUCT 102C — dialog runtime access persistence closeout

## Context
After `CORE-STRUCT-102-B` moved the dialog-state machine default persistence path onto `$DATA_DIR/dialog_state.json`, the next bounded `CORE-STRUCT-102 / Voice-Memory hardening` step was a closeout sweep across the remaining dialog and command consumers.

The key remaining risk was not the dialog-state machine itself anymore, but the runtime seam that constructs it for the shipped voice routes.

## Exact defect removed
`copilot_core.voice.runtime_access.VoiceRuntimeAccess.get_dialog_machine()` still called `get_dialog_machine()` without forwarding the runtime data directory resolved by the active app/services configuration.

That meant dialog and command consumers that correctly came through the runtime seam could still reopen the singleton dialog machine on its fallback path instead of the add-on runtime's configured `data_dir`.

In practice, `102-B` fixed the default persistence helper, but the installed voice runtime could still miss the app-specific storage seam when `COPILOT_CFG.data_dir` or the injected services config carried the authoritative runtime directory.

## Decision
Keep one dialog-state singleton and keep all dialog/command callers on the existing runtime seam, but make `VoiceRuntimeAccess` resolve the runtime `data_dir` before it constructs the dialog machine.

Prefer the injected services config when present, then fall back to `app.config["COPILOT_CFG"].data_dir`.

This is the smallest truthful closeout step because it preserves the existing dialog/command API contract while ensuring the runtime seam now points at the same persistence authority as the shipped add-on runtime.

## Changes
- updated `addons/pilotsuite/app/copilot_core/voice/runtime_access.py`
- added a small `_get_runtime_data_dir()` helper on `VoiceRuntimeAccess`
- passed the resolved runtime `data_dir` into `copilot_core.voice.dialog_state.get_dialog_machine(...)`
- extended `tests/test_voice_command_api.py` with focused coverage proving the runtime seam prefers `services["config"]["data_dir"]` and otherwise falls back to `COPILOT_CFG.data_dir`

## Result
The remaining shipped dialog/command consumers no longer bypass the runtime-backed dialog-state persistence seam when they construct the dialog machine through `VoiceRuntimeAccess`.

`CORE-STRUCT-102` now has the dialog-state closeout slice landed: the dialog-state machine default path follows `DATA_DIR`, and the runtime seam that owns dialog/command access now forwards the real runtime data dir instead of silently reopening fallback storage truth.

## Verification
- `python3 -m py_compile addons/pilotsuite/app/copilot_core/voice/runtime_access.py tests/test_voice_command_api.py`
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_voice_command_api.py tests/test_voice_ha_assist_bridge_contract.py`
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_voice_command_api.py tests/test_voice_ha_assist_bridge_contract.py tests/test_voice_context_cache_replay_isolation_contract.py tests/test_voice_context_runtime_closeout_contract.py tests/test_voice_language_preference_slice402_contract.py`
- results: `39 passed` and `48 passed`

## Next step
Move to the next prepared Core pull behind the hardened voice/runtime seam: keep the focused runtime verification ring green while selecting one bounded backend or consumer-facing follow-on packet instead of reopening another persistence micro-slice.
