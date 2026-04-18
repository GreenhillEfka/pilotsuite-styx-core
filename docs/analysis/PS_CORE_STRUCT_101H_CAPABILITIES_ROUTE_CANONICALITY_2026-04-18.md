# PS Core — CORE-STRUCT-101H Capabilities Route Canonicality

**Date:** 2026-04-18 15:54 Europe/Berlin
**Lane:** PilotClaw / Core
**Status:** ✅ DONE

## Why this slice exists

After `CORE-STRUCT-101G`, the next honest runtime-health sweep target was the capability/discovery surface used by monitoring and dev callers.

That sweep exposed a real duplication defect in the lightweight add-on app factory: `/api/v1/capabilities` was registered twice, once through the nested `api_v1.dev` blueprint and again directly in `copilot_core.app.create_app()`.

The live response already came from the blueprint route, but the second registration left the surface ambiguous and made future capability-truth changes easy to misapply to the shadowed handler.

## Artifacts changed

- `addons/pilotsuite/app/copilot_core/app.py`
  - removed the shadow `/api/v1/capabilities` registration from the lightweight app factory
  - left one canonical capability surface owned by `api_v1.dev.get_capabilities`
- `tests/test_voice_discovery_surface_contract.py`
  - replaced the skipped create-app capability check with a live contract proving only one `/api/v1/capabilities` rule is registered
  - locks that canonical route to the shared voice discovery module payload used by capability consumers

## Blocker removed

Capability and monitoring callers no longer sit behind two competing `/api/v1/capabilities` handlers in the lightweight add-on app. The canonical route is now singular, explicit, and contract-proven, so voice runtime truth for discovery/dev consumers cannot silently diverge behind a shadow registration.

## Verification

```bash
python3 -m py_compile \
  addons/pilotsuite/app/copilot_core/app.py \
  tests/test_voice_discovery_surface_contract.py

/config/clawd/.venv_smoke_gate/bin/python -m pytest -q \
  tests/test_voice_discovery_surface_contract.py \
  tests/test_voice_health_block_contract.py \
  tests/test_voice_health_surface_contract.py \
  tests/test_voice_api_transcribe_synthesize_contract.py \
  tests/test_voice_app_factory_route_contract.py
```

Result: `14 passed, 1 skipped`

## Next exact step

`CORE-STRUCT-101I / capability-surface parity sweep` — check whether the full production app factory (`addons/pilotsuite/app/main.py`) still advertises an older reduced `/api/v1/capabilities` payload than the canonical lightweight app/dev surface, and close that next truth mismatch if it is still live.
