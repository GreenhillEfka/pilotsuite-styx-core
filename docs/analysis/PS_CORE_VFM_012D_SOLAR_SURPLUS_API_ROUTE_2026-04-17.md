# PS Core — VFM-012 Slice 012-D solar surplus API route

**Date:** 2026-04-17  
**Branch:** `pilotclaw/core-restore-runtime`  
**Status:** ✅ DONE

## Was

Exposed the VFM-012 normalized solar-surplus batch through one thin token-protected energy API route.

## Why

Slice 012-C created the canonical Core-local reporting surface, but callers still had no stable HTTP seam to submit raw forecast/device payloads and receive the normalized recommendation batch.

## Change

Added `POST /api/v1/energy/solar-surplus/recommendations` in `addons/pilotsuite/app/copilot_core/api/v1/energy_forecast.py`.

The route now:

- requires the existing token auth decorator
- accepts raw `pv_forecast`, optional `load_forecast`, optional `price_forecast`, and `shiftable_devices`
- accepts deterministic `reference_time` / `now` timestamps for stable callers and tests
- invokes `SolarSurplusOptimizer.get_recommendations_as_dict(...)`
- returns one stable batch with:
  - `ok`
  - `generated_at`
  - `summary`
  - `recommendations`
  - `slots`
  - `candidates`
- rejects malformed list/timestamp inputs with focused `400` responses

Added a focused route contract test covering:

- stable happy-path batch shape and recommendation payload
- required list validation
- ISO timestamp validation

## Verification

- `python3 -m py_compile addons/pilotsuite/app/copilot_core/api/v1/energy_forecast.py tests/test_energy_solar_surplus_route_contract.py` → success
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_energy_solar_surplus_route_contract.py tests/test_solar_surplus_optimizer.py` → `10 passed in 0.19s`

## Files touched

- `addons/pilotsuite/app/copilot_core/api/v1/energy_forecast.py`
- `tests/test_energy_solar_surplus_route_contract.py`
- `docs/analysis/PS_CORE_VFM_012D_SOLAR_SURPLUS_API_ROUTE_2026-04-17.md`

## Blocker removed

API and UI callers now have one live authenticated endpoint for the canonical solar-surplus batch instead of needing to import Core internals or rebuild normalization/report assembly themselves.

## Next single step

Wire the new route into the next caller surface, most likely the energy UI or automation-facing client seam that should consume the normalized `summary` and `recommendations` payload directly.
