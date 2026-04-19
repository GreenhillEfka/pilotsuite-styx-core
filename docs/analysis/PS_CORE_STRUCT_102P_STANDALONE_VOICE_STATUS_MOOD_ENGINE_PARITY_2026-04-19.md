# PS CORE-STRUCT-102P — Standalone `/voice/status` mood-engine parity restored

## Task
Align standalone `GET /api/v1/voice/status` `components.mood_engine` truth with the shared helper fallback, then rerun the same bounded `CORE-STRUCT-102` closeout proof ring.

## Changes
- taught `copilot_core.voice.voice_health.get_voice_health_block()` to use runtime-backed component truth only when a voice runtime seam is already installed on the current app, instead of auto-creating one for standalone helper/status probes
- kept the route-local fallback in `copilot_core.api.v1.voice` bounded so missing `components` payloads still preserve installed-runtime component truth while no-runtime standalone fallback stays aligned with the shared helper
- widened the focused contract ring with standalone helper coverage plus explicit fallback/runtime status coverage for `components.mood_engine`

## Verification
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_voice_api_transcribe_synthesize_contract.py tests/test_voice_health_block_contract.py tests/test_voice_health_surface_contract.py tests/test_voice_discovery_surface_contract.py` → `26 passed in 2.85s` ✅
- `/config/clawd/.venv_smoke_gate/bin/python - <<'PY' ... status/helper/discovery parity probe ... PY` → `status_helper_components_match=True`, `discovery_helper_components_match=True`, `status_mood_engine=unavailable`, `helper_mood_engine=unavailable` ✅

## Result
- blocker removed: standalone `/api/v1/voice/status`, `get_voice_health_block()`, and `voice_capabilities_module()` now agree on `components.mood_engine` truth instead of leaving the public status route as the last surviving standalone/public parity drift
- scope held: this slice stayed on the exact `102P` parity packet and stopped after the closeout proof ring went green again

## Next exact pull
Re-run the bounded `CORE-STRUCT-102` closeout sweep on the now-aligned standalone/shared/public truth ring and decide whether the seam is honestly closed or one final file-backed packet remains.
