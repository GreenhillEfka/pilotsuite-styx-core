# PS_CORE_F2_5A_SOLAR_SURPLUS_FOLLOW_ON_FRAMING_2026-04-19

## Type
**Read-only framing document** — no build, no code changes.
Used to prepare the F2.5-A pull before HA-559 lands.

## Status
READY FOR PULL — gap clearly bounded, and fresh repo truth confirms the `/api/v1/energy/report` route is still missing.

---

## What F2.5 Is

F2.5 = **Solar surplus utilization follow-on surface**
From Vision Matrix: "F2.5 — Solar surplus utilization — Planned v1.1.0"

This is the consumer-facing counterpart to VFM-012 / 012-E which landed the
`/api/v1/automations/generate` caller surface and the `solar_surplus_batches`
integration into the automations suggestion engine.

---

## What Already Exists

### Energy API surface
- `POST /api/v1/energy/solar-surplus/recommendations` — in `energy_forecast.py:746`
- `SolarSurplusOptimizer` kernel — 618 lines in `energy/solar_surplus_optimizer.py`
- `/api/v1/automations/generate` with `solar_surplus_batches` body — in `automations/api.py`

### VFM-012 / 012-E landed
- `addons/pilotsuite/app/copilot_core/automations/api.py` — caller integration ✅
- `addons/pilotsuite/app/copilot_core/automations/suggestion_engine.py` — engine wired ✅
- `addons/pilotsuite/app/copilot_core/energy/report_generator.py` — report layer ✅
- Contract test: `test_automations_solar_surplus_generate_contract.py` ✅

---

## Remaining F2.5 Family Backlog

The gap between VFM-012 (automations caller) and the full shipped F2.5 feature
still spans three follow-on surfaces, but only the first one belongs to the
next exact pull.

### G1 — Energy report consumer endpoint
`/api/v1/energy/report` should expose the solar surplus decision in a
user-facing format. Currently `report_generator.py` produces structured data
but no public API endpoint consumes it.

**Exact gap:** No `/api/v1/energy/report` endpoint that returns solar surplus
summary for the current billing period.

### G2 — Solar surplus dashboard widget data
The HA dashboard needs a widget that shows current solar surplus status.
Currently no API surface delivers this to the Lovelace card system.

**Exact gap:** No `/api/v1/widgets/energy/solar-surplus` endpoint.

### G3 — HA notification on surplus event
When surplus exceeds threshold, notify the user via HA notification system.
VFM-012 computes recommendations but nothing triggers a HA notification.

**Exact gap:** No surplus event → HA notification wiring.

---

## Bounded F2.5-A Scope

**Locked first F2.5-A slice:**

> Add one bounded `GET /api/v1/energy/report` route in `energy_forecast.py` so
> it returns the current billing-period solar surplus summary through the
> existing report-generator truth, reusing the current solar-surplus
> optimizer/report truth instead of opening a second consumer route, with one
> focused contract test proving the report payload now carries the additive
> `solar_surplus` block.

### Fresh route-presence proof
- Fresh repo check on `energy_forecast.py` shows no live `/api/v1/energy/report`
  route yet, so `F2.5-A` is a bounded route-add slice, not an edit to an
  already-shipped report handler.
- Keep that distinction explicit so the next pull does not widen into a report
  family rewrite or a second consumer surface.

### Explicit stop line for this pull
- **In scope:** G1 only, on `/api/v1/energy/report`
- **Out of scope:** G2 widget endpoint, G3 HA notification wiring, any new HA
  card plumbing, and any second API surface beyond the report route
- **If implementation starts widening:** stop after landing/logging the exact
  report-route slice and leave G2/G3 parked as later F2.5 follow-ons

That is one bounded slice, verifiable, no new HA integration required yet.

## Route contract guard for F2.5-A

- Keep `F2.5-A` additive to the existing energy route family through exactly one
  new `/api/v1/energy/report` surface only, not as a widget, notification, or
  parallel consumer route.
