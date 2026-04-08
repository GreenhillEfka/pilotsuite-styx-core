# PS Core Slice 99 — `widget_positions` OpenAPI-/Contract-Inventur

## Stand
- Slice 98 hatte die Runtime für `dashboard.api.v1.widget_positions` wiederhergestellt, aber die Inventar-/OpenAPI-Wahrheit des `v20.0.0`-Baums blieb leer.
- Im aktuellen Worktree fehlten `docs/openapi.*`, `scripts/contract_inventory_check.py` und eine lokale Contract-Inventur für die registrierten Core-Blueprints.
- Die vorhandene Pre-Commit-Hülle zeigte genau diese Lücke: Guard vorhanden, eigentliche Inventur noch nicht gelandet.

## Gelandete Artefakte
- `pilotsuite_core/rootfs/usr/src/app/dashboard/api/v1/blueprints_config.py`
- `scripts/contract_inventory_check.py`
- `docs/openapi.json`
- `docs/openapi.yaml`
- `tests/test_contract_inventory_check.py`

## Gelandeter Scope
- `widget_positions` als explizite Contract-Inventur mit allen Runtime-Pfaden und HTTP-Methoden verankert
- OpenAPI-Spec für den aktuellen `v20`-Baum wieder angelegt und den laufenden `widget_positions`-Slice dokumentiert
- Drift-Guard gelandet, der Runtime ↔ Inventur und optional Inventur ↔ OpenAPI verifiziert
- fokussierter Test deckt Guard-Lauf in Light- und Full-Mode sowie die dokumentierten `widget_positions`-Pfade ab

## Test-Evidence
- `pytest -q tests/test_widget_positions_contract.py tests/test_contract_inventory_check.py`
- `python3 scripts/contract_inventory_check.py --repo . --light`
- `python3 scripts/contract_inventory_check.py --repo .`

## Bekannte Inkonsistenz
- die in der Pflichtbasis genannten Dateien `PILOTSUITE_EXECUTION_FOUNDATION.md` und `PILOTSUITE_RECONSOLIDATED_MASTER_WORKPLAN_2026-04-04.md` fehlen in `/config/clawd/team`; der Slice wurde deshalb vom letzten realen Artefaktstand aus Taskboard/Tasklog fortgesetzt.

## Nächster exakter Task
- Slice 100: README-/OpenAPI-Claims für verbleibende Legacy-Endpunkte (`/version`, `/api/v1/zones`, `/api/v1/presence`, `/api/v1/analytics`, `/api/v1/notifications`) gegen die echte `v20`-Runtime rebaselinen oder explizit entfernen.
