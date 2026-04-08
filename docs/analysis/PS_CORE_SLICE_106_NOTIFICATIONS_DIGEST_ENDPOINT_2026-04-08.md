# PS Core Slice 106 — `/api/v1/notifications/digest` read-only Follow-up

## Ausgangslage
- Nach Slice 105 war der historische Notifications-Root-Feed unter `/api/v1/notifications` wieder öffentlich gelandet.
- Der nächstkleinere historische Follow-up-Pfad war der read-only Summary-Endpoint `/api/v1/notifications/digest`.
- Die verpflichtenden Team-Basisdokumente fehlten weiterhin am erwarteten Pfad; der Slice wurde daher erneut vom letzten realen Artefaktstand in Taskboard/Tasklog fortgeführt.

## Audit
- Die Git-Historie führte für Notifications zusätzlich Write-, Pending- und Stats-Pfade.
- Der kleinste landingfähige nächste Slice ist nur der Digest, weil er direkt auf dem bereits gelandeten Feed aufsetzt und keinen Delivery- oder Engine-Zustand voraussetzt.
- Der historische Contract verlangte nur eine verdichtete Summary-Sicht, keine neue Write-Side.

## Landing-Scope
- `GET /api/v1/notifications/digest`
- read-only Digest direkt aus dem bereits gelandeten In-Memory-Feed abgeleitet
- Summary-Felder: `period`, `total`, `unread`, `read`, `dismissed`, `sent`, `by_type`, `by_source`, `by_priority`, `latest_timestamp`
- Contract-/README-/OpenAPI-Inventur auf den neuen öffentlichen Follow-up-Pfad rebased

## Nicht Teil dieses Slices
- keine `POST /api/v1/notifications`-Write-Side
- keine `/api/v1/notifications/pending`- oder `/api/v1/notifications/stats`-Pfade
- keine Delivery-Queues, Notification-Engines oder Subscription-/Push-Adapter

## Artefakte
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
- Slice 107 — `/api/v1/notifications/pending` als nächsten kleinsten read-only Follow-up-Slice gegen den historischen Notifications-Contract auditieren und nur den minimalen landingfähigen Scope ziehen.
