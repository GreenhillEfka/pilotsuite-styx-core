# PS Core Slice 123 — `widget_positions` Bulk-Payload-Guard

## Stand
- Trotz gelandeter `widget_positions`-Runtime, Inventur und Persistenz-Härtung blieb im Bulk-Write noch eine kleine Contract-Lücke offen.
- `POST /api/v1/widgets/positions/bulk` lief bei shape-falschen Top-Level-Payloads oder Nicht-Objekt-Einträgen bislang in Python-`AttributeError` statt kontrolliert zu antworten.
- Auf Rekonsolidierungs-Priorität wurde deshalb der kleinste verbliebene `widget_positions`-Contract-Rest vor weiterem Notifications-Follow-up geschlossen.

## Gelandete Artefakte
- `pilotsuite_core/rootfs/usr/src/app/dashboard/api/v1/widget_positions.py`
- `tests/test_widget_positions_contract.py`
- `docs/analysis/PS_CORE_SLICE_123_WIDGET_POSITIONS_BULK_PAYLOAD_GUARD_2026-04-08.md`

## Gelandeter Scope
- `_coerce_position(...)` lehnt shape-falsche Nicht-Objekt-Payloads jetzt kontrolliert mit `Invalid position payload` ab statt in `.get(...)` zu kippen
- `POST /api/v1/widgets/positions` beantwortet damit auch JSON-Listen oder andere Nicht-Objekte sauber mit `400`
- `POST /api/v1/widgets/positions/bulk` verlangt für `positions` jetzt explizit eine Liste und antwortet sonst kontrolliert mit `400 Invalid positions payload`
- gemischte Bulk-Payloads mit Nicht-Objekt-Einträgen bleiben landingfähig: valide Einträge werden gespeichert, invalide Einträge landen kontrolliert in `errors[]`
- öffentliche Runtime-Surface, Inventur und OpenAPI bleiben unverändert; es war ein reiner Contract-Härtungs-Slice

## Test-Evidence
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_widget_positions_contract.py tests/test_contract_inventory_check.py tests/test_public_api_docs_alignment.py tests/test_system_contract.py` → **13 passed**
- `/config/clawd/.venv_smoke_gate/bin/python scripts/contract_inventory_check.py --repo . --light` → **OK**
- `/config/clawd/.venv_smoke_gate/bin/python scripts/contract_inventory_check.py --repo .` → **OK**

## Nächster exakter Task
- Slice 124 — `POST /api/v1/widgets/positions/bulk` auf den kleinsten Event-Paritäts-Follow-up auditieren, damit erfolgreiche Bulk-Saves dieselbe `widget_position_update`-Hook-Wahrheit wie der Single-Write halten, ohne neue Surface oder zusätzliche Store-Logik einzuführen.
