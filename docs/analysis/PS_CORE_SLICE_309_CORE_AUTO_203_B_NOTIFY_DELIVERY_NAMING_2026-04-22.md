# PS CORE SLICE 309 — CORE-AUTO-203-B notify-delivery naming

Stand: 2026-04-22 02:24 Europe/Berlin
Owner: PilotClaw
Status: queued exactly

## Task
Take one bounded fresh-truth naming slice only for the first post-`CORE-AUTO-203-A` follow-on on the same `CORE-AUTO-203` family, then stop before widening into dashboard, MQTT, `ha_call`, or a second automation seam by assumption.

## Fresh basis used
1. `/config/clawd/AGENTS.md`
2. `/config/clawd/MEMORY.md`
3. `/config/clawd/team/PILOTSUITE_PROGRESS_LEDGER.md`
4. `/config/clawd/agents/pilotclaw/TASKLOG.md`
5. `/config/clawd/team/PILOTSUITE_48H_TASKPLAN_2026-04-20.md`
6. `/config/clawd/team/worktrees/pilotsuite-styx-core-current/addons/pilotsuite/app/copilot_core/proactive_engine.py`
7. `rg -n "deliver_suggestion|ProactiveContextEngine|persistent_notification|presence_trigger" team/worktrees/pilotsuite-styx-core-current/tests -g '*.py'`

## Fresh truth
- `CORE-AUTO-203-A` already proved the first bounded `Zone/Habitus state -> Core rule decision -> notification` step on the existing rule-engine seam.
- The 48h plan still binds `CORE-AUTO-203` to a real end-to-end automation path on existing productive seams only.
- `RuleExecutor` currently hands notification delivery to `ProactiveContextEngine.deliver_suggestion(..., method="notification")`, so the smallest honest post-`A` follow-on remains the existing delivery seam, not dashboard, MQTT, or a wider action family.
- Fresh test discovery shows no dedicated proof ring yet for that delivery seam.

## Next exact pull pinned
`CORE-AUTO-203-B` — bounded notification-delivery contract on the existing proactive seam only.

### Exact files
- `addons/pilotsuite/app/copilot_core/proactive_engine.py`
- `tests/test_core_auto_203_b_notification_delivery_contract.py`

### Exact proof to land
1. `deliver_suggestion(..., method="notification")` returns `{ok: False, error: "No SUPERVISOR_TOKEN"}` when the supervisor token is absent.
2. With a token present, the same seam issues one POST to `${SUPERVISOR_API}/services/notify/persistent_notification` with Bearer auth and payload `{message, title: "Styx"}`.
3. On successful POST, the seam returns the canonical `{ok: True, method: "notification"}` result.
4. On request failure, the seam returns `{ok: False, error: <exception text>}` without widening into other delivery methods.

## Why this is the right next pull
- stays on the same already-active `CORE-AUTO-203` notification family
- tightens the first real delivery leg behind the now-proved rule decision
- fits inside one cron run with one code seam and one dedicated proof ring
- avoids assumption drift into dashboard, MQTT, HA roundtrip, or broader automation orchestration

## Stop boundary
Do not widen into:
- dashboard consumers
- MQTT delivery
- `ha_call` action execution
- broader automation CRUD or multi-action orchestration

## External routing note
Routine bounded slice update belongs in `topic:13196`.
