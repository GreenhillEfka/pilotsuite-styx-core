# PS Core — VFM-012 Slice 012-B forecast and candidate adapters

**Date:** 2026-04-17  
**Branch:** `pilotclaw/core-restore-runtime`  
**Status:** ✅ DONE

## Was

Wired deterministic adapter helpers into the pure `solar_surplus_optimizer.py` kernel so existing energy forecast surfaces and shiftable-device profiles can be normalized into the optimizer without Home Assistant runtime coupling.

## Why

Slice 012-A created the policy kernel, but later slices still needed a stable translation seam from real forecast/candidate payload shapes into `SolarSurplusSlot` and `SolarSurplusCandidate` inputs.

Without this adapter layer, every caller would have to re-implement timestamp alignment, default handling, and device eligibility rules outside the optimizer.

## Change

Added bounded adapter helpers in `addons/pilotsuite/app/copilot_core/energy/solar_surplus_optimizer.py`:

- `SolarSurplusSlot.from_forecast_point(...)`
- `SolarSurplusSlot.from_forecasts(...)`
- `SolarSurplusCandidate.from_shiftable_device(...)`
- `SolarSurplusCandidate.from_shiftable_devices(...)`

The new adapter path now:
- accepts dataclasses, mappings, and simple objects from existing energy surfaces
- aligns PV, load, and price forecasts by canonical UTC hour and shared horizon
- derives safe defaults when optional forecast fields are missing
- filters out non-idle / non-ready devices before they enter the scheduling kernel
- normalizes candidate start windows against allowed-hour bounds and completion deadlines

## Verification

- `python3 -m py_compile addons/pilotsuite/app/copilot_core/energy/solar_surplus_optimizer.py tests/test_solar_surplus_optimizer.py` → success
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_solar_surplus_optimizer.py` → `6 passed in 0.15s`

## Files touched

- `addons/pilotsuite/app/copilot_core/energy/solar_surplus_optimizer.py`
- `tests/test_solar_surplus_optimizer.py`
- `docs/analysis/PS_CORE_VFM_012B_FORECAST_AND_CANDIDATE_ADAPTERS_2026-04-17.md`

## Blocker removed

The VFM-012 chain now has a canonical adapter seam between existing energy forecasts / shiftable-device payloads and the pure optimizer kernel, so the next slice can consume normalized inputs instead of rebuilding alignment logic again.

## Next single step

Land **VFM-012 Slice 012-C** by exposing one thin service/reporting surface that calls these adapters plus `SolarSurplusOptimizer.recommend(...)`, then prove the returned recommendation batch shape on a focused contract test.
