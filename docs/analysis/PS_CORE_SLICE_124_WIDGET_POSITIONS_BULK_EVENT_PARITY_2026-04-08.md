# PS Core Slice 124 — `widget_positions` Bulk-Event-Parität

## Stand
- Nach dem Bulk-Payload-Guard blieb im `widget_positions`-Scope noch eine kleine Paritätslücke zwischen Single-Write und Bulk-Write offen.
- `POST /api/v1/widgets/positions` emittierte bereits pro erfolgreicher Mutation den Hook `widget_position_update`, der Bulk-Pfad speicherte erfolgreiche Einträge aber noch still ohne denselben Event-Call.
- Auf Rekonsolidierungs-Priorität wurde deshalb der kleinste verbleibende `widget_positions`-Follow-up auf Hook-Wahrheit gezogen, ohne neue Surface oder zusätzliche Store-Logik einzuführen.

## Gelandete Artefakte
- `pilotsuite_core/rootfs/usr/src/app/dashboard/api/v1/widget_positions.py`
- `tests/test_widget_positions_contract.py`
- `docs/analysis/PS_CORE_SLICE_124_WIDGET_POSITIONS_BULK_EVENT_PARITY_2026-04-08.md`

## Gelandeter Scope
- `POST /api/v1/widgets/positions/bulk` sammelt erfolgreiche Saves jetzt als Event-Payloads mit derselben Form wie der Single-Write: `{"widget_id", "position"}`
- die Persistenz bleibt bewusst unverändert minimal: alle validen Einträge werden weiter in einem Durchlauf gespeichert und genau einmal persistiert
- erst nach erfolgreichem Persist werden pro erfolgreich gespeichertem Bulk-Eintrag `widget_position_update`-Hooks emittiert, in derselben Reihenfolge wie die gelandeten Saves
- invalide Bulk-Einträge bleiben rein in `errors[]` sichtbar und emittieren bewusst keinen Erfolgs-Hook
- öffentliche Runtime-Surface, Inventur und OpenAPI bleiben unverändert; es war ein reiner Hook-/Contract-Paritäts-Slice

## Test-Evidence
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_widget_positions_contract.py tests/test_contract_inventory_check.py tests/test_public_api_docs_alignment.py tests/test_system_contract.py` → **13 passed**
- `/config/clawd/.venv_smoke_gate/bin/python scripts/contract_inventory_check.py --repo . --light` → **OK**
- `/config/clawd/.venv_smoke_gate/bin/python scripts/contract_inventory_check.py --repo .` → **OK**

## Nächster exakter Task
- Slice 125 — `GET /api/v1/widgets/positions` auf den kleinsten `last_update`-Aggregations-Guard auditieren, damit gemischte Persistenz-Entries ohne `last_update` die Root-Response nicht in Python-`TypeError` kippen, ohne neue Surface oder zusätzliche Store-Logik einzuführen.
