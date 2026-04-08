# PS Core Slice 134 — `widget_positions` `/history` `redo_stack`-Ziel-Container-Guard

## Stand
- Nach Slice 133 blieb im `widget_positions`-Runtime-Scope noch eine kleine Lücke auf `POST /api/v1/widgets/positions/<widget_id>/history` offen.
- Der Pfad reparierte einen bereits persistierten shape-falschen `redo_stack`-Container bisher still zu `[]`, bevor der neue History-Snapshot geschrieben wurde.
- Auf Rekonsolidierungs-Priorität wurde deshalb nur der kleinste explizite Ziel-Container-Guard im bestehenden `/history`-Zugriff gelandet, ohne neue Surface oder zusätzliche Store-Logik einzuführen.

## Gelandete Artefakte
- `pilotsuite_core/rootfs/usr/src/app/dashboard/api/v1/widget_positions.py`
- `tests/test_widget_positions_contract.py`
- `docs/analysis/PS_CORE_SLICE_134_WIDGET_POSITIONS_HISTORY_REDO_TARGET_CONTAINER_GUARD_2026-04-08.md`

## Gelandeter Scope
- `POST /api/v1/widgets/positions/<widget_id>/history` validiert den Persistenz-Ziel-Container `redo_stack` jetzt explizit vor History-Append und Reset.
- shape-falsche Legacy-/Persistenz-`redo_stack`-Container laufen damit kontrolliert in die bestehende `404 Widget position not found`-Wahrheit statt still zu leeren Listen repariert zu werden.
- fehlende `redo_stack`-Container bleiben weiter minimal landingfähig; der Slice härtet nur den kleinsten Persistenz-Drift-Fall auf dem bestehenden `/history`-Pfad.
- fehlerhafte Persistenz-Container bleiben bewusst unverändert liegen; der Slice erweitert weder Store-Reparatur noch öffentliche Surface.

## Test-Evidence
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_widget_positions_contract.py tests/test_contract_inventory_check.py tests/test_public_api_docs_alignment.py tests/test_system_contract.py` → **28 passed**
- `/config/clawd/.venv_smoke_gate/bin/python scripts/contract_inventory_check.py --repo . --light` → **OK**
- `/config/clawd/.venv_smoke_gate/bin/python scripts/contract_inventory_check.py --repo .` → **OK**

## Nächster exakter Task
- Slice 135 — `POST /api/v1/widgets/positions` und `POST /api/v1/widgets/positions/bulk` auf den kleinsten expliziten Legacy-/Persistenz-`redo_stack`-Ziel-Container-Guard auditieren, damit shape-falsche bereits gespeicherte `redo_stack`-Container auf Overwrite-Write-Pfaden nicht still in leere Listen repariert werden, ohne neue Surface oder zusätzliche Store-Logik einzuführen.
