# PS Core Slice 111 — `/api/v1/notifications/subscriptions/<device_id>` minimaler Subscription-Write-Follow-up

## Kontext
- Nach Slice 110 war der read-only Subscription-Snapshot unter `/api/v1/notifications/subscriptions` wieder öffentlich gelandet.
- Der nächste kleinste echte historische Follow-up am selben Pfad war nicht ein weiterer Read-Slice, sondern `PUT /subscriptions/<device_id>` für bestehende Device-Subscriptions.
- Die Pflichtbasis-Dateien außerhalb des Worktrees fehlen weiter, deshalb wurde erneut vom letzten echten Artefaktstand aus Taskboard, Tasklog und Runtime fortgesetzt.

## Entscheidung
- Gelandet wird nur der kleinste Update-Scope für bestehende Geräte unter `PUT /api/v1/notifications/subscriptions/<device_id>`.
- Der Write-Scope bleibt bewusst schmal: nur `enabled` und bekannte Preference-Flags (`notify_mood`, `notify_alerts`, `notify_suggestions`, `notify_system`).
- Keine Reintroduction von Subscribe-, Unsubscribe-, HA-Register- oder Manager-/DB-Persistenzpfaden in diesem Slice.
- Die Response bleibt an die aktuelle schlanke Runtime-Form angepasst (`ok`, `subscription`) statt die historische `success/data`-Hülle wieder einzuführen.

## Gelandete Änderungen
- neuer minimaler Write-Endpoint `PUT /api/v1/notifications/subscriptions/<device_id>`
- kontrollierte Validierung für JSON-Body, `enabled`-Bool und bekannte Preference-Flags ergänzt
- 404-Pfad für unbekannte `device_id` ergänzt statt stiller Erfolgs-Acks
- fokussierter Read-after-write-Pfad hält Listen-Snapshot und `enabled_count` nach Mutation synchron
- Blueprint-Inventur, README und `docs/openapi.*` auf die neue öffentliche Runtime-Surface erweitert
- fokussierte Contract- und Alignment-Guards auf den neuen Pfad erweitert

## Artefakte
- `pilotsuite_core/rootfs/usr/src/app/dashboard/api/v1/notifications.py`
- `pilotsuite_core/rootfs/usr/src/app/dashboard/api/v1/blueprints_config.py`
- `README.md`
- `docs/openapi.json`
- `docs/openapi.yaml`
- `docs/analysis/PS_CORE_SLICE_111_NOTIFICATIONS_SUBSCRIPTION_UPDATE_ENDPOINT_2026-04-08.md`
- `tests/test_notifications_contract.py`
- `tests/test_contract_inventory_check.py`
- `tests/test_public_api_docs_alignment.py`
- `TASKBOARD.md`

## Tests
- `pytest -q tests/test_notifications_contract.py tests/test_system_contract.py tests/test_contract_inventory_check.py tests/test_public_api_docs_alignment.py`
- `python3 scripts/contract_inventory_check.py --repo . --light`
- `python3 scripts/contract_inventory_check.py --repo .`

## Nächster exakter Task
- Slice 112 — `POST /api/v1/notifications/unsubscribe` als nächsten kleinsten Subscription-Write-Follow-up gegen den historischen Notifications-Contract auditieren und nur den minimalen landingfähigen Scope ziehen.
