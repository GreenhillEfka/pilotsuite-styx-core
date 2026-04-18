# PS_CORE_P3_003_TOPOLOGY_INSPECTABLE_CANVAS_2026-04-18

## Task
P3-003 follow-through after topology-aware delta anchors: make the shipped `/styx` brain canvas inspectable without opening a second graph page or transport.

## Why this slice
The live graph overlay was already topology-aware, but the dashboard still behaved like a passive animation surface. Andreas asked for visible product progress, so the next bounded step was to let the existing canvas expose real graph detail directly.

## Landed scope
- Added one inline `brain-focus-panel` below the existing canvas in `addons/pilotsuite/app/copilot_core/templates/styx_dashboard.html`
- Bound hover and click inspection to the same bounded `/api/v1/graph/state` snapshot already used for topology-aware anchors
- Highlighted focused nodes plus connected edges directly inside the existing canvas backdrop
- Reused current graph node metadata (`label`, `kind`, `score`) and derived neighbor/degree information locally, with no new endpoint or backend write path
- Extended `tests/test_styx_dashboard_live_contract.py` to lock the new inspectability contract

## Verification
- `node --check tmp_styx_dashboard_check.js`
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_styx_dashboard_live_contract.py tests/test_styx_brain_graph_live_bridge_contract.py`
- Result: `9 passed`

## Result
The shipped `/styx` surface now supports bounded graph inspection in place: operators can hover a node to inspect it, click to pin it, and see connected topology on the same live canvas while realtime delta overlays keep running.

## Next exact pull
`CORE-STRUCT-101 / Runtime-API haerten`
