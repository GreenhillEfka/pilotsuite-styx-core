# PS_CORE_F10_5_D4 Usage Pattern Report Export

Date: 2026-04-18
Owner: PilotClaw
Task: `CORE-RESEARCH-004 / F10.5-D4`

## Scope
Expose the already-landed D1/D2/D3 usage-pattern report stack through one bounded Core API surface without rebuilding report semantics.

## Landed artifacts
- `addons/pilotsuite/app/copilot_core/energy/report_generator.py`
- `addons/pilotsuite/app/copilot_core/api/v1/energy_forecast.py`
- `tests/test_usage_pattern_report_export_contract.py`

## What changed
- added `export_usage_pattern_summary(...)` as a thin export-ready wrapper over the existing canonical `generate_usage_pattern_summary(...)`
- added `GET /api/v1/energy/reports/usage-patterns/export`
- route accepts only bounded window inputs plus `min_confidence`
- route returns the canonical D1/D2/D3 payload shape directly: `status`, `window`, `comparison_window`, `patterns`, `impact`, `drift`, `recommendations`

## Why this shape
- keeps D1/D2/D3 as the single truth source
- avoids a second analytics pipeline
- gives frontend/backend consumers one stable token-protected read seam
- stays inside D4 scope, no dashboard binding, no auto-apply, no new recommendation logic

## Verification
- `python3 -m py_compile addons/pilotsuite/app/copilot_core/energy/report_generator.py addons/pilotsuite/app/copilot_core/api/v1/energy_forecast.py tests/test_usage_pattern_report_export_contract.py`
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_usage_pattern_report_export_contract.py`

## Next exact pull
`CORE-FRONTEND-BACKEND-002 / F10.5 usage-pattern consumer binding`
