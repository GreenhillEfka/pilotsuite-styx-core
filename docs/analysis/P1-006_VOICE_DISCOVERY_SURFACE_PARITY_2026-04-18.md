# P1-006 Voice discovery surface parity (2026-04-18)

## Problem

The bounded P1-006 rescue had already restored the public voice runtime routes on the add-on app surface, but two discovery layers still lagged behind that runtime truth:

- the shipped `/api/v1/capabilities` discovery payload still exposed only the legacy `voice_context` helper surface and omitted any dedicated public `voice` module entry.
- `copilot_core/api/rest_api.py` still advertised the stale `POST /api/v1/voice/process` route and omitted the restored public runtime routes like `/intent`, `/speak`, `/status`, `/audio/<audio_id>`, `/zones`, and `/intents`.

That left route discovery and generated registry/OpenAPI metadata behind the shipped runtime surface.

## Bounded fix

- added shared `addons/pilotsuite/app/copilot_core/api/voice_discovery.py` metadata so both discovery surfaces read from one bounded public voice contract
- wired that shared contract into `addons/pilotsuite/app/copilot_core/api/v1/dev.py` and `addons/pilotsuite/app/copilot_core/app.py`, so `/api/v1/capabilities` now advertises a dedicated `voice` module alongside the legacy `voice_context` helper surface
- replaced the stale repo-root REST registry `voice/process` advertisement with the actual public voice routes now exposed by the add-on runtime
- added focused contract coverage for the authenticated `/api/v1/capabilities` payload and the repo-root REST registry

## Result

Discovery layers now point at the same bounded public voice surface the runtime actually exposes:

- `/api/v1/voice/intent`
- `/api/v1/voice/transcribe`
- `/api/v1/voice/synthesize`
- `/api/v1/voice/speak`
- `/api/v1/voice/status`
- `/api/v1/voice/audio/<audio_id>`
- `/api/v1/voice/zones`
- `/api/v1/voice/intents`

The legacy `voice_context` helper surface remains separate instead of masquerading as the public voice runtime contract.

## Verification

```bash
cd /config/clawd/team/worktrees/pilotsuite-styx-core-current
python3 -m py_compile addons/pilotsuite/app/copilot_core/api/voice_discovery.py addons/pilotsuite/app/copilot_core/app.py addons/pilotsuite/app/copilot_core/api/v1/dev.py copilot_core/api/rest_api.py tests/test_voice_discovery_surface_contract.py
PYTHONPATH=/config/clawd/team/worktrees/pilotsuite-styx-core-current/.venv-validate/lib/python3.11/site-packages python3 - <<'PY'
# authenticated create_app() capabilities check + REST registry parity assertions
PY
```

## Next single step

Take the next bounded Runtime/API hardening pull by making the runtime readiness surface explicit in `core_setup.py` / runtime health, now that voice route discovery no longer lies about the restored public surface.
