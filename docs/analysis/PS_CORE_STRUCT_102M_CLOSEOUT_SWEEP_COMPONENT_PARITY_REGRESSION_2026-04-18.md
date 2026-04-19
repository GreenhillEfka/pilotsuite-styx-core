# CORE-STRUCT-102M — Closeout sweep found remaining shared/public voice component-parity drift

**Date:** 2026-04-18 23:39 Europe/Berlin  
**Task:** Run the bounded `CORE-STRUCT-102` closeout sweep after `102L` and decide whether the hardened voice/runtime seam is actually clean, or whether one exact follow-on packet still remains.

## What the closeout sweep checked

After `CORE-STRUCT-102L`, the remaining question was no longer another ad hoc null-return branch on `/api/v1/voice/status`. The closeout sweep re-checked whether the shared helper-backed surfaces still exposed the same additive component-visibility truth that the public status surface already serves.

Specifically:
- `GET /api/v1/voice/status` still exposes a `components` block with `intent_handler`, `context_builder`, `proactive_hints`, `mood_engine`, `habitus_service`, `stt_engine`, `tts_engine`, and `nlu_engine`
- the shared helper `copilot_core.voice.voice_health.get_voice_health_block()` should still carry the same additive component ring if `CORE-STRUCT-102` is actually closed
- `copilot_core.api.voice_discovery.voice_capabilities_module()` should therefore inherit that same bounded component truth instead of dropping it on helper-backed consumers

## Finding

The closeout sweep found one real remaining drift instead of a clean `CORE-STRUCT-102` finish:

- `/api/v1/voice/status` still serves the additive `components` block
- `get_voice_health_block()` currently returns only `can_*`, `available_backends`, and `runtime`
- `voice_capabilities_module()` therefore also omits additive `components` truth because it forwards the helper payload as-is

That means the active seam is not actually closed yet: the public status surface and the shared helper/discovery surfaces no longer project the same bounded component-visibility truth.

## Verification

- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_voice_api_transcribe_synthesize_contract.py -k test_voice_status_exposes_shared_runtime_truth` → `1 passed, 7 deselected in 0.04s` ✅
- `/config/clawd/.venv_smoke_gate/bin/python - <<'PY' ... get_voice_health_block(); voice_capabilities_module() ... PY` → `helper_has_components= False`, `discovery_runtime_has_components= False` ✅

## Result

- blocker removed: the `CORE-STRUCT-102` closeout state is no longer ambiguous, because the sweep found one exact surviving shared/public component-parity regression instead of falsely declaring the chain complete
- scope held: no new implementation slice was opened from this cron run once the remaining mismatch was identified

## Next single step

`CORE-STRUCT-102N / restore additive voice component parity on helper-backed surfaces`:
- extend `copilot_core.voice.voice_health.get_voice_health_block()` with the same bounded `components` block already exposed on `/api/v1/voice/status`
- update `copilot_core.api.voice_discovery.voice_capabilities_module()` and helper-backed health/readiness proofs to lock that shared/public parity again
- then rerun the focused voice status, health-surface, and discovery contracts before re-attempting `CORE-STRUCT-102` closeout
