# PS Core — VFM-012 Slice 012-A solar surplus policy kernel

**Date:** 2026-04-17  
**Owner:** PilotClaw  
**Status:** done

## Goal

Open the prepared VFM-012 execution chain with a recommendation-first policy kernel that stays pure Core logic, accepts deterministic forecast slots plus shiftable candidates, and produces stable recommendation objects without any Home Assistant runtime dependency.

## Files touched

- `addons/pilotsuite/app/copilot_core/energy/solar_surplus_optimizer.py`
- `addons/pilotsuite/app/copilot_core/energy/__init__.py`
- `tests/test_solar_surplus_optimizer.py`

## What landed

- new pure optimizer module with explicit dataclasses for:
  - `SolarSurplusSlot`
  - `SolarSurplusCandidate`
  - `SolarSurplusAction`
  - `SolarSurplusSummary`
- deterministic `SolarSurplusOptimizer.recommend(...)` policy kernel that:
  - filters feasible surplus windows against candidate start bounds
  - preserves recommendation-first behavior (`schedule_now`, `schedule_at`, `delay`, `do_not_shift`)
  - computes stable expected self-consumption gain, savings, and grid-relief metrics
  - emits aggregate summary data for the recommendation batch
- package exports added in `energy/__init__.py`
- focused deterministic tests proving:
  - fixed input fixtures produce stable recommendation outputs
  - immediate best-slot windows classify as `schedule_now`
  - the optimizer module stays runtime-pure and does not import Home Assistant surfaces

## Why this removes the next blocker

Before this slice, VFM-012 existed only as a plan. The Core lane had no canonical optimizer kernel to build the later adapter/API/reporting slices on top of.

Now there is a concrete, test-backed surplus recommendation core with a stable data model and scoring path, so Slice 012-B can focus on forecast/candidate adapters instead of rediscovering policy structure.

## Verification

- `python3 -m py_compile addons/pilotsuite/app/copilot_core/energy/solar_surplus_optimizer.py tests/test_solar_surplus_optimizer.py` -> success
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_solar_surplus_optimizer.py` -> `3 passed in 0.06s`

## Next single step

Land **VFM-012 Slice 012-B** by wiring forecast-slot and device-candidate adapters from the existing energy surfaces into `solar_surplus_optimizer.py`, with safe missing-field handling and horizon alignment tests.
