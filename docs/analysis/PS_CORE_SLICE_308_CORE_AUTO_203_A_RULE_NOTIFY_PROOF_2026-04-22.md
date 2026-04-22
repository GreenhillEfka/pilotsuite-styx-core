# PS CORE SLICE 308 — CORE-AUTO-203-A rule-to-notification proof (2026-04-22)

## Scope
Bounded `CORE-AUTO-203-A` proof landing on the existing rule/notification seam only: `Zone/Habitus state -> Core rule decision -> notification`.

## Landed
- kept scope on the already-present Core automation seam in `autonomy/rule_engine.py` plus the dedicated proof ring `tests/test_core_auto_203_a_contract.py`
- tightened the proof ring from matcher-only coverage to one executed notification path on the same seam
- proved a zone alert context (`zone_mood=alert`, `zone_id=wohnzimmer`) executes through `RuleExecutor` and interpolates the existing notification message `Zone alert in wohnzimmer`
- proved the same run updates the existing rule trigger counter and execution log on the same Core seam

## Verification
- `python3 -m py_compile tests/test_core_auto_203_a_contract.py`
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_core_auto_203_a_contract.py` → `9 passed in 0.12s`

## Result
`CORE-AUTO-203-A` is now file-backed as one honest bounded proof slice on fresh repo truth: zone/habitus context matches a Core rule, the existing execution seam sends the notification payload, and the run is visible in rule-execution state.

## Next exact pull
Do one bounded fresh-truth naming slice only for the first post-`CORE-AUTO-203-A` follow-on on the same `CORE-AUTO-203` family, without widening into dashboard or MQTT work by assumption.
