# PS Core Slice 130 — `widget_positions` `history`-Current-Position-Guard

## Stand
- Nach Slice 129 blieb im `widget_positions`-Runtime-Scope noch eine kleine Lücke auf `POST /api/v1/widgets/positions/<widget_id>/history` offen.
- Der Pfad griff die aktuell persistierte Widget-Position bisher ungeprüft direkt über `current["x"]` und `current["y"]` an.
- Bereits gespeicherte shape-falsche Legacy-/Persistenz-Entries konnten dadurch weiter in `KeyError`-Wahrheit kippen, obwohl neue Write-Payloads und Stack-Zugriffe bereits enger gehärtet sind.
- Auf Rekonsolidierungs-Priorität wurde deshalb nur der kleinste explizite Current-Position-Guard im bestehenden `history`-Pfad gelandet, ohne neue Surface oder zusätzliche Store-Logik einzuführen.

## Gelandete Artefakte
- `pilotsuite_core/rootfs/usr/src/app/dashboard/api/v1/widget_positions.py`
- `tests/test_widget_positions_contract.py`
- `docs/analysis/PS_CORE_SLICE_130_WIDGET_POSITIONS_HISTORY_CURRENT_POSITION_GUARD_2026-04-08.md`

## Gelandeter Scope
- `POST /api/v1/widgets/positions/<widget_id>/history` validiert die aktuell gespeicherte Widget-Position jetzt vor dem History-Append über denselben minimalen Positions-Shape-Guard wie die bestehenden Stack-Zugriffe.
- shape-falsche Legacy-/Persistenz-Entries laufen damit kontrolliert in die bestehende `404 Widget position not found`-Wahrheit statt in Python-`KeyError`.
- fehlerhafte Persistenz-Entries bleiben bewusst unverändert liegen; der Slice härtet nur den kleinsten Runtime-Zugriff auf die aktuelle Position vor dem Snapshot in `history`.
- Persistenzform, Event-Surface und übrige Runtime-Logik bleiben bewusst unverändert.

## Test-Evidence
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_widget_positions_contract.py tests/test_contract_inventory_check.py tests/test_public_api_docs_alignment.py tests/test_system_contract.py` → **22 passed**
- `/config/clawd/.venv_smoke_gate/bin/python scripts/contract_inventory_check.py --repo . --light` → **OK**
- `/config/clawd/.venv_smoke_gate/bin/python scripts/contract_inventory_check.py --repo .` → **OK**

## Nächster exakter Task
- Slice 131 — `POST /api/v1/widgets/positions/<widget_id>/history` auf den kleinsten expliziten Legacy-/Persistenz-`history`-Container-Guard auditieren, damit shape-falsche bereits gespeicherte nicht-listige `history`-Container nicht weiter in `AttributeError`-Wahrheit kippen, ohne neue Surface oder zusätzliche Store-Logik einzuführen.
