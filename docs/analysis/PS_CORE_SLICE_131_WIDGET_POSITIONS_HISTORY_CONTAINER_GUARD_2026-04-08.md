# PS Core Slice 131 — `widget_positions` `history`-Container-Guard

## Kontext
- Scope bleibt bewusst auf `POST /api/v1/widgets/positions/<widget_id>/history` begrenzt.
- Bereits gespeicherte shape-falsche nicht-listige `history`-Container konnten im Runtime-Pfad bisher in Python-`AttributeError` kippen.
- Öffentliche Surface, Persistenzform und Store-Repair bleiben unverändert.

## Änderung
- der `/history`-Pfad validiert den bereits gespeicherten `history`-Container jetzt explizit auf List-Shape, bevor ein neuer Snapshot angehängt wird
- shape-falsche persistierte `history`-Container laufen kontrolliert in die bestehende `404 Widget position not found`-Wahrheit statt in Python-Fehler
- vorhandene fehlerhafte Persistenzreste bleiben bewusst unverändert liegen; der Slice härtet nur den kleinsten Runtime-Zugriff

## Tests
- fokussierter Contract-Test deckt persistierte nicht-listige `history`-Container auf `/history` jetzt explizit gegen Drift ab
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_widget_positions_contract.py tests/test_contract_inventory_check.py tests/test_public_api_docs_alignment.py tests/test_system_contract.py`
- `/config/clawd/.venv_smoke_gate/bin/python scripts/contract_inventory_check.py --repo . --light`
- `/config/clawd/.venv_smoke_gate/bin/python scripts/contract_inventory_check.py --repo .`

## Ergebnis
- echter Runtime-Diff gelandet
- fokussierte Tests und Contract-Inventur grün
- kein zusätzlicher API-, Config- oder Store-Scope eingeführt
