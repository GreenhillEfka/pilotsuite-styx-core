# PS_CORE_F2_5G3_TRIGGER_ROUTE_FRAMING_2026-04-19

**Stand:** 2026-04-19 14:49 Europe/Berlin  
**Owner:** PilotClaw  
**Status:** READY AFTER `HA-559`

## Intent
Sharpen the held Core resume point `F2.5-G3 / Solar-Surplus HA-Notification` to one exact first pull that fits the serial no-drift rule.

## Exact first slice
Start `F2.5-G3` in:
- `addons/pilotsuite/app/copilot_core/api/v1/energy_forecast.py`

Land one bounded route-add slice only:
- `POST /api/v1/energy/solar-surplus/trigger`
- owner: `energy_forecast_bp`
- auth/envelope: same adjacent seam as existing solar-surplus routes (`@require_token`, `jsonify({"ok": True, ...})`)

## Why this is the right owner
Fresh repo truth already shows the existing solar-surplus HTTP seam in `energy_forecast.py`:
- `POST /solar-surplus/recommendations`
- `GET /solar-surplus/status`

So the trigger entrypoint should start on the same blueprint instead of opening a second energy API owner, a new blueprint, or an automation-first surface.

## Locked touch budget for the first pull
Default first-touch budget:
- `addons/pilotsuite/app/copilot_core/api/v1/energy_forecast.py`
- `tests/test_energy_solar_surplus_route_contract.py`
- this slice note

Only widen beyond that if a minimal thin HA-notify handoff is strictly required to make the route truthful.

## Locked response contract for the first pull
Keep the first trigger route on the already-shipped summary shape from `GET /api/v1/energy/solar-surplus/status`:
- return one additive `surplus` block only, using the same summary fields already exposed by the zero-input status seam
- allow one small trigger acknowledgement field next to it (`triggered` or equivalent thin ack)
- do **not** return the full recommendations batch shape (`summary`, `recommendations`, `slots`, `candidates`) from `POST /solar-surplus/recommendations`

This keeps the first `POST /solar-surplus/trigger` pull on one thin status-plus-ack contract instead of reopening the heavy optimizer payload family.

## Explicit stop line
Park outside the first slice:
- new blueprint or second route family
- widget/dashboard work
- optimizer rewrite
- broad automations/scheduler expansion
- notification preference/device-management expansion
- full recommendation-batch response reuse on the trigger route

If the route cannot stay thin and immediately demands wider notification orchestration, stop after checkpointing the exact next pull.

## Proof ring
- focused py_compile on the touched route/test seam
- focused pytest on `tests/test_energy_solar_surplus_route_contract.py`
- tasklog checkpoint naming the exact next pull after proof
