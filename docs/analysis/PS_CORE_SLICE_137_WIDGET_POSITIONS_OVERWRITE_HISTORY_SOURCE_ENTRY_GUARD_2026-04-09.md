# PS Core Slice 137 — `widget_positions` Overwrite-Write `history`-Quell-Entry-Guard

## Stand
- Nach Slice 136 blieb auf den Overwrite-Write-Pfaden von `POST /api/v1/widgets/positions` und `POST /api/v1/widgets/positions/bulk` noch eine kleine Persistenzlücke offen.
- Bereits persistierte shape-falsche `history`-Einträge wurden beim Überschreiben einer bestehenden Widget-Position bisher still in den neuen Snapshot weitergetragen, solange der Container selbst listig war.
- Gelandet wurde deshalb nur der kleinste explizite Quell-Entry-Guard auf den bestehenden Overwrite-Pfaden, ohne neue Surface oder zusätzliche Store-Logik einzuführen.

## Gelandete Artefakte
- `pilotsuite_core/rootfs/usr/src/app/dashboard/api/v1/widget_positions.py`
- `tests/test_widget_positions_contract.py`
- `docs/analysis/PS_CORE_SLICE_137_WIDGET_POSITIONS_OVERWRITE_HISTORY_SOURCE_ENTRY_GUARD_2026-04-09.md`

## Gelandeter Scope
- `POST /api/v1/widgets/positions` validiert beim Überschreiben einer bestehenden Position jetzt auch die bereits persistierten `history`-Einträge explizit vor der Übernahme in den neuen Snapshot.
- `POST /api/v1/widgets/positions/bulk` behandelt denselben Legacy-Fall pro betroffenem Eintrag kontrolliert in `errors[]`, statt shape-falsche Persistenzreste still weiterzutragen.
- fehlende `history`-Container bleiben weiter minimal landingfähig; der Slice härtet nur den kleinsten Persistenz-Drift-Fall auf bestehenden Overwrite-Write-Pfaden.
- valide historische Zusatzfelder wie `timestamp` bleiben weiterhin landingfähig; fehlerhafte Persistenz-Entries bleiben bewusst unverändert liegen.

## Test-Evidence
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_widget_positions_contract.py tests/test_contract_inventory_check.py tests/test_public_api_docs_alignment.py tests/test_system_contract.py` → **34 passed**
- `/config/clawd/.venv_smoke_gate/bin/python scripts/contract_inventory_check.py --repo . --light` → **OK**
- `/config/clawd/.venv_smoke_gate/bin/python scripts/contract_inventory_check.py --repo .` → **OK**

## Nächster exakter Task
- Slice 138 — `POST /api/v1/widgets/positions/<widget_id>/history` auf den kleinsten expliziten Legacy-/Persistenz-`history`-Quell-Entry-Guard auditieren, damit shape-falsche bereits gespeicherte `history`-Einträge beim History-Append nicht still weitergetragen werden, ohne neue Surface oder zusätzliche Store-Logik einzuführen.
