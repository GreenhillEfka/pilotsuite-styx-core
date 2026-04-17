# PS Core — VFM-012 Slice 012-C solar surplus reporting surface

**Date:** 2026-04-17  
**Branch:** `pilotclaw/core-restore-runtime`  
**Status:** ✅ DONE

## Was

Added one thin service/reporting surface on top of the VFM-012 adapter seam so callers can hand over raw PV/load/price forecasts plus shiftable-device payloads and receive one normalized solar-surplus recommendation batch.

## Why

Slice 012-B normalized the inputs, but there was still no single canonical call that:

1. runs the forecast and candidate adapters,
2. invokes `SolarSurplusOptimizer.recommend(...)`, and
3. returns a stable report shape for later API/UI callers.

Without this slice, every consumer would still need to duplicate batch assembly and response shaping outside the optimizer.

## Change

Added `SolarSurplusOptimizer.get_recommendations_as_dict(...)` in `addons/pilotsuite/app/copilot_core/energy/solar_surplus_optimizer.py`.

The new reporting surface now:

- accepts raw forecast payloads and shiftable-device profiles
- normalizes them through `SolarSurplusSlot.from_forecasts(...)` and `SolarSurplusCandidate.from_shiftable_devices(...)`
- runs the pure recommendation kernel with a deterministic reference timestamp
- returns one stable batch with:
  - `generated_at`
  - `summary`
  - `recommendations`
  - `slots`
  - `candidates`

Added a focused contract test proving the batch shape, normalized input echo, and recommendation payload structure stay stable.

## Verification

- `python3 -m py_compile addons/pilotsuite/app/copilot_core/energy/solar_surplus_optimizer.py tests/test_solar_surplus_optimizer.py` → success
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_solar_surplus_optimizer.py` → `7 passed in 0.10s`

## Files touched

- `addons/pilotsuite/app/copilot_core/energy/solar_surplus_optimizer.py`
- `tests/test_solar_surplus_optimizer.py`
- `docs/analysis/PS_CORE_VFM_012C_SOLAR_SURPLUS_REPORTING_SURFACE_2026-04-17.md`

## Blocker removed

The VFM-012 chain now has one canonical Core-local batch/report surface instead of making future API or UI callers rebuild adapter invocation, optimizer execution, and response shaping on their own.

## Next single step

Land **VFM-012 Slice 012-D** by exposing this normalized batch through one thin token-protected energy API route and proving the route contract on a focused endpoint test.
