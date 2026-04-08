# PS Core Slice 132 — `widget_positions` `undo`-/`redo`-Current-Position-Guard

## Stand
- Nach Slice 131 blieb im `widget_positions`-Runtime-Scope noch eine kleine Lücke auf den bestehenden `undo`-/`redo`-Pfaden offen.
- `POST /api/v1/widgets/positions/<widget_id>/undo` und `POST /api/v1/widgets/positions/<widget_id>/redo` griffen die aktuell persistierte Widget-Position beim Stack-Shift bisher ungeprüft direkt über `current["x"]` und `current["y"]` an.
- Bereits gespeicherte shape-falsche Legacy-/Persistenz-Current-Entries konnten dadurch weiter in `KeyError`-Wahrheit kippen, obwohl History-, Redo- und `/history`-Zugriffe bereits enger gehärtet sind.
- Auf Rekonsolidierungs-Priorität wurde deshalb nur der kleinste explizite Current-Position-Guard im bestehenden `undo`-/`redo`-Zugriff gelandet, ohne neue Surface oder zusätzliche Store-Logik einzuführen.

## Gelandete Artefakte
- `pilotsuite_core/rootfs/usr/src/app/dashboard/api/v1/widget_positions.py`
- `tests/test_widget_positions_contract.py`
- `docs/analysis/PS_CORE_SLICE_132_WIDGET_POSITIONS_UNDO_REDO_CURRENT_POSITION_GUARD_2026-04-08.md`

## Gelandeter Scope
- `POST /api/v1/widgets/positions/<widget_id>/undo` validiert die aktuell gespeicherte Widget-Position jetzt vor History-Pop und Redo-Append über denselben minimalen Positions-Shape-Guard wie die übrigen Runtime-Zugriffe.
- `POST /api/v1/widgets/positions/<widget_id>/redo` behandelt denselben Legacy-Fall analog vor Redo-Pop und History-Append, statt ungeprüft auf `x`/`y` der aktuellen Persistenzwahrheit zuzugreifen.
- shape-falsche Legacy-/Persistenz-Current-Entries laufen damit kontrolliert in die bestehende `404 Widget position not found`-Wahrheit statt in Python-`KeyError`.
- fehlerhafte Persistenz-Entries bleiben bewusst unverändert liegen; der Slice härtet nur den kleinsten Runtime-Zugriff beim Stack-Shift.

## Test-Evidence
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_widget_positions_contract.py tests/test_contract_inventory_check.py tests/test_public_api_docs_alignment.py tests/test_system_contract.py` → **25 passed**
- `/config/clawd/.venv_smoke_gate/bin/python scripts/contract_inventory_check.py --repo . --light` → **OK**
- `/config/clawd/.venv_smoke_gate/bin/python scripts/contract_inventory_check.py --repo .` → **OK**

## Nächster exakter Task
- Slice 133 — `POST /api/v1/widgets/positions/<widget_id>/undo` und `POST /api/v1/widgets/positions/<widget_id>/redo` auf den kleinsten expliziten Legacy-/Persistenz-Ziel-Container-Guard auditieren, damit shape-falsche bereits gespeicherte `redo_stack`-Container auf `/undo` und `history`-Container auf `/redo` nicht still in leere Listen repariert werden, ohne neue Surface oder zusätzliche Store-Logik einzuführen.
