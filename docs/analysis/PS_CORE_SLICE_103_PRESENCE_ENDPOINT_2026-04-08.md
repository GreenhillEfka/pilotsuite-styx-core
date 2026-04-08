# PS Core Slice 103 — `/api/v1/presence` read-only Reintroduction

## Ausgangslage
- Der aktuelle `v20.0.0`-Worktree hatte nach Slice 102 nur `/health`, `/version`, `/api/v1/zones` und `widget_positions` als echte öffentliche Runtime-Surface.
- README, frühere API-Dokumente und historische Dashboard-Artefakte führten `/api/v1/presence` weiter als öffentliche Surface, im laufenden Baum existierte dafür aber kein Endpoint mehr.
- Die verpflichtenden Team-Basisdokumente fehlten weiterhin am erwarteten Pfad; der Slice wurde daher erneut vom letzten realen Artefaktstand in Taskboard/Tasklog fortgeführt.

## Audit
- Im aktuellen Worktree gibt es keine lebende Presence-Runtime mehr.
- In der Git-Historie ist `/api/v1/presence` klar als öffentliche `v20`-Surface dokumentiert, auch wenn die letzte Implementierung vor allem unter Subpfaden wie `/status`, `/history` und `/update` lebte.
- Für den kleinsten landingfähigen Slice wurde deshalb nur die read-only Haushaltszusammenfassung auf dem Root-Pfad reintroduziert, statt die alte mutierende Presence-Pipeline mitzuschleppen.

## Landing-Scope
- neuer Flask-Blueprint `dashboard.api.v1.presence`
- `GET /api/v1/presence`
- statische read-only Haushalts-Presence-Zusammenfassung mit `persons_home`, `persons_away`, Totals und `household_status`
- Contract-/README-/OpenAPI-Inventur auf den gelandeten Root-Pfad rebased

## Nicht Teil dieses Slices
- keine Presence-Mutationen
- keine `/api/v1/presence/update`, `/history`, `/hold` oder `/sources`-Subpfade
- keine Sensor-Fusion
- keine Analytics-/Notifications-Reintroduktion

## Artefakte
- `pilotsuite_core/rootfs/usr/src/app/main.py`
- `pilotsuite_core/rootfs/usr/src/app/dashboard/api/v1/presence.py`
- `pilotsuite_core/rootfs/usr/src/app/dashboard/api/v1/blueprints_config.py`
- `README.md`
- `docs/openapi.json`
- `docs/openapi.yaml`
- `tests/test_presence_contract.py`
- `tests/test_contract_inventory_check.py`
- `tests/test_public_api_docs_alignment.py`

## Verifikation
- `pytest -q tests/test_presence_contract.py tests/test_system_contract.py tests/test_contract_inventory_check.py tests/test_public_api_docs_alignment.py`
- `python3 scripts/contract_inventory_check.py --repo . --light`
- `python3 scripts/contract_inventory_check.py --repo .`

## Nächster exakter Task
- Slice 104 — `/api/v1/analytics` als nächsten kleinsten öffentlichen Reintroduktions-Kandidaten read-only gegen den realen `v20`-Baum auditieren und nur den minimalen landingfähigen Contract-Scope ziehen.
