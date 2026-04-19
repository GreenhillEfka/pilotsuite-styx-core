# PS CORE-STRUCT-102O — Closeout sweep found the surviving standalone `/voice/status` mood-engine parity drift

## Task
Re-run the bounded `CORE-STRUCT-102` closeout sweep after `102N` and decide whether the hardened voice/runtime seam is actually clean, or whether one exact follow-on packet still remains.

## Findings
- The focused voice status/helper/discovery proof ring stays green after `102N` (`23 passed`), so the helper-backed additive `components` contract is still landed.
- `voice_capabilities_module()` now matches the shared helper on `runtime.components` in the standalone path.
- The public `GET /api/v1/voice/status` route still drifts from the shared helper on the standalone fallback path: the route reports `components.mood_engine = "available"` while `get_voice_health_block()` reports `"unavailable"` for the same no-runtime/default probe.
- The drift is isolated to the route-local fallback component projection in `addons/pilotsuite/app/copilot_core/api/v1/voice.py`; it is not a wider discovery/helper regression.

## Verification
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_voice_api_transcribe_synthesize_contract.py tests/test_voice_health_block_contract.py tests/test_voice_health_surface_contract.py tests/test_voice_discovery_surface_contract.py` → `23 passed in 2.79s` ✅
- `/config/clawd/.venv_smoke_gate/bin/python - <<'PY' ... status/helper/discovery parity probe ... PY` → `status_helper_components_match False`, `discovery_helper_components_match True` ✅
- Detailed diff from the same live probe:
  - `status.components.mood_engine = "available"`
  - `helper.components.mood_engine = "unavailable"`
  - all other component keys matched ✅

## Result
`CORE-STRUCT-102` is not honestly closed yet. One exact surviving standalone/public parity slice remains: align `/api/v1/voice/status` fallback `components.mood_engine` truth with the shared helper on the no-runtime path, then re-run the same bounded closeout proof ring.

## Next exact pull
`CORE-STRUCT-102P / align standalone `/api/v1/voice/status` mood-engine component truth with the shared helper fallback`
