# PS Core — F10.5-D2 usage pattern window trend and drift comparison

**Date:** 2026-04-18 Europe/Berlin  
**Branch:** `pilotclaw/core-restore-runtime`  
**Status:** ✅ DONE

## Was

Landed the bounded D2 follow-up for VFM-014 usage pattern reporting:

- window-aware pattern summaries on `automation/pattern_learner.py`
- equal-length previous-window comparison plus explicit drift reporting on `energy/report_generator.py`

This keeps the work on top of the D1 summary shape without widening into recommendations, exports, or API wiring.

## Why

D1 made usage-pattern reporting executable, but every pattern still reported `trend="stable"` because Core had no truthful window-vs-window comparison. That left the design’s D2 drift layer file-backed but not shipped.

## Change

### `addons/pilotsuite/app/copilot_core/automation/pattern_learner.py`
- now reloads persisted `observations.jsonl` on startup so window comparison can survive restarts
- added bounded observation-to-pattern matching for time-based and weather-based patterns
- added `get_pattern_window_summaries(...)` so callers can ask for window-specific frequency and last-seen metrics instead of lifetime-only counts
- keeps a truthful fallback to pattern-level metadata when observations are unavailable, and marks that source so downstream trend logic does not overclaim

### `addons/pilotsuite/app/copilot_core/energy/report_generator.py`
- `generate_usage_pattern_summary(...)` now compares the requested window against one equal-length previous window
- upgrades pattern items with bounded comparison fields:
  - `previous_frequency`
  - `frequency_delta`
  - computed `trend`
- adds explicit top-level `comparison_window`
- adds explicit top-level `drift` with:
  - bounded summary counts
  - `new_patterns`
  - `fading_patterns`
- keeps drift conservative when data only comes from fallback pattern metadata rather than observed window counts

## Scope guard

This slice does **not** implement:
- recommendation generation
- export/report serialization
- dashboard hookup
- public analytics route wiring
- comfort scoring or user-facing prose generation

## Verification

- `python3 -m py_compile addons/pilotsuite/app/copilot_core/energy/report_generator.py addons/pilotsuite/app/copilot_core/automation/pattern_learner.py tests/test_usage_pattern_report_generator.py` → success
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_usage_pattern_report_generator.py` → `4 passed`

## Files touched

- `addons/pilotsuite/app/copilot_core/automation/pattern_learner.py`
- `addons/pilotsuite/app/copilot_core/energy/report_generator.py`
- `tests/test_usage_pattern_report_generator.py`
- `docs/analysis/PS_CORE_F10_5_D2_USAGE_PATTERN_WINDOW_TREND_DRIFT_2026-04-18.md`

## Blocker removed

F10.5 no longer stops at a static D1 summary. Core can now compare adjacent bounded windows, emit truthful per-pattern trend signals, and surface new/fading drift without opening a second analytics pipeline.

## Next single step

`CORE-RESEARCH-003 / F10.5-D3` — add one bounded recommendation layer with explicit explainability on top of the D2 summary/trend output, still without widening into export or dashboard work.
