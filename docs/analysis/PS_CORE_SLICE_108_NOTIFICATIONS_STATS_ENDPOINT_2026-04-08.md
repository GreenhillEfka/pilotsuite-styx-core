# PS Core Slice 108 — `/api/v1/notifications/stats` read-only Follow-up

## Kontext
- Nach Slice 107 war der historische Notifications-Feed inklusive Digest und Pending-Queue wieder öffentlich gelandet.
- Der kleinste noch offene read-only Follow-up-Pfad aus derselben Contract-Familie war `/api/v1/notifications/stats`.
- Die Pflichtbasis-Dateien außerhalb des Worktrees fehlen weiter, deshalb wurde erneut vom letzten echten Artefaktstand aus Taskboard, Tasklog und Runtime fortgesetzt.

## Entscheidung
- `/api/v1/notifications/stats` wird als kleinster read-only Metrics-Follow-up-Slice gelandet.
- Der Scope bleibt bewusst schmal: nur eine Statistik-Sicht auf Basis des bereits gelandeten Notifications-Feeds, keine Write-, Delivery-, Subscription- oder HA-Adapter-Reintroduction.
- Der Slice nutzt die bereits öffentliche Feed-Wahrheit und führt keine zweite Notification-Engine ein.

## Gelandete Änderungen
- neuer read-only Endpoint `GET /api/v1/notifications/stats`
- minimale Statistik-Ableitung aus dem bestehenden In-Memory-Feed ergänzt (`total_notifications`, `unread_count`, `by_source`, `by_priority`, `by_type`)
- Blueprint-Inventur um den neuen öffentlichen Pfad erweitert
- README und `docs/openapi.*` auf die neue öffentliche Runtime-Surface gezogen
- fokussierte Contract- und Alignment-Guards auf den neuen Pfad erweitert

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

## Tests
- `pytest -q tests/test_notifications_contract.py tests/test_system_contract.py tests/test_contract_inventory_check.py tests/test_public_api_docs_alignment.py`
- `python3 scripts/contract_inventory_check.py --repo . --light`
- `python3 scripts/contract_inventory_check.py --repo .`

## Nächster exakter Task
- Slice 109 — `/api/v1/notifications/subscriptions` als nächsten kleinsten read-only Follow-up-Slice gegen den historischen Notifications-Contract auditieren und nur den minimalen landingfähigen Scope ziehen.