- Reuse the existing solar-surplus optimizer/report truth; do not add new
  persistence, scheduler work, HA callbacks, or a second optimization path.
- If the current billing-period surplus view is missing or partial, keep the
  route truthful on `/api/v1/energy/report` instead of widening into a
  parameter matrix or background recomputation slice.
- Proof for this pull stays limited to the existing route-contract seam in
  `tests/test_energy_solar_surplus_route_contract.py`; widget or notification
  proof belongs to later `F2.5` follow-ons only.

## Payload-shape guard for F2.5-A

- Land the surplus data as one additive `solar_surplus` block on the single new
  `/api/v1/energy/report` payload, not as a new top-level response family,
  export variant, or sibling report endpoint.
- Default this first pull to the current billing period only; do not widen into
  date-range, comparison, historical-window, or forecast query parameters.
- If the existing report serializer needs cleanup first, stop at the smallest
  truthful additive block and leave response-family refactors parked behind
  `F2.5-A` instead of widening the pull.

## Serializer-ownership guard for F2.5-A

- Keep the existing report assembly path as the single owner of the additive
  `solar_surplus` block.
- Do not add a new report builder, a second optimizer pass, or a route-local
  recomputation branch just to populate the first `solar_surplus` payload.
- If the current report path exposes only partial billing-period surplus truth,
  return that bounded truth inside the additive block and park richer
  aggregation or serializer refactors behind later `F2.5` follow-ons.

## Touch-budget guard for F2.5-A

- Default implementation budget stays on the prepared route seam only:
  `energy_forecast.py`, its focused route-contract test, and the slice note.
- Treat `report_generator.py` as an existing upstream owner to read through, not
  as a second active build front; only touch it if the additive block cannot be
  surfaced truthfully without one minimal serializer hookup.
- Keep `automations/api.py`, `suggestion_engine.py`, optimizer internals, HA
  files, widget files, and notification wiring out of the first pull.
- If that touch budget no longer holds, stop and log the exact next pull instead
  of widening `F2.5-A` inside the same run.

## Owner-and-period guard for F2.5-A

- Use `EnergyReportGenerator.generate_report(report_type="monthly")` as the
  default current-billing-period owner for the first route slice, because that
  existing report path already emits `period_start`, `period_end`,
  `consumption`, and `costs` on one serialized report object.
- Build the first additive `solar_surplus` block from the already-generated
  report fields that carry bounded surplus truth now, especially
  `consumption.self_consumed_kwh`, `consumption.fed_in_kwh`,
  `consumption.self_consumption_ratio_pct`, `costs.solar_savings_eur`, and
  `costs.feed_in_revenue_eur`.
- Do not widen the first pull into request-time period switching, daily/weekly
  selector plumbing, custom date ranges, or a second report assembler just to
  ship the current billing-period route.
- If richer billing semantics are still needed after the monthly route lands,
  park that as the exact next pull instead of widening `F2.5-A`.

---

## Files to Touch (F2.5-A)

| File | Change |
|------|--------|
| `addons/pilotsuite/app/copilot_core/api/v1/energy_forecast.py` | Add `/report` endpoint |
| `tests/test_energy_solar_surplus_route_contract.py` | Add contract test |
| `docs/analysis/PS_CORE_F2_5A_ENERGY_REPORT_SOLAR_SURPLUS_2026-04-19.md` | Slice doc |

---

## Verification Target (F2.5-A)

```
python3 -m py_compile addons/pilotsuite/app/copilot_core/api/v1/energy_forecast.py
/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_energy_solar_surplus_route_contract.py
```

---

## Serial Queue Position

```
1. HA-559 [HomeClaw] ← ACTIVE, waiting
2. F2.5-A [PilotClaw] ← PRE-PULLED, ready to go after HA-559
3. VFM-003 [PilotClaw]
4. F10.5 [PilotClaw]
```

---

## Decision Needed
None. The serial trigger is already locked.
After `HA-559`, PilotClaw pulls `F2.5-A` immediately without a new approval gate.
