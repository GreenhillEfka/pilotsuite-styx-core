# PS Core Slice 105 — `/api/v1/notifications` read-only Reintroduction

## Ausgangslage
- Der aktuelle `v20.0.0`-Worktree hatte nach Slice 104 nur `/health`, `/version`, `/api/v1/presence`, `/api/v1/analytics`, `/api/v1/zones` und `widget_positions` als echte öffentliche Runtime-Surface.
- README und historische HA-Artefakte verwiesen weiter auf einen Notifications-Feed unter `/api/v1/notifications`, im laufenden Baum existierte dafür aber kein öffentlicher Endpoint mehr.
- Die verpflichtenden Team-Basisdokumente fehlten weiterhin am erwarteten Pfad; der Slice wurde daher erneut vom letzten realen Artefaktstand in Taskboard/Tasklog fortgeführt.

## Audit
- Im aktuellen Worktree gibt es keine lebende Notifications-Runtime mehr.
- Die Git-Historie führt unter `/api/v1/notifications*` viele Write-, Delivery-, Digest- und Subscription-Pfade mit.
- Der kleinste landingfähige Slice ist deshalb bewusst nur der read-only Root-Feed unter `/api/v1/notifications`, weil genau dieser Pfad historisch als Basisliste diente und von der HA-Seite weiterhin direkt referenziert wird.

## Landing-Scope
- neuer Flask-Blueprint `dashboard.api.v1.notifications`
- `GET /api/v1/notifications`
- statischer read-only Notifications-Feed mit `limit`, `unread_only`, `type` und `source` als exakten Query-Filtern
- Contract-/README-/OpenAPI-Inventur auf den gelandeten Root-Pfad rebased

## Nicht Teil dieses Slices
- keine `POST /api/v1/notifications`-Write-Side
- keine `/api/v1/notifications/digest`, `/pending`, `/stats` oder Delivery-/Subscription-Pfade
- keine Notification-Engines, Delivery-Adapter oder externe Zustellung

## Artefakte
- `pilotsuite_core/rootfs/usr/src/app/main.py`
- `pilotsuite_core/rootfs/usr/src/app/dashboard/api/v1/notifications.py`
- `pilotsuite_core/rootfs/usr/src/app/dashboard/api/v1/blueprints_config.py`
- `README.md`
- `docs/openapi.json`
- `docs/openapi.yaml`
- `tests/test_notifications_contract.py`
- `tests/test_contract_inventory_check.py`
- `tests/test_public_api_docs_alignment.py`

## Verifikation
- `pytest -q tests/test_notifications_contract.py tests/test_system_contract.py tests/test_contract_inventory_check.py tests/test_public_api_docs_alignment.py`
- `python3 scripts/contract_inventory_check.py --repo . --light`
- `python3 scripts/contract_inventory_check.py --repo .`

## Nächster exakter Task
- Slice 106 — `/api/v1/notifications/digest` als nächsten kleinsten read-only Follow-up-Slice gegen den historischen Notifications-Contract auditieren und nur den minimalen landingfähigen Scope ziehen.
