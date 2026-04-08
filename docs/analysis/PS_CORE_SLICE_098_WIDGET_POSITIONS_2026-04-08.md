# PS Core Slice 98 — `dashboard.api.v1.widget_positions`

## Stand
- Worktree `pilotsuite-styx-core-current` hatte keinen nutzbaren `TASKBOARD.md` und keine laufende `dashboard.api.v1.widget_positions`-Runtime mehr.
- Der aktuelle `v20.0.0`-Baum enthielt nur ein minimales Flask-Stub ohne Widget-Positions-API.
- Für die aktive Inventar-/Contract-Lücke wurde der kleinste echte Slice direkt im Runtime-Baum wieder hergestellt.

## Gelandete Artefakte
- `pilotsuite_core/rootfs/usr/src/app/dashboard/api/v1/widget_positions.py`
- `pilotsuite_core/rootfs/usr/src/app/main.py`
- `tests/test_widget_positions_contract.py`

## Gelandeter Scope
- REST-Surface für Widget-Positionen unter `/api/v1/widgets/positions`
- CRUD, Bulk-Save, History, Undo, Redo, Reset
- Dateibasierte Persistenz über `dashboard/data/widget_positions.json`
- Event-Hooks für `widget_position_update`, `widget_position_deleted`, `widget_positions_reset`
- Fokussierte Contract-Tests für Happy Path, Validation und Not-Found-Pfade

## Test-Evidence
- `pytest -q tests/test_widget_positions_contract.py`

## Nächster exakter Task
- Slice 99: `widget_positions` in die aktuelle Contract-/OpenAPI-Inventur des `v20`-Baums einhängen, damit der Guard nicht nur Runtime-, sondern auch Inventar-Wahrheit abdeckt.
