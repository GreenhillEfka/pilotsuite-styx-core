# PS Core — CORE-STRUCT-101G Voice Health HTTP Surface Proof

**Date:** 2026-04-18 14:53 Europe/Berlin
**Lane:** PilotClaw / Core
**Status:** ✅ DONE

## Why this slice exists

`CORE-STRUCT-101F` fixed the shared helper so partial backend truth survives import failures, but that guarantee still lived only at the helper unit level.

This slice closes the loop at the HTTP boundary so helper-backed public surfaces cannot silently regress and re-collapse partial voice truth during future app/bootstrap/auth changes.

## Artifacts changed

- `tests/test_voice_health_surface_contract.py`
  - added focused app-level proof that `/health`, `/api/v1/status`, and `/api/v1/ready` all preserve helper-provided partial voice truth
  - covers both TTS-only and STT-only partial-availability payloads
  - stubs health checker + app bootstrap dependencies so the contract stays bounded and non-flaky

## Blocker removed

The independent partial-backend truth is now locked at the HTTP surface, not only inside `voice_health.py`. Future changes to app wiring, readiness, or bootstrap auth are now less likely to reintroduce silent voice-block drift.

## Verification

```bash
python3 -m py_compile \
  tests/test_voice_health_surface_contract.py

/config/clawd/.venv_smoke_gate/bin/python -m pytest -q \
  tests/test_voice_health_block_contract.py \
  tests/test_voice_health_surface_contract.py \
  tests/test_voice_command_api.py \
  tests/test_voice_api_transcribe_synthesize_contract.py \
  tests/test_voice_api_endpoint_contracts.py \
  tests/test_voice_degraded_path_contract.py \
  tests/test_voice_discovery_surface_contract.py \
  tests/test_voice_ha_assist_bridge_contract.py \
  tests/test_voice_language_preference_slice402_contract.py
```

Result: `74 passed, 1 skipped`

## Next exact step

`CORE-STRUCT-101H / runtime-health consumer sweep` — scan the remaining non-HTTP consumers of voice runtime truth, especially monitoring/dev surfaces, and close the next smallest remaining mismatch or duplication.
