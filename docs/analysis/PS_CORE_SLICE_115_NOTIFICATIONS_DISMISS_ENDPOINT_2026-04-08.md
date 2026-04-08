# PS_CORE_SLICE_115_NOTIFICATIONS_DISMISS_ENDPOINT_2026-04-08

## Scope
- kleinster historisch belastbarer Dismiss-Follow-up für den bereits gelandeten Notifications-Root-Slice
- nur `DELETE /api/v1/notifications/{notification_id}` gegen den bestehenden In-Memory-Snapshot
- keine Send-, Clear-, Delivery-, Manager- oder HA-Adapter-Surface mitgezogen

## Implementation
- `dashboard.api.v1.notifications` ergänzt einen minimalen `DELETE /api/v1/notifications/<notification_id>`-Write-Pfad
- bekannte Notification-IDs werden nur als `dismissed = true` markiert und im bestehenden Response-Schema zurückgegeben
- unbekannte IDs liefern kontrolliert `404 notification_not_found`
- Feed und Digest bleiben per Read-after-write auf derselben Notification-Wahrheit synchron

## Artefakte
- `pilotsuite_core/rootfs/usr/src/app/dashboard/api/v1/notifications.py`
- `pilotsuite_core/rootfs/usr/src/app/dashboard/api/v1/blueprints_config.py`
- `tests/test_notifications_contract.py`
- `tests/test_contract_inventory_check.py`
- `tests/test_public_api_docs_alignment.py`
- `README.md`
- `docs/openapi.json`
- `docs/openapi.yaml`
- `docs/analysis/PS_CORE_SLICE_115_NOTIFICATIONS_DISMISS_ENDPOINT_2026-04-08.md`
- `TASKBOARD.md`
- `/config/clawd/agents/pilotclaw/TASKLOG.md`

## Verification
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_notifications_contract.py tests/test_system_contract.py tests/test_contract_inventory_check.py tests/test_public_api_docs_alignment.py` → `24 passed`
- `/config/clawd/.venv_smoke_gate/bin/python scripts/contract_inventory_check.py --repo . --light` → `contract inventory OK (light runtime check)`
- `/config/clawd/.venv_smoke_gate/bin/python scripts/contract_inventory_check.py --repo .` → `contract inventory OK (runtime + OpenAPI + README check)`
