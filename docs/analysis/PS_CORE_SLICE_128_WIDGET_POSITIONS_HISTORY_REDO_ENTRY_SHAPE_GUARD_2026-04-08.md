# PS Core Slice 128 — `widget_positions` `history`-/`redo_stack`-Entry-Shape-Guard

## Stand
- Nach Slice 127 blieb im `widget_positions`-Write-Scope noch eine kleine Contract-Lücke offen.
- `POST /api/v1/widgets/positions` und `POST /api/v1/widgets/positions/bulk` akzeptierten zwar nur noch listige `history`- und `redo_stack`-Container, übernahmen aber weiterhin shape-falsche Listeneinträge ungeprüft.
- Dadurch konnten Einträge ohne `x`/`y` oder mit nicht brauchbaren Positionswerten später die `undo`-/`redo`-Pfade in `KeyError`-/`TypeError`-Wahrheit ziehen.
- Auf Rekonsolidierungs-Priorität wurde deshalb nur der kleinste explizite Entry-Shape-Guard im bestehenden Write-Pfad gelandet, ohne neue Surface oder zusätzliche Store-Logik einzuführen.

## Gelandete Artefakte
- `pilotsuite_core/rootfs/usr/src/app/dashboard/api/v1/widget_positions.py`
- `tests/test_widget_positions_contract.py`
- `docs/analysis/PS_CORE_SLICE_128_WIDGET_POSITIONS_HISTORY_REDO_ENTRY_SHAPE_GUARD_2026-04-08.md`

## Gelandeter Scope
- `POST /api/v1/widgets/positions` validiert `history`- und `redo_stack`-Einträge jetzt explizit auf minimale Positions-Shape mit brauchbaren `x`-/`y`-Werten und optional positivem `width`/`height`.
- `POST /api/v1/widgets/positions/bulk` behandelt dieselbe Form pro Eintrag kontrolliert in `errors[]`, statt shape-falsche Stack-Einträge in Persistenz oder Runtime-Wahrheit zu übernehmen.
- valide Stack-Einträge bleiben landingfähig; vorhandene Zusatzfelder wie `timestamp` bleiben erhalten.
- bestehende Runtime-Surface, Persistenzform, Event-Hooks und Contract-Inventur bleiben unverändert; der Slice härtet nur die minimale Entry-Validierung im bestehenden Write-Pfad.

## Test-Evidence
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_widget_positions_contract.py tests/test_contract_inventory_check.py tests/test_public_api_docs_alignment.py tests/test_system_contract.py` → **19 passed**
- `/config/clawd/.venv_smoke_gate/bin/python scripts/contract_inventory_check.py --repo . --light` → **OK**
- `/config/clawd/.venv_smoke_gate/bin/python scripts/contract_inventory_check.py --repo .` → **OK**

## Nächster exakter Task
- Slice 129 — `POST /api/v1/widgets/positions/<widget_id>/undo` und `POST /api/v1/widgets/positions/<widget_id>/redo` auf den kleinsten expliziten Legacy-/Persistenz-Entry-Guard auditieren, damit bereits gespeicherte shape-falsche `history`-/`redo_stack`-Einträge nicht weiter in `KeyError`-/`TypeError`-Wahrheit kippen, ohne neue Surface oder zusätzliche Store-Logik einzuführen.
