# PS CORE SLICE 310 — CORE-AUTO-203-B notification delivery contract

## Summary
`CORE-AUTO-203-B` landed on the existing proactive notification-delivery seam only.

## Scope held
- file: `addons/pilotsuite/app/copilot_core/proactive_engine.py`
- proof ring: `tests/test_core_auto_203_b_notification_delivery_contract.py`
- no widening into dashboard, MQTT, `ha_call`, or broader automation flows

## Landing
- kept the existing no-token failure path explicit: `{"ok": false, "error": "No SUPERVISOR_TOKEN"}`
- locked the canonical bearer-auth POST to `/services/notify/persistent_notification`
- made delivery use runtime `SUPERVISOR_API` env truth inside `deliver_suggestion(...)` instead of only import-time state
- prevented false-positive success on failed HTTP responses by calling `raise_for_status()` before returning `{"ok": true, "method": "notification"}`
- kept request failures explicit as `{"ok": false, "error": ...}` on the same seam

## Verification
- `python3 -m py_compile addons/pilotsuite/app/copilot_core/proactive_engine.py tests/test_core_auto_203_b_notification_delivery_contract.py`
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_core_auto_203_b_notification_delivery_contract.py`
- result: `4 passed`

## Operative effect
The existing `Zone/Habitus state -> Core decision -> notification` family is now clean through the dedicated delivery seam, so `CORE-AUTO-203` no longer stops at rule proof only.

## Next exact step
Shared serial order now hands the immediate follow-on to `HA-E2E-303`. PilotClaw should stay parked behind that HA-owned roundtrip step; when Core resumes, take one bounded fresh-truth naming slice only for the first post-`CORE-AUTO-203` `CORE-HARDEN-204` pull.
