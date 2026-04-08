# PS Core Slice 126 — `widget_positions` `widget_id`-Typ-Guard

## Stand
- Nach Slice 125 blieb im `widget_positions`-Write-Scope noch eine kleine Contract-Lücke offen.
- `POST /api/v1/widgets/positions` und `POST /api/v1/widgets/positions/bulk` prüften bislang nur auf vorhandenes `widget_id`, aber nicht explizit auf String-Typ.
- Dadurch konnten shape-falsche nicht-stringige `widget_id`-Payloads als Store-Key, Lookup-Wahrheit oder Bulk-Fehler-Referenz in einen instabilen Zustand driften.
- Auf Rekonsolidierungs-Priorität wurde deshalb nur der kleinste explizite Typ-Guard gelandet, ohne neue Surface oder zusätzliche Store-Logik einzuführen.

## Gelandete Artefakte
- `pilotsuite_core/rootfs/usr/src/app/dashboard/api/v1/widget_positions.py`
- `tests/test_widget_positions_contract.py`
- `docs/analysis/PS_CORE_SLICE_126_WIDGET_POSITIONS_WIDGET_ID_TYPE_GUARD_2026-04-08.md`

## Gelandeter Scope
- `POST /api/v1/widgets/positions` lehnt nicht-stringige `widget_id`-Payloads jetzt kontrolliert mit `400 Invalid widget_id` ab.
- `POST /api/v1/widgets/positions/bulk` behandelt dieselbe Form explizit als Fehler statt shape-falsche Keys in Persistenz oder Lookup-Wahrheit zu übernehmen.
- Bulk-Fehler referenzieren bei nicht-stringiger oder fehlender `widget_id` kontrolliert weiter `unknown`, damit die Fehlerliste keine zweite instabile Identifier-Form eröffnet.
- bestehende Runtime-Surface, Persistenzform, Event-Hooks und Contract-Inventur bleiben unverändert; der Slice härtet nur die minimale Write-Validierung.

## Test-Evidence
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_widget_positions_contract.py tests/test_contract_inventory_check.py tests/test_public_api_docs_alignment.py tests/test_system_contract.py` → **15 passed**
- `/config/clawd/.venv_smoke_gate/bin/python scripts/contract_inventory_check.py --repo . --light` → **OK**
- `/config/clawd/.venv_smoke_gate/bin/python scripts/contract_inventory_check.py --repo .` → **OK**

## Nächster exakter Task
- Slice 127 — `POST /api/v1/widgets/positions` und `POST /api/v1/widgets/positions/bulk` auf den kleinsten expliziten `history`-/`redo_stack`-Listen-Guard auditieren, damit shape-falsche Container aus Write-Payloads die späteren `history`-/`undo`-/`redo`-Pfade nicht in instabile Laufzeitwahrheit ziehen, ohne neue Surface oder zusätzliche Store-Logik einzuführen.
