# PS Core Slice 114 — `POST /api/v1/notifications/<notification_id>/read` minimaler Notification-Read-Ack-Follow-up

## Kontext
- Nach Slice 113 war die minimale Subscription-Surface für Re-Register bestehender Devices wieder konsistent gelandet.
- Der nächste kleinste historische Notifications-Write-Follow-up war das Quittieren genau einer bestehenden Notification als gelesen.
- Die Pflichtbasis-Dateien außerhalb des Worktrees fehlen weiterhin, daher wurde der Slice erneut direkt vom letzten realen Artefaktstand in Taskboard und Tasklog fortgeführt.

## Entscheidung
- Gelandet wird nur der kleinste belastbare Read-Ack-Slice: `POST /api/v1/notifications/<notification_id>/read` markiert genau eine bestehende Notification als gelesen.
- Der Scope bleibt bewusst schmal: keine neue Dismiss-, Read-All-, Delivery-, Persistenz-, Manager- oder Auth-Surface.
- Read-after-write gegen Feed, Digest und Stats bleibt die führende Kontrolloberfläche.

## Umsetzung
- `notifications.py` hält den Runtime-Bestand jetzt zusätzlich über `_DEFAULT_NOTIFICATIONS`, damit Mutations-Tests deterministisch auf den gleichen Basissnapshot zurücksetzen können
- neuer Minimalpfad `POST /api/v1/notifications/<notification_id>/read` markiert bekannte Notifications idempotent per `read = true`
- unbekannte Notification-IDs liefern kontrolliert `404 notification_not_found`
- fokussierter Contract-Test deckt den Read-Ack plus synchronen Drift-Schutz für `/api/v1/notifications`, `/api/v1/notifications/digest` und `/api/v1/notifications/stats` ab
- README, OpenAPI und Blueprint-Inventur führen den Pfad jetzt konsistent als öffentliche Runtime-Surface

## Artefakte
- `pilotsuite_core/rootfs/usr/src/app/dashboard/api/v1/notifications.py`
- `pilotsuite_core/rootfs/usr/src/app/dashboard/api/v1/blueprints_config.py`
- `tests/test_notifications_contract.py`
- `tests/test_contract_inventory_check.py`
- `tests/test_public_api_docs_alignment.py`
- `README.md`
- `docs/openapi.json`
- `docs/openapi.yaml`
- `docs/analysis/PS_CORE_SLICE_114_NOTIFICATIONS_MARK_READ_ENDPOINT_2026-04-08.md`
- `TASKBOARD.md`
- `/config/clawd/agents/pilotclaw/TASKLOG.md`

## Tests
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_notifications_contract.py tests/test_system_contract.py tests/test_contract_inventory_check.py tests/test_public_api_docs_alignment.py`
- `/config/clawd/.venv_smoke_gate/bin/python scripts/contract_inventory_check.py --repo . --light`
- `/config/clawd/.venv_smoke_gate/bin/python scripts/contract_inventory_check.py --repo .`

## Nächster exakter Task
- Slice 115 — `DELETE /api/v1/notifications/<notification_id>` als nächsten kleinsten Notification-Dismiss-Follow-up gegen den historischen Notifications-Contract auditieren und nur den minimalen landingfähigen Scope ziehen.
