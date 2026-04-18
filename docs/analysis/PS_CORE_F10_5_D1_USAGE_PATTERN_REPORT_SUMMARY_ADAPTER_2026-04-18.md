# PS Core — F10.5-D1 usage pattern report summary adapter

**Date:** 2026-04-18 Europe/Berlin  
**Branch:** `pilotclaw/core-restore-runtime`  
**Status:** ✅ DONE

## Was

Landed the first bounded backend slice for VFM-014 usage pattern reporting:

- a summary-friendly accessor on `automation/pattern_learner.py`
- a thin D1 report builder on `energy/report_generator.py`

This keeps the slice aggregate-first and JSON-ready without widening into trends, recommendations, exports, or dashboard wiring.

## Why

The F10.5 design truth was already file-backed, but Core still lacked one real executable adapter that turns learned patterns into a stable report payload. Without D1, frontend or API work would have needed to scrape internal pattern objects ad hoc.

## Change

### `addons/pilotsuite/app/copilot_core/automation/pattern_learner.py`
- added `get_pattern_summaries(...)` as one bounded summary accessor
- returns only summary-safe fields:
  - `pattern_id`
  - `pattern_type`
  - `category`
  - `entity_id`
  - `action`
  - `zone`
  - `confidence`
  - `occurrence_count`
  - `last_occurrence`
  - `hour_of_day`
  - `day_of_week`
  - bounded impact hints from metadata when present
- keeps zone extraction truthful by reading explicit metadata/context hints only, otherwise returns `null`
- keeps category mapping bounded to the D1 report vocabulary (`energy`, `presence`, `media`, `climate`, `automation`)

### `addons/pilotsuite/app/copilot_core/energy/report_generator.py`
- added `generate_usage_pattern_summary(...)`
- consumes the new learner summaries instead of raw internal pattern objects
- emits the bounded D1 payload shape:
  - `status`
  - `window`
  - `patterns`
  - `impact`
- keeps `trend="stable"` for D1 rather than overclaiming drift analysis before D2
- reuses the existing energy pricing context for cost estimation fallback when only kWh impact is available

## Scope guard

This slice does **not** implement:
- window comparison / drift analysis
- recommendation generation
- export serialization
- dashboard hookup
- public API endpoint wiring

Those remain follow-on work.

## Verification

- `python3 -m py_compile addons/pilotsuite/app/copilot_core/energy/report_generator.py addons/pilotsuite/app/copilot_core/automation/pattern_learner.py tests/test_usage_pattern_report_generator.py` → success
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_usage_pattern_report_generator.py` → green

## Files touched

- `addons/pilotsuite/app/copilot_core/automation/pattern_learner.py`
- `addons/pilotsuite/app/copilot_core/energy/report_generator.py`
- `tests/test_usage_pattern_report_generator.py`
- `docs/analysis/PS_CORE_F10_5_D1_USAGE_PATTERN_REPORT_SUMMARY_ADAPTER_2026-04-18.md`

## Blocker removed

F10.5 is no longer only design truth. Core now has one bounded, deterministic backend adapter that turns learned usage patterns into a report-ready summary payload.

## Next single step

`CORE-RESEARCH-002 / F10.5-D2` — compare two bounded windows on top of the D1 shape and add explicit trend/drift reporting without widening into recommendation or export work.
