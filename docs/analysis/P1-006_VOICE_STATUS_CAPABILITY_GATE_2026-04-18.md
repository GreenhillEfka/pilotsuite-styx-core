# P1-006 Voice Status Capability Gate — 2026-04-18

## Why this slice existed
After the degraded-path rescue, `/api/v1/voice/status` exposed backend runtime truth, but HA still had to infer which voice actions were safe to call. The next bounded fix was to project that runtime truth into one explicit capability gate on the same status surface.

## What landed
- extended `addons/pilotsuite/app/copilot_core/api/v1/voice.py`
  - added cached `_get_nlu_engine()` for the shipped rule-based NLU seam
  - extended `runtime` with `nlu`
  - added top-level `capabilities` with `can_transcribe`, `can_synthesize`, `can_speak`, `can_dialog`
  - derived `can_dialog` from the real intent-handler + STT + TTS + NLU availability path
- extended `tests/test_voice_api_transcribe_synthesize_contract.py`
  - verifies all capability flags go true when all voice backends are available
  - verifies the gate turns false when STT/TTS are unavailable so HA no longer needs route probing

## Bounded contract
`GET /api/v1/voice/status`

```json
{
  "status": "ok",
  "runtime": {
    "stt": {"available": true},
    "tts": {"available": true},
    "nlu": {"available": true, "engine": "rule_based"}
  },
  "capabilities": {
    "can_transcribe": true,
    "can_synthesize": true,
    "can_speak": true,
    "can_dialog": true
  }
}
```

## Verification
```bash
cd /config/clawd/team/worktrees/pilotsuite-styx-core-current
python3 -m py_compile addons/pilotsuite/app/copilot_core/api/v1/voice.py tests/test_voice_api_transcribe_synthesize_contract.py
/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_voice_api_transcribe_synthesize_contract.py tests/test_voice_api_endpoint_contracts.py tests/test_voice_degraded_path_contract.py
# 25 passed
```

## Blocker removed
HA consumers can now branch on one truthful capability gate instead of discovering STT/TTS availability through failing route calls.

## Next exact step
Consume these `capabilities` flags on the HA side (`HA-552-B`) so coordinator truth and UI branching stop probing backend failures directly.
