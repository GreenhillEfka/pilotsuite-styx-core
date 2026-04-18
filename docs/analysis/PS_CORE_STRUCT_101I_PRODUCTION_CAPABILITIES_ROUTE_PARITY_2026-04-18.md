# PS Core — CORE-STRUCT-101I Production Capabilities Route Parity

**Date:** 2026-04-18 16:12 Europe/Berlin
**Lane:** PilotClaw / Core
**Status:** ✅ DONE

## Why this slice exists

`CORE-STRUCT-101H` removed the shadow `/api/v1/capabilities` handler from the lightweight add-on app factory.

The same sweep showed the full production app factory in `addons/pilotsuite/app/main.py` still registered its own older reduced `/api/v1/capabilities` payload after `register_blueprints(...)` had already installed the canonical `copilot_core.api.v1.dev.get_capabilities` route.

In live routing, the blueprint handler won, but the second registration left the production app with the same ambiguity and a stale security doc that still claimed the surface was unauthenticated.

## Artifacts changed

- `addons/pilotsuite/app/main.py`
  - removed the shadow production `/api/v1/capabilities` handler
  - left one canonical capability/discovery surface owned by the dev blueprint registered during `register_blueprints(...)`
- `tests/test_voice_discovery_surface_contract.py`
  - added live contract proof that the production app now exposes exactly one `/api/v1/capabilities` rule
  - proved the canonical route stays auth-gated and still returns the shared `voice_capabilities_module()` payload
- `docs/SECURITY_POLICY.md`
  - corrected the authentication table so `GET /api/v1/capabilities` matches the live token-gated route truth

## Blocker removed

The production app no longer carries a dead reduced `/api/v1/capabilities` shadow route behind the canonical dev blueprint surface. Capability/discovery callers now see one auth-consistent route in both factories, and the repo docs no longer claim a weaker unauthenticated contract than the runtime actually enforces.

## Verification

```bash
python3 -m py_compile \
  addons/pilotsuite/app/copilot_core/app.py \
  addons/pilotsuite/app/main.py \
  tests/test_voice_discovery_surface_contract.py

/config/clawd/.venv_smoke_gate/bin/python -m pytest -q \
  tests/test_voice_discovery_surface_contract.py \
  tests/test_voice_health_block_contract.py \
  tests/test_voice_health_surface_contract.py \
  tests/test_voice_api_transcribe_synthesize_contract.py \
  tests/test_voice_app_factory_route_contract.py
```

Result: `15 passed, 1 skipped`

## Next exact step

`CORE-STRUCT-101J / capability consumer truth sweep` — scan the remaining file-backed capability consumers and docs around `/api/v1/capabilities` for any lingering assumptions about duplicate handlers, reduced module payloads, or unauthenticated access, and close the next smallest remaining mismatch.
