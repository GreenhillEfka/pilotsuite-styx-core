# PS Core Slice 100 — Public-API-Claims auf echte `v20`-Runtime bereinigt

## Stand
- Nach Slice 99 war die Runtime-/Inventur-Wahrheit für `widget_positions` gelandet, aber der nächste offene Contract-Slice blieb die öffentliche Claim-Lage in README/OpenAPI.
- Der aktuelle `v20.0.0`-Worktree exponiert real nur `/health` plus `widget_positions`; Legacy-Endpunkte aus älteren Baumständen sind in dieser Runtime nicht vorhanden.

## Gelandete Artefakte
- `README.md`
- `scripts/contract_inventory_check.py`
- `docs/openapi.json`
- `docs/openapi.yaml`
- `tests/test_public_api_docs_alignment.py`

## Gelandeter Scope
- README auf den tatsächlich gelandeten `v20`-Runtime-Scope rebaselined
- verbleibende Legacy-Endpunkte `/version`, `/api/v1/zones`, `/api/v1/presence`, `/api/v1/analytics`, `/api/v1/notifications` explizit als nicht Teil der aktuellen Runtime markiert statt implizit mitzuschwingen
- Full-Mode-Guard erweitert, damit README-Endpunktclaims gegen die echte öffentliche Runtime-Surface geprüft werden
- OpenAPI-Beschreibung auf dieselbe öffentliche Runtime-Wahrheit gezogen

## Test-Evidence
- `pytest -q tests/test_contract_inventory_check.py tests/test_public_api_docs_alignment.py`
- `python3 scripts/contract_inventory_check.py --repo . --light`
- `python3 scripts/contract_inventory_check.py --repo .`

## Bekannte Inkonsistenz
- die in der Pflichtbasis genannten Dateien `PILOTSUITE_EXECUTION_FOUNDATION.md` und `PILOTSUITE_RECONSOLIDATED_MASTER_WORKPLAN_2026-04-04.md` fehlen weiterhin in `/config/clawd/team`
- der Slice wurde deshalb erneut vom letzten realen Artefaktstand aus Taskboard/Tasklog fortgesetzt

## Nächster exakter Task
- Slice 101: kleinsten echten Reintroduktions-Kandidaten wählen, beginnend mit `/version` als eigener Runtime-/OpenAPI-Slice, falls der Endpoint im `v20`-Baum wieder öffentlich gebraucht wird
