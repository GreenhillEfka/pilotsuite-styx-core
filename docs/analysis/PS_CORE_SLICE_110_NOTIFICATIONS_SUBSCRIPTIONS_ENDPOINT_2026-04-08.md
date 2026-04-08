# PS Core Slice 110 — `/api/v1/notifications/subscriptions` read-only Follow-up

## Kontext
- Nach Slice 109 war der aktive `widget_positions`-Rest sauber geschlossen und der Notifications-Block wieder der kleinste offene Contract-Follow-up.
- Der kleinste noch offene historische Notifications-Pfad mit read-only Scope war `/api/v1/notifications/subscriptions`.
- Die Pflichtbasis-Dateien außerhalb des Worktrees fehlen weiter, deshalb wurde erneut vom letzten echten Artefaktstand aus Taskboard, Tasklog und Runtime fortgesetzt.

## Entscheidung
- `/api/v1/notifications/subscriptions` wird als kleinster read-only Subscription-Follow-up-Slice gelandet.
- Der Scope bleibt bewusst schmal: nur ein statischer Device-Subscription-Snapshot auf Basis des historischen Contracts, keine Subscribe-, Unsubscribe- oder Preference-Write-Side.
- Die Response bleibt an die aktuelle schlanke Runtime-Form (`ok`, `count`, Listenpayload) angepasst statt die alte Manager-/Engine-Struktur wieder einzuführen.

## Gelandete Änderungen
- neuer read-only Endpoint `GET /api/v1/notifications/subscriptions`
- minimale Subscription-Snapshot-Daten im Notifications-Blueprint ergänzt (`device_id`, `device_name`, `device_type`, masked `push_token`, `enabled`, `preferences`, `ha_entity_id`, `last_seen`, `created_at`)
- zusätzliche Kennzahl `enabled_count` für den kleinsten stabilen Überblick ergänzt
- Blueprint-Inventur um den neuen öffentlichen Pfad erweitert
- README und `docs/openapi.*` auf die neue öffentliche Runtime-Surface gezogen
- fokussierte Contract- und Alignment-Guards auf den neuen Pfad erweitert

## Artefakte
- `pilotsuite_core/rootfs/usr/src/app/dashboard/api/v1/notifications.py`
- `pilotsuite_core/rootfs/usr/src/app/dashboard/api/v1/blueprints_config.py`
- `README.md`
- `docs/openapi.json`
- `docs/openapi.yaml`
- `docs/analysis/PS_CORE_SLICE_110_NOTIFICATIONS_SUBSCRIPTIONS_ENDPOINT_2026-04-08.md`
- `tests/test_notifications_contract.py`
- `tests/test_contract_inventory_check.py`
- `tests/test_public_api_docs_alignment.py`
- `TASKBOARD.md`

## Tests
- `pytest -q tests/test_notifications_contract.py tests/test_system_contract.py tests/test_contract_inventory_check.py tests/test_public_api_docs_alignment.py`
- `python3 scripts/contract_inventory_check.py --repo . --light`
- `python3 scripts/contract_inventory_check.py --repo .`

## Nächster exakter Task
- Slice 111 — `/api/v1/notifications/subscriptions/<device_id>` als nächsten kleinsten Subscription-Follow-up gegen den historischen Notifications-Contract auditieren und nur den minimalen landingfähigen Scope ziehen.
