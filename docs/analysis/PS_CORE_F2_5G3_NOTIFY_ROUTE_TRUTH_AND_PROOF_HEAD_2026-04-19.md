# PS_CORE_F2_5G3_NOTIFY_ROUTE_TRUTH_AND_PROOF_HEAD_2026-04-19

**Stand:** 2026-04-19 17:04 Europe/Berlin  
**Owner:** PilotClaw  
**Status:** READY AFTER `HA-559`

## Intent
Re-check the held `F2.5-G3 / Solar-Surplus HA-Notification` head against fresh repo truth so PilotClaw does not resume on an invented second route seam.

## Fresh seam truth
`F2.5-G3` is not a fresh `POST /api/v1/energy/solar-surplus/trigger` route-add.

The active Core repo already carries:
- `POST /api/v1/energy/solar-surplus/notify`
- owner: `energy_forecast_bp`
- focused contract file: `tests/test_solar_surplus_notify_contract.py`
- landing commit: `e544bceb` (`feat(core): F2.5-G3 — POST /solar-surplus/notify HA notification trigger`)

## Exact next pull after `HA-559`
Resume `F2.5-G3` only as one bounded proof-closeout slice:
- primary touch: `tests/test_solar_surplus_notify_contract.py`
- optional minimal adjacent touch: `addons/pilotsuite/app/copilot_core/api/v1/energy_forecast.py` only if the focused proof ring exposes a truthful route-side defect
- do **not** open a second `/trigger` route family
- do **not** widen into notification preferences, scheduler/device management, or broader HA orchestration

## Why this is the right held head
Fresh repo truth already proves the notify seam exists, so the remaining honest work is to close the focused proof ring cleanly, not to add a second near-duplicate route.

## Proof status right now
A fresh focused pytest run is currently red before app bootstrap:
- `tests/test_solar_surplus_notify_contract.py` tries to monkeypatch `copilot_core.api.v1.energy_forecast._SURPLUS_LAST_TRIGGERED_MS`
- that happens before the test file inserts the add-on app path into `sys.path`
- result: import-time failure on `copilot_core.api.v1.energy_forecast`, before the route contract itself is exercised

## Locked stop line
Park outside the first resume slice:
- new `/trigger` route work
- route renames or second alias surfaces
- widget/dashboard work
- optimizer rewrites
- broad HA notification orchestration expansion

## Proof ring for the next pull
- focused pytest on `tests/test_solar_surplus_notify_contract.py`
- optional focused py_compile only on touched files
- tasklog checkpoint naming the next exact Core pull after proof
