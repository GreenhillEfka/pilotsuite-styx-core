# PS CORE-STRUCT-102P — Standalone `/voice/status` mood-engine parity restored

## Task
Land the exact `CORE-STRUCT-102P` follow-on behind `102O` by aligning standalone `/api/v1/voice/status` `components.mood_engine` truth with the shared helper/discovery fallback without widening into a broader runtime slice.

## Findings
- The surviving drift was not a wider helper/discovery defect. It came from `/api/v1/voice/status` calling `_build_voice_status_config()`, which auto-installed the voice runtime seam on a plain standalone probe just to read default hint config values.
- That side effect mutated later helper/discovery reads on the same app, reopening standalone/public `mood_engine` parity drift after the route already emitted the no-runtime fallback payload.
- Keeping the standalone status path on canonical `HintConfig()` defaults unless a voice runtime is already installed restores one stable no-runtime truth ring across status, helper, and discovery.

## Changes
- tightened `addons/pilotsuite/app/copilot_core/api/v1/voice.py` so `_build_voice_status_config()` no longer auto-installs the runtime seam on a plain standalone status probe
- kept injected-runtime behavior intact by still reading live proactive-hints config when a runtime seam is already installed
- added a focused regression in `tests/test_voice_api_transcribe_synthesize_contract.py` proving one standalone `/api/v1/voice/status` request keeps `mood_engine` parity aligned across the route payload, `get_voice_health_block()`, and `voice_capabilities_module()`

## Verification
- `python3 -m py_compile addons/pilotsuite/app/copilot_core/api/v1/voice.py tests/test_voice_api_transcribe_synthesize_contract.py` ✅
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_voice_api_transcribe_synthesize_contract.py tests/test_voice_health_block_contract.py tests/test_voice_health_surface_contract.py tests/test_voice_discovery_surface_contract.py` → `27 passed in 2.62s` ✅
- `/config/clawd/.venv_smoke_gate/bin/python /tmp/pilotsuite_core_102p_probe.py` → `status_helper_components_match=True`, `discovery_helper_components_match=True`, all three surfaces report `components.mood_engine="unavailable"` on the same standalone probe ✅

## Result
- blocker removed: standalone `/api/v1/voice/status`, the shared health helper, and discovery now keep one bounded `mood_engine` component truth instead of drifting after the status probe mutates runtime state
- scope held: the slice stayed inside the exact `102P` parity packet and stopped after proof plus checkpoint-ready evidence

## Next exact pull
Re-run the bounded `CORE-STRUCT-102` closeout sweep now that the last known standalone/public `mood_engine` parity drift is closed, and either close the seam honestly or file the next exact residual packet if one still exists.
