# PS Core Slice 102 — `/api/v1/zones` read-only Reintroduction

## Ausgangslage
- Der aktuelle `v20.0.0`-Worktree hatte nach Slice 101 nur `/health`, `/version` und `widget_positions` als echte öffentliche Runtime-Surface.
- README und frühere Artefakte verwiesen historisch auf `/api/v1/zones`, im laufenden Baum existierte dafür aber kein Endpoint mehr.
- Die verpflichtenden Team-Basisdokumente fehlten weiterhin am erwarteten Pfad; der Slice wurde daher erneut vom letzten realen Artefaktstand in Taskboard/Tasklog fortgeführt.

## Audit
- Im aktuellen Worktree gibt es keine lebende Zonen-Implementierung mehr.
- In der Git-Historie liegt jedoch ein klarer `v20`-Vorläufer für den Habitus-Zonenkatalog vor, insbesondere in den früheren `habitus_zones`-Definitionen.
- Für den kleinsten landingfähigen Slice wurde bewusst nur der read-only Katalog übernommen, ohne alte Write-/Metrics-/Matcher-Flächen mitzuschleppen.

## Landing-Scope
- neuer Flask-Blueprint `dashboard.api.v1.zones`
- `GET /api/v1/zones`
- optionaler Query-Filter `?zone_type=<exact>`
- kontrollierter `400 invalid_zone_type`-Pfad
- statischer read-only Habitus-Zonenkatalog als kleinste belastbare Runtime-Wahrheit im nackten `v20`-Baum

## Nicht Teil dieses Slices
- keine Zonen-Mutationen
- keine Metrics
- kein Matcher
- keine Home-Assistant-Discovery
- keine Presence-/Analytics-/Notifications-Reintroduktion

## Artefakte
- `pilotsuite_core/rootfs/usr/src/app/main.py`
- `pilotsuite_core/rootfs/usr/src/app/dashboard/api/v1/zones.py`
- `pilotsuite_core/rootfs/usr/src/app/dashboard/api/v1/blueprints_config.py`
- `README.md`
- `docs/openapi.json`
- `docs/openapi.yaml`
- `tests/test_zones_contract.py`
- `tests/test_contract_inventory_check.py`
- `tests/test_public_api_docs_alignment.py`

## Verifikation
- `pytest -q tests/test_zones_contract.py tests/test_system_contract.py tests/test_contract_inventory_check.py tests/test_public_api_docs_alignment.py`
- `python3 scripts/contract_inventory_check.py --repo . --light`
- `python3 scripts/contract_inventory_check.py --repo .`

## Nächster exakter Task
- Slice 103 — kleinsten nächsten öffentlichen Reintroduktions-Kandidaten `/api/v1/presence` read-only gegen den realen `v20`-Baum auditieren und nur den minimalen landingfähigen Contract-Scope ziehen.
