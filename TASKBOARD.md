# TASKBOARD — pilotsuite-styx-core-current

## Aktiver Stand
- [x] Slice 128 `widget_positions` `history`-/`redo_stack`-Entry-Shape-Guard gezogen und gelandet.

## Artefakte
- `pilotsuite_core/rootfs/usr/src/app/dashboard/api/v1/widget_positions.py`
- `tests/test_widget_positions_contract.py`
- `docs/analysis/PS_CORE_SLICE_128_WIDGET_POSITIONS_HISTORY_REDO_ENTRY_SHAPE_GUARD_2026-04-08.md`
- `TASKBOARD.md`
- `/config/clawd/agents/pilotclaw/TASKLOG.md`

## Teststatus
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_widget_positions_contract.py tests/test_contract_inventory_check.py tests/test_public_api_docs_alignment.py tests/test_system_contract.py` → **19 passed**
- `/config/clawd/.venv_smoke_gate/bin/python scripts/contract_inventory_check.py --repo . --light` → **OK**
- `/config/clawd/.venv_smoke_gate/bin/python scripts/contract_inventory_check.py --repo .` → **OK**

## Nächster exakter Task
- Slice 129 — `POST /api/v1/widgets/positions/<widget_id>/undo` und `POST /api/v1/widgets/positions/<widget_id>/redo` auf den kleinsten expliziten Legacy-/Persistenz-Entry-Guard auditieren, damit bereits gespeicherte shape-falsche `history`-/`redo_stack`-Einträge nicht weiter in `KeyError`-/`TypeError`-Wahrheit kippen, ohne neue Surface oder zusätzliche Store-Logik einzuführen.
