# PS Core Slice 107 — `/api/v1/notifications/pending` read-only Follow-up

## Kontext
- Nach Slice 106 war der historische Notifications-Feed inklusive Digest wieder öffentlich gelandet.
- Der kleinste noch offene Follow-up-Pfad aus derselben Contract-Familie war `/api/v1/notifications/pending`.
- Die Pflichtbasis-Dateien außerhalb des Worktrees fehlen weiter, deshalb wurde erneut vom letzten echten Artefaktstand aus Taskboard, Tasklog und Runtime fortgesetzt.

## Entscheidung
- `/api/v1/notifications/pending` wird als kleinster read-only Delivery-Follow-up-Slice gelandet.
- Der Scope bleibt bewusst schmal: nur eine Pending-Queue-Sicht, keine Stats-, Write-, Delivery- oder Subscription-Reintroduction.
- Der Slice bleibt vom bestehenden Feed getrennt, damit die bereits gelandeten `/api/v1/notifications`- und `/digest`-Contracts unverändert stabil bleiben.

## Gelandete Änderungen
- neuer read-only Endpoint `GET /api/v1/notifications/pending`
- minimale Pending-Queue-Snapshot-Daten im Notifications-Blueprint ergänzt
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
- Slice 108 — `/api/v1/notifications/stats` als nächsten kleinsten read-only Follow-up-Slice gegen den historischen Notifications-Contract auditieren und nur den minimalen landingfähigen Scope ziehen.
