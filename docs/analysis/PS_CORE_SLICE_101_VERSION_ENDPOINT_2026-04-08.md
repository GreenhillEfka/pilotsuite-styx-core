# PS Core Slice 101 — `/version` als Runtime-/OpenAPI-Slice reintroduziert

## Stand
- Nach Slice 100 war die öffentliche Claim-Lage bereinigt, aber `/version` blieb noch bewusst aus der `v20`-Runtime entfernt.
- Im Worktree existiert mit `VERSION` bereits eine kanonische Manifest-Wahrheit, daher war `/version` der kleinste echte Reintroduktions-Kandidat ohne neue Schattenquelle.

## Gelandete Artefakte
- `pilotsuite_core/rootfs/usr/src/app/main.py`
- `README.md`
- `docs/openapi.json`
- `docs/openapi.yaml`
- `tests/test_system_contract.py`
- `tests/test_contract_inventory_check.py`
- `tests/test_public_api_docs_alignment.py`

## Gelandeter Scope
- `GET /version` als echter Runtime-Endpoint wieder gelandet
- Endpoint liest die Runtime-Version direkt aus `VERSION`
- README und OpenAPI auf dieselbe öffentliche Surface (`/health`, `/version`, `widget_positions*`) gezogen
- Guard-Tests auf Runtime-, OpenAPI- und README-Alignment mit `/version` erweitert

## Test-Evidence
- `pytest -q tests/test_system_contract.py tests/test_contract_inventory_check.py tests/test_public_api_docs_alignment.py`
- `python3 scripts/contract_inventory_check.py --repo . --light`
- `python3 scripts/contract_inventory_check.py --repo .`

## Bekannte Inkonsistenz
- die in der Pflichtbasis genannten Dateien `PILOTSUITE_EXECUTION_FOUNDATION.md`, `PILOTSUITE_PROGRESS_LEDGER.md`, `PILOTSUITE_RECONSOLIDATED_MASTER_WORKPLAN_2026-04-04.md` und `PILOTSUITE_ONE_LEAD_EXECUTION_STANDARD_2026-04-04.md` fehlen in den referenzierten Pfaden weiterhin
- der Slice wurde deshalb erneut vom letzten realen Artefaktstand aus Taskboard/Tasklog fortgesetzt

## Nächster exakter Task
- Slice 102: `/api/v1/zones` als nächsten kleinsten öffentlichen Reintroduktions-Kandidaten read-only gegen den realen `v20`-Baum auditieren und den minimalen landingfähigen Contract-Scope festziehen
