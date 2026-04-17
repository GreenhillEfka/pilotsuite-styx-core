# PS Core — VFM-012 Slice 012-E automations caller-surface integration

**Date:** 2026-04-17  
**Branch:** `pilotclaw/core-restore-runtime`  
**Status:** ✅ DONE

## Was

Wired the new canonical solar-surplus recommendation batch into one real automation-facing caller surface.

## Why

Slice 012-D exposed `POST /api/v1/energy/solar-surplus/recommendations`, but the new route was still orphaned from product-facing Core behavior. Slice 012-E needed one live caller seam so the optimizer could drive an actual user-visible automation path instead of remaining API-only.

## Change

Extended the automation suggestions surface so `POST /api/v1/automations/generate` now accepts `solar_surplus_batches` and turns actionable optimizer recommendations into stored energy suggestions.

The caller seam now:

- parses deterministic `reference_time` / `now` inputs for stable batch generation
- invokes `SolarSurplusOptimizer.get_recommendations_as_dict(...)` through the automations API seam
- converts actionable `schedule_now` / `schedule_at` recommendations into `AutomationSuggestionEngine` energy suggestions
- preserves the canonical batch report in the response under `solar_surplus_batches`
- leaves non-actionable optimizer outputs visible in the batch report without generating false suggestion records

Added focused regression coverage proving:

- one solar-surplus batch can generate one persisted automation suggestion through `/api/v1/automations/generate`
- the returned batch keeps canonical recommendation/report data alongside generated suggestion ids
- non-actionable optimizer outputs still return the batch report while generating zero suggestions

## Verification

- `python3 -m py_compile addons/pilotsuite/app/copilot_core/automations/api.py addons/pilotsuite/app/copilot_core/automations/suggestion_engine.py tests/test_automations_solar_surplus_generate_contract.py` → success
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_automations_solar_surplus_generate_contract.py tests/test_energy_solar_surplus_route_contract.py tests/test_solar_surplus_optimizer.py` → `12 passed in 0.22s`

## Files touched

- `addons/pilotsuite/app/copilot_core/automations/api.py`
- `addons/pilotsuite/app/copilot_core/automations/suggestion_engine.py`
- `tests/test_automations_solar_surplus_generate_contract.py`
- `docs/analysis/PS_CORE_VFM_012E_AUTOMATIONS_CALLER_SURFACE_INTEGRATION_2026-04-17.md`

## Blocker removed

The solar-surplus API route is no longer a dead-end backend surface. Core now has one live automation-facing caller path that consumes the canonical optimizer batch and turns it into persisted suggestion output.

## Next single step

Start **VFM-002 / CORE-VFM-002-A** by opening the first bounded `/api/v1/voice/command` route slice with explicit `safe / clarify / confirm / reject` contract coverage.
