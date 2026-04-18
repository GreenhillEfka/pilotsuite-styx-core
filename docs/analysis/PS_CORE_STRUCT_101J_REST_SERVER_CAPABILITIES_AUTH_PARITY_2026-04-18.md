# PS Core — CORE-STRUCT-101J REST Server Capabilities Auth Parity

**Date:** 2026-04-18 16:18 Europe/Berlin
**Lane:** PilotClaw / Core
**Status:** ✅ DONE

## Why this slice exists

`CORE-STRUCT-101H/I` removed shadow `/api/v1/capabilities` handlers and aligned the Flask runtime surfaces on one canonical auth-gated discovery contract.

The next capability-consumer sweep found one remaining file-backed mismatch in the repo-root FastAPI compatibility server: `copilot_core/api/rest_server.py` still exposed `GET /api/v1/capabilities` without authentication, even though the canonical runtime surfaces now require a token.

That left a weaker unauthenticated capability contract alive in one shipped server surface and a stale test that normalized it.

## Artifacts changed

- `copilot_core/api/rest_server.py`
  - added `Depends(get_current_user)` to `GET /api/v1/capabilities`
  - documented that the compatibility server should not expose a weaker unauthenticated capability contract than the canonical Flask runtime
- `copilot_core/api/tests/test_rest_server.py`
  - replaced the open-access assumption with proof that unauthenticated requests now return `401`
  - added the authenticated happy-path assertion using a minted bearer token

## Blocker removed

The repo-root FastAPI compatibility server no longer leaves `/api/v1/capabilities` publicly readable while the canonical Core runtime treats the same surface as token-gated. Capability discovery auth truth is now consistent across the remaining shipped server variants touched in this sweep.

## Verification

```bash
python3 -m py_compile \
  copilot_core/api/rest_server.py \
  copilot_core/api/tests/test_rest_server.py

/config/clawd/.venv_smoke_gate/bin/python -m pytest -q \
  copilot_core/api/tests/test_rest_server.py

/config/clawd/.venv_smoke_gate/bin/python -m pytest -q \
  tests/test_voice_discovery_surface_contract.py \
  tests/test_voice_health_block_contract.py \
  tests/test_voice_health_surface_contract.py \
  tests/test_voice_api_transcribe_synthesize_contract.py \
  tests/test_voice_app_factory_route_contract.py \
  copilot_core/api/tests/test_rest_server.py
```

Result: `5 passed, 19 skipped` and `20 passed, 20 skipped`

## Next exact step

`CORE-STRUCT-101K / capability shape parity sweep` — decide whether the repo-root FastAPI compatibility server should keep its intentionally reduced module list or whether the remaining `/api/v1/capabilities` payload shape needs one more bounded alignment step, then land the smallest truthful fix.
