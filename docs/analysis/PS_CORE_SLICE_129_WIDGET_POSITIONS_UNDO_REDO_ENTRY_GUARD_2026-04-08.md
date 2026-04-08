# PS Core Slice 129 — `widget_positions` `undo`-/`redo`-Legacy-Entry-Guard

## Stand
- Nach Slice 128 blieb im `widget_positions`-Runtime-Scope noch eine kleine Lücke auf den bestehenden `undo`-/`redo`-Pfaden offen.
- `POST /api/v1/widgets/positions/<widget_id>/undo` und `POST /api/v1/widgets/positions/<widget_id>/redo` griffen den obersten Stack-Eintrag bisher ungeprüft direkt an.
- Bereits gespeicherte shape-falsche `history`- oder `redo_stack`-Einträge konnten dadurch weiter in `KeyError`-/`TypeError`-Wahrheit kippen, obwohl Slice 128 neue fehlerhafte Write-Payloads bereits geschlossen hatte.
- Auf Rekonsolidierungs-Priorität wurde deshalb nur der kleinste explizite Runtime-Entry-Guard im bestehenden `undo`-/`redo`-Zugriff gelandet, ohne neue Surface oder zusätzliche Store-Logik einzuführen.

## Gelandete Artefakte
- `pilotsuite_core/rootfs/usr/src/app/dashboard/api/v1/widget_positions.py`
- `tests/test_widget_positions_contract.py`
- `docs/analysis/PS_CORE_SLICE_129_WIDGET_POSITIONS_UNDO_REDO_ENTRY_GUARD_2026-04-08.md`

## Gelandeter Scope
- `POST /api/v1/widgets/positions/<widget_id>/undo` validiert den obersten `history`-Eintrag jetzt vor dem Pop über denselben minimalen Entry-Shape-Guard wie der Write-Pfad.
- `POST /api/v1/widgets/positions/<widget_id>/redo` behandelt den obersten `redo_stack`-Eintrag analog kontrolliert, statt ungeprüft auf `x`/`y` zuzugreifen.
- shape-falsche Legacy-/Persistenz-Top-Entries laufen damit kontrolliert in die bestehende `404 No history available`- bzw. `404 No redo available`-Wahrheit statt in Python-Fehler.
- Persistenzform, Event-Surface und übrige Runtime-Logik bleiben bewusst unverändert; der Slice härtet nur den kleinsten Zugriff auf bereits gespeicherte Stack-Einträge.

## Test-Evidence
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_widget_positions_contract.py tests/test_contract_inventory_check.py tests/test_public_api_docs_alignment.py tests/test_system_contract.py` → **21 passed**
- `/config/clawd/.venv_smoke_gate/bin/python scripts/contract_inventory_check.py --repo . --light` → **OK**
- `/config/clawd/.venv_smoke_gate/bin/python scripts/contract_inventory_check.py --repo .` → **OK**

## Nächster exakter Task
- Slice 130 — `POST /api/v1/widgets/positions/<widget_id>/history` auf den kleinsten expliziten Legacy-/Persistenz-Current-Position-Guard auditieren, damit shape-falsche bereits gespeicherte Widget-Einträge nicht weiter in `KeyError`-Wahrheit kippen, ohne neue Surface oder zusätzliche Store-Logik einzuführen.
