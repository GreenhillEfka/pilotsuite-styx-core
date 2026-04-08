# PS Core Slice 127 — `widget_positions` `history`-/`redo_stack`-Listen-Guard

## Stand
- Nach Slice 126 blieb im `widget_positions`-Write-Scope noch eine kleine Contract-Lücke offen.
- `POST /api/v1/widgets/positions` und `POST /api/v1/widgets/positions/bulk` übernahmen `history` und `redo_stack` bislang ungeprüft aus Write-Payloads.
- Dadurch konnten shape-falsche Container wie Objekte oder Strings in die Runtime gelangen und die späteren `history`-/`undo`-/`redo`-Pfade auf instabile Listen-Wahrheit setzen.
- Auf Rekonsolidierungs-Priorität wurde deshalb nur der kleinste explizite Listen-Guard gelandet, ohne neue Surface oder zusätzliche Store-Logik einzuführen.

## Gelandete Artefakte
- `pilotsuite_core/rootfs/usr/src/app/dashboard/api/v1/widget_positions.py`
- `tests/test_widget_positions_contract.py`
- `docs/analysis/PS_CORE_SLICE_127_WIDGET_POSITIONS_HISTORY_REDO_LIST_GUARD_2026-04-08.md`

## Gelandeter Scope
- `POST /api/v1/widgets/positions` lehnt nicht-listige `history`- oder `redo_stack`-Payloads jetzt kontrolliert mit `400 Invalid history` bzw. `400 Invalid redo_stack` ab.
- `POST /api/v1/widgets/positions/bulk` behandelt dieselbe Form pro Eintrag kontrolliert in `errors[]`, ohne shape-falsche Container in Persistenz oder Laufzeitwahrheit zu übernehmen.
- valide Listen-Payloads bleiben landingfähig und werden weiter unverändert deep-copied übernommen.
- bestehende Runtime-Surface, Persistenzform, Event-Hooks und Contract-Inventur bleiben unverändert; der Slice härtet nur die minimale Container-Validierung im bestehenden Write-Pfad.

## Test-Evidence
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_widget_positions_contract.py tests/test_contract_inventory_check.py tests/test_public_api_docs_alignment.py tests/test_system_contract.py` → **17 passed**
- `/config/clawd/.venv_smoke_gate/bin/python scripts/contract_inventory_check.py --repo . --light` → **OK**
- `/config/clawd/.venv_smoke_gate/bin/python scripts/contract_inventory_check.py --repo .` → **OK**

## Nächster exakter Task
- Slice 128 — `POST /api/v1/widgets/positions` und `POST /api/v1/widgets/positions/bulk` auf den kleinsten expliziten `history`-/`redo_stack`-Entry-Shape-Guard auditieren, damit listige aber shape-falsche History-/Redo-Einträge die späteren `undo`-/`redo`-Pfade nicht in KeyError-/TypeError-Wahrheit ziehen, ohne neue Surface oder zusätzliche Store-Logik einzuführen.
