# PS Core Slice 112 — `POST /api/v1/notifications/unsubscribe` minimaler Subscription-Write-Follow-up

## Kontext
- Nach Slice 111 war der minimale Update-Pfad für bestehende Device-Subscriptions unter `/api/v1/notifications/subscriptions/<device_id>` wieder öffentlich gelandet.
- Der nächste kleinste historische Subscription-Write-Follow-up im alten Notifications-Contract war `POST /unsubscribe`.
- Die Pflichtbasis-Dateien außerhalb des Worktrees fehlen weiterhin, daher wurde der Slice erneut direkt vom letzten realen Artefaktstand in Taskboard und Tasklog fortgeführt.

## Entscheidung
- Gelandet wird nur `POST /api/v1/notifications/unsubscribe` als minimaler Remove-Pfad für bestehende Device-Subscriptions.
- Der Scope bleibt bewusst schmal: nur `device_id` validieren, genau ein vorhandenes Device aus dem In-Memory-Subscription-Snapshot entfernen, Read-after-write stabil halten.
- Keine Reintroduction von `subscribe`, HA-Registration, Notification-Manager, DB-Persistenz oder zusätzlicher Auth-/Routing-Surface in diesem Slice.

## Umsetzung
- neuer minimaler Write-Endpoint `POST /api/v1/notifications/unsubscribe`
- `invalid_body` bei nicht-diktförmigem JSON-Body, `invalid_device_id` bei leerem oder nicht-string `device_id`
- `device_not_found` bei unbekanntem Gerät, statt stillem Erfolgs-Ack
- neuer interner Helper entfernt genau einen Subscription-Eintrag aus `_SUBSCRIPTIONS`
- Contract-Test deckt Erfolgsfall, Listen-Synchronität und Negativpfade ab
- README, OpenAPI und Blueprint-Inventur dokumentieren den neuen öffentlichen Pfad konsistent

## Artefakte
- `pilotsuite_core/rootfs/usr/src/app/dashboard/api/v1/notifications.py`
- `pilotsuite_core/rootfs/usr/src/app/dashboard/api/v1/blueprints_config.py`
- `README.md`
- `docs/openapi.json`
- `docs/openapi.yaml`
- `tests/test_notifications_contract.py`
- `tests/test_contract_inventory_check.py`
- `tests/test_public_api_docs_alignment.py`
- `TASKBOARD.md`
- `/config/clawd/agents/pilotclaw/TASKLOG.md`

## Tests
- `pytest -q tests/test_notifications_contract.py tests/test_system_contract.py tests/test_contract_inventory_check.py tests/test_public_api_docs_alignment.py`
- `python scripts/contract_inventory_check.py --repo . --light`
- `python scripts/contract_inventory_check.py --repo .`

## Nächster exakter Task
- Slice 113 — `POST /api/v1/notifications/subscribe` als nächsten kleinsten Subscription-Write-Follow-up gegen den historischen Notifications-Contract auditieren und nur den minimalen landingfähigen Scope ziehen.
