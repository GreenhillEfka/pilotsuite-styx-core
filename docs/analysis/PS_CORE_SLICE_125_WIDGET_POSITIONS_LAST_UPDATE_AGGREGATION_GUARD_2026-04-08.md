# PS Core Slice 125 — `widget_positions` `last_update`-Aggregations-Guard

## Stand
- Nach Slice 124 blieb im `widget_positions`-Scope noch eine kleine Root-Read-Lücke offen.
- `GET /api/v1/widgets/positions` aggregierte `last_update` direkt per `max(...)` über alle Persistenz-Entries.
- Sobald gemischte geladene Entries vorlagen, bei denen mindestens ein valider Eintrag kein `last_update` hatte, konnte die Root-Response in Python-`TypeError` kippen.
- Auf Rekonsolidierungs-Priorität wurde deshalb nur der kleinste Read-Guard gelandet, ohne neue Surface oder zusätzliche Store-Logik einzuführen.

## Gelandete Artefakte
- `pilotsuite_core/rootfs/usr/src/app/dashboard/api/v1/widget_positions.py`
- `tests/test_widget_positions_contract.py`
- `docs/analysis/PS_CORE_SLICE_125_WIDGET_POSITIONS_LAST_UPDATE_AGGREGATION_GUARD_2026-04-08.md`

## Gelandeter Scope
- `GET /api/v1/widgets/positions` verwendet die Root-Aggregation für `last_update` jetzt über einen kleinen Helper statt über einen ungeschützten direkten `max(...)`-Call.
- für die Aggregation werden nur vorhandene String-`last_update`-Werte berücksichtigt, damit gemischte Persistenz-Entries ohne Feld oder mit shape-falschem Wert die Root-Response nicht kippen.
- die bestehende Response-Form bleibt unverändert: wenn kein verwertbarer `last_update` existiert, bleibt der Root-Wert kontrolliert `null`.
- Persistenz, Event-Hooks, Write-Pfade und öffentliche Surface bleiben bewusst unverändert; es war ein reiner Read-Guard-Slice.

## Test-Evidence
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_widget_positions_contract.py tests/test_contract_inventory_check.py tests/test_public_api_docs_alignment.py tests/test_system_contract.py` → **14 passed**
- `/config/clawd/.venv_smoke_gate/bin/python scripts/contract_inventory_check.py --repo . --light` → **OK**
- `/config/clawd/.venv_smoke_gate/bin/python scripts/contract_inventory_check.py --repo .` → **OK**

## Nächster exakter Task
- Slice 126 — `POST /api/v1/widgets/positions` und `POST /api/v1/widgets/positions/bulk` auf den kleinsten expliziten `widget_id`-Typ-Guard auditieren, damit shape-falsche nicht-stringige `widget_id`-Payloads keine instabile Persistenz-/Lookup-Wahrheit erzeugen, ohne neue Surface oder zusätzliche Store-Logik einzuführen.
