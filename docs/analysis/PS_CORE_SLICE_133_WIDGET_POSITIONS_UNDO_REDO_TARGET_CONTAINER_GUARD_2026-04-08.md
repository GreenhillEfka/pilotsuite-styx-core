# PS Core Slice 133 — `widget_positions` `undo`-/`redo`-Ziel-Container-Guard

## Stand
- Nach Slice 132 blieb im `widget_positions`-Runtime-Scope noch eine kleine Lücke auf den bestehenden `undo`-/`redo`-Pfaden offen.
- `POST /api/v1/widgets/positions/<widget_id>/undo` reparierte einen bereits persistierten shape-falschen `redo_stack`-Container bisher still zu `[]`, bevor der Stack-Shift abgeschlossen wurde.
- `POST /api/v1/widgets/positions/<widget_id>/redo` tat dasselbe analog für einen shape-falschen `history`-Container.
- Auf Rekonsolidierungs-Priorität wurde deshalb nur der kleinste explizite Ziel-Container-Guard im bestehenden `undo`-/`redo`-Zugriff gelandet, ohne neue Surface oder zusätzliche Store-Logik einzuführen.

## Gelandete Artefakte
- `pilotsuite_core/rootfs/usr/src/app/dashboard/api/v1/widget_positions.py`
- `tests/test_widget_positions_contract.py`
- `docs/analysis/PS_CORE_SLICE_133_WIDGET_POSITIONS_UNDO_REDO_TARGET_CONTAINER_GUARD_2026-04-08.md`

## Gelandeter Scope
- `POST /api/v1/widgets/positions/<widget_id>/undo` validiert den Persistenz-Ziel-Container `redo_stack` jetzt explizit vor History-Pop und Redo-Append.
- `POST /api/v1/widgets/positions/<widget_id>/redo` validiert den Persistenz-Ziel-Container `history` jetzt explizit vor Redo-Pop und History-Append.
- shape-falsche Legacy-/Persistenz-Ziel-Container laufen damit kontrolliert in die bestehende `404 Widget position not found`-Wahrheit statt still zu leeren Listen repariert zu werden.
- fehlerhafte Persistenz-Container bleiben bewusst unverändert liegen; der Slice härtet nur den kleinsten Runtime-Zugriff beim Stack-Shift.

## Test-Evidence
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_widget_positions_contract.py tests/test_contract_inventory_check.py tests/test_public_api_docs_alignment.py tests/test_system_contract.py` → **27 passed**
- `/config/clawd/.venv_smoke_gate/bin/python scripts/contract_inventory_check.py --repo . --light` → **OK**
- `/config/clawd/.venv_smoke_gate/bin/python scripts/contract_inventory_check.py --repo .` → **OK**

## Nächster exakter Task
- Slice 134 — `POST /api/v1/widgets/positions/<widget_id>/history` auf den kleinsten expliziten Legacy-/Persistenz-`redo_stack`-Ziel-Container-Guard auditieren, damit shape-falsche bereits gespeicherte `redo_stack`-Container auf `/history` nicht still in leere Listen repariert werden, ohne neue Surface oder zusätzliche Store-Logik einzuführen.
