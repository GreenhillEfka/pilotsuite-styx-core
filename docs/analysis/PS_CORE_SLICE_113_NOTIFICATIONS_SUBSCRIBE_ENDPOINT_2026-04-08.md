# PS Core Slice 113 — `POST /api/v1/notifications/subscribe` minimaler Subscription-Re-Register-Follow-up

## Kontext
- Nach Slice 112 war der minimale Remove-Pfad für bestehende Device-Subscriptions unter `/api/v1/notifications/unsubscribe` wieder öffentlich gelandet.
- `POST /api/v1/notifications/subscribe` war bereits als minimaler Add-/Refresh-Pfad im Worktree vorhanden, hatte aber noch eine Contract-Lücke beim Re-Register deaktivierter Devices.
- Die Pflichtbasis-Dateien außerhalb des Worktrees fehlen weiterhin, daher wurde der Slice erneut direkt vom letzten realen Artefaktstand in Taskboard und Tasklog fortgeführt.

## Entscheidung
- Gelandet wird nur die kleinste belastbare Härtung des bestehenden Subscribe-Slices: Re-Register eines bekannten Devices aktiviert die Subscription wieder.
- Der Scope bleibt bewusst schmal: keine neue Manager-, HA-, Auth-, Persistenz- oder zusätzliche Notification-Mutations-Surface.
- Read-after-write gegen `/api/v1/notifications/subscriptions` bleibt die führende Kontrolloberfläche.

## Umsetzung
- bestehender `POST /api/v1/notifications/subscribe`-Pfad reaktiviert bekannte Devices jetzt deterministisch über `enabled = true`
- bestehende Upsert-/Refresh-Semantik für `device_name`, `device_type`, `push_token`, `ha_entity_id`, `preferences` und `last_seen` bleibt erhalten
- neuer fokussierter Contract-Test deckt Re-Register eines zuvor deaktivierten Devices inklusive synchronem `enabled_count` im Listen-Snapshot ab
- README und OpenAPI beschreiben den Pfad jetzt explizit als Create-/Refresh-/Re-Enable-Surface

## Artefakte
- `pilotsuite_core/rootfs/usr/src/app/dashboard/api/v1/notifications.py`
- `tests/test_notifications_contract.py`
- `README.md`
- `docs/openapi.json`
- `docs/openapi.yaml`
- `docs/analysis/PS_CORE_SLICE_113_NOTIFICATIONS_SUBSCRIBE_ENDPOINT_2026-04-08.md`
- `TASKBOARD.md`
- `/config/clawd/agents/pilotclaw/TASKLOG.md`

## Tests
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_notifications_contract.py tests/test_system_contract.py tests/test_contract_inventory_check.py tests/test_public_api_docs_alignment.py`
- `/config/clawd/.venv_smoke_gate/bin/python scripts/contract_inventory_check.py --repo . --light`
- `/config/clawd/.venv_smoke_gate/bin/python scripts/contract_inventory_check.py --repo .`

## Nächster exakter Task
- Slice 114 — `POST /api/v1/notifications/<notification_id>/read` als nächsten kleinsten Notification-Write-Follow-up gegen den historischen Notifications-Contract auditieren und nur den minimalen landingfähigen Scope ziehen.
