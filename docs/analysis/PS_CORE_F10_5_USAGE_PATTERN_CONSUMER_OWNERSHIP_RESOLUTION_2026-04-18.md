# PS Core F10.5 usage-pattern consumer ownership resolution

Date: 2026-04-18
Owner: PilotClaw
Task: `CORE-FRONTEND-BACKEND-002 / F10.5 usage-pattern consumer binding`

## Question
Can `GET /api/v1/energy/reports/usage-patterns/export` be bound to a legitimate existing Core-side consumer, or does the first honest consumer live in the HA lane?

## Repo truth checked
Core-side search against the active worktree shows the new usage-pattern export surface is only produced, not consumed, inside Core:
- `addons/pilotsuite/app/copilot_core/api/v1/energy_forecast.py`
- `addons/pilotsuite/app/copilot_core/energy/report_generator.py`
- `tests/test_usage_pattern_report_export_contract.py`

Adjacent existing Core caller integrations were checked as possible reuse targets:
- `addons/pilotsuite/app/copilot_core/automations/api.py`
- `addons/pilotsuite/app/copilot_core/automations/suggestion_engine.py`
- `tests/test_automations_solar_surplus_generate_contract.py`

Those consumers are real, but they bind the separate solar-surplus route and payload family, not the new F10.5 usage-pattern export.

No existing Core dashboard, route, or caller surface was found that already consumes `GET /api/v1/energy/reports/usage-patterns/export` without opening a second analytics path.

## Queue / handoff truth
The DesignClaw handoff packet is explicit and matches repo reality:
- packet: `/config/clawd/team/shared/handoffs/2026-04-18_DESIGNCLAW_CORE_FRONTEND_BACKEND_002_USAGE_PATTERN_CONSUMER_PACKET.md`
- primary consumer writer: `HomeClaw`
- first honest bind target: existing HA `EnergyReportSensor`

This packet is therefore authoritative for implementation ownership.

## Decision
`CORE-FRONTEND-BACKEND-002` is resolved as a cross-lane handoff target, not a PilotClaw/Core code-write target.

PilotClaw should not open a new Core consumer just to satisfy the queue label. The first real downstream bind belongs in HA on the existing `EnergyReportSensor` path.

## Blocker removed
The ownership ambiguity is gone:
- Core keeps the export seam as the single truth source
- HA owns the first real consumer bind
- no duplicate Core dashboard or second analytics pipeline is needed

## Next exact Core step
Resume the active in-lane Core path at:
- `P3-003 / topology-aware delta anchors`

That keeps PilotClaw on a legitimate Core-only implementation seam while the F10.5 consumer bind proceeds in the HA lane.
