# PS Core — F10.5-D3 usage pattern recommendations with bounded explainability

**Date:** 2026-04-18 Europe/Berlin  
**Branch:** `pilotclaw/core-restore-runtime`  
**Status:** ✅ DONE

## Was

Landed the bounded D3 follow-up for VFM-014 usage pattern reporting:

- one conservative recommendation layer on top of the existing D2 summary/trend/drift output
- explicit explainability payloads for every emitted recommendation
- bounded anti-noise gating so the layer stays useful instead of becoming a second analytics firehose

## Why

D2 could now tell Core which patterns were rising, new, stable, or fading, but it still stopped one step before actionable guidance. That left the design's recommendation layer file-backed but not executable.

## Change

### `addons/pilotsuite/app/copilot_core/energy/report_generator.py`
- `generate_usage_pattern_summary(...)` now returns top-level `recommendations`
- added bounded recommendation families:
  - `optimize_rising_usage`
  - `review_new_pattern`
  - `review_fading_pattern`
- every recommendation now carries:
  - `recommendation_id`
  - `title`
  - `reason`
  - `why_now`
  - `expected_benefit`
  - `confidence`
  - `priority`
  - `action_type`
  - `explainability`
- kept the layer conservative:
  - observation-backed patterns only
  - minimum confidence / frequency threshold
  - one per recommendation family + category + zone cooldown slot per report window
  - max three emitted recommendations
- reuses the same D2 pattern/impact context instead of opening a parallel recommendation pipeline

### `tests/test_usage_pattern_report_generator.py`
- extended the contract coverage so D1/D2 report shapes now include the new `recommendations` field
- added a D3 contract proving rising/new/fading recommendation output plus explainability fields
- added a bounded anti-noise proof that only the highest-signal recommendation survives when two same-zone energy patterns compete for the same cooldown slot

## Scope guard

This slice does **not** implement:
- dashboard hookup
- export/report serialization
- public analytics route wiring
- persisted recommendation history
- auto-apply or automation execution

## Verification

- `python3 -m py_compile addons/pilotsuite/app/copilot_core/energy/report_generator.py tests/test_usage_pattern_report_generator.py` → success
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_usage_pattern_report_generator.py` → `5 passed`

## Files touched

- `addons/pilotsuite/app/copilot_core/energy/report_generator.py`
- `tests/test_usage_pattern_report_generator.py`
- `docs/analysis/PS_CORE_F10_5_D3_USAGE_PATTERN_RECOMMENDATIONS_2026-04-18.md`

## Blocker removed

F10.5 no longer stops at descriptive reporting. Core can now turn bounded trend/drift evidence into a small explainable recommendation set without widening into export, dashboard, or automation execution work.

## Next single step

`CORE-RESEARCH-004 / F10.5-D4` — expose this report stack through one bounded export or analytics surface, keeping the already-landed D1/D2/D3 payload as the only source of truth.
