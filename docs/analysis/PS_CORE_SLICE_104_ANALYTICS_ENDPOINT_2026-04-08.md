# PS Core Slice 104 — `/api/v1/analytics` read-only Reintroduction

## Ausgangslage
- Der aktuelle `v20.0.0`-Worktree hatte nach Slice 103 nur `/health`, `/version`, `/api/v1/presence`, `/api/v1/zones` und `widget_positions` als echte öffentliche Runtime-Surface.
- README und frühere Artefakte verwiesen historisch weiter auf Analytics, im laufenden Baum existierte dafür aber kein öffentlicher Endpoint mehr.
- Die verpflichtenden Team-Basisdokumente fehlten weiterhin am erwarteten Pfad; der Slice wurde daher erneut vom letzten realen Artefaktstand in Taskboard/Tasklog fortgeführt.

## Audit
- Im aktuellen Worktree gibt es keine lebende Analytics-Runtime mehr.
- In der Git-Historie ist die Analytics-Surface fragmentiert, vor allem über spätere Unterpfade wie `/api/v1/analytics/overview`, `/trends`, `/predictions` und `/patterns`.
- Für den kleinsten landingfähigen Slice wurde deshalb bewusst nur ein read-only Root-Überblick unter `/api/v1/analytics` reintroduziert, statt die frühere Subpfad-Landschaft samt Engines und Stores mitzuschleppen.

## Landing-Scope
- neuer Flask-Blueprint `dashboard.api.v1.analytics`
- `GET /api/v1/analytics`
- statische read-only Analytics-Übersicht mit `module_cards`, `kpis`, `attention_required`, Gesamtstatus und Zeitfenster
- Contract-/README-/OpenAPI-Inventur auf den gelandeten Root-Pfad rebased

## Nicht Teil dieses Slices
- keine `/api/v1/analytics/trends`, `/predictions`, `/patterns` oder `/overview`-Subpfade
- keine Analytics-Stores
- keine Forecast-/Anomaly-Engine-Reaktivierung
- keine Notifications-Reintroduktion

## Artefakte
- `pilotsuite_core/rootfs/usr/src/app/main.py`
- `pilotsuite_core/rootfs/usr/src/app/dashboard/api/v1/analytics.py`
- `pilotsuite_core/rootfs/usr/src/app/dashboard/api/v1/blueprints_config.py`
- `README.md`
- `docs/openapi.json`
- `docs/openapi.yaml`
- `tests/test_analytics_contract.py`
- `tests/test_contract_inventory_check.py`
- `tests/test_public_api_docs_alignment.py`

## Verifikation
- `pytest -q tests/test_analytics_contract.py tests/test_system_contract.py tests/test_contract_inventory_check.py tests/test_public_api_docs_alignment.py`
- `python3 scripts/contract_inventory_check.py --repo . --light`
- `python3 scripts/contract_inventory_check.py --repo .`

## Nächster exakter Task
- Slice 105 — `/api/v1/notifications` als nächsten kleinsten öffentlichen Reintroduktions-Kandidaten read-only gegen den realen `v20`-Baum auditieren und nur den minimalen landingfähigen Contract-Scope ziehen.
