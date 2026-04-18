# PS_CORE_P3_011K_CONTEXT_RUNTIME_CLOSEOUT_2026-04-18

## Task
Finish the residual `P3-011 / Hexagonal Architecture Refactor` audit after `P3-011-J` by checking the remaining non-route `build_context(...)` callers and closing any last direct collaborator bundling defects.

## Why this slice
`P3-011-J` removed the obvious adapter-owned context dependency sourcing, but two internal callers still rebuilt context by passing raw `mood_engine` and `habitus_service` separately. The public queue named this as the last visible context-runtime audit before deciding whether `P3-011` is functionally closed.

## Exact defect removed
The remaining internal voice callers no longer pass loose mood/habitus collaborators into `VoiceContextBuilder`.

Repo-truth change:
- added a small `_get_context_runtime()` helper on `VoiceIntentHandler`
- added the same runtime-bundle helper on `ProactiveVoiceHints`
- rewired both self-built context paths to call `build_context(context_runtime=...)` instead of passing `mood_engine=` and `habitus_service=` directly
- exported `VoiceContextRuntime` from `copilot_core.voice` and updated the package doc examples plus `voice/README.md` to match the now-canonical runtime-bundle usage
- added focused contract coverage proving both internal callers hand one `VoiceContextRuntime` bundle to the builder instead of reopening raw collaborator plumbing

## Files touched
- `addons/pilotsuite/app/copilot_core/voice/voice_handler.py`
- `addons/pilotsuite/app/copilot_core/voice/proactive.py`
- `addons/pilotsuite/app/copilot_core/voice/__init__.py`
- `addons/pilotsuite/app/copilot_core/voice/README.md`
- `tests/test_voice_context_runtime_closeout_contract.py`

## Verification
- `python3 -m py_compile addons/pilotsuite/app/copilot_core/voice/voice_handler.py addons/pilotsuite/app/copilot_core/voice/proactive.py addons/pilotsuite/app/copilot_core/voice/__init__.py tests/test_voice_context_runtime_closeout_contract.py`
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_voice_context_runtime_closeout_contract.py tests/test_voice_command_api.py tests/test_voice_ha_assist_bridge_contract.py tests/test_voice_language_preference_slice402_contract.py`
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_voice_context_runtime_closeout_contract.py tests/test_voice_command_api.py tests/test_voice_api_transcribe_synthesize_contract.py tests/test_voice_api_endpoint_contracts.py tests/test_voice_degraded_path_contract.py tests/test_voice_discovery_surface_contract.py tests/test_voice_ha_assist_bridge_contract.py tests/test_voice_language_preference_slice402_contract.py`
- result: `70 passed, 1 skipped`

## Blocker removed
The last known voice-context self-build paths now use the same bounded runtime bundle instead of reopening separate mood and habitus collaborator wiring, so `P3-011` no longer has an obvious residual context-runtime seam leak.

## Next exact step
Start `CORE-STRUCT-101 / Runtime-API hardening` on the now-clean `P3-011` baseline, unless Orakel wants one explicit queue-close marker for `P3-011` first.
