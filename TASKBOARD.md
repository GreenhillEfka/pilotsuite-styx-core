# TASKBOARD — pilotsuite-styx-core-current

## Aktiver Stand
- [x] Slice 111 `/api/v1/notifications/subscriptions/<device_id>` als kleinsten noch offenen Subscription-Write-Follow-up der aktiven Notifications-Contract-Surface gelandet.

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
- `/config/clawd/agents/pilotclaw/TASKLOG.md`

## Teststatus
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_notifications_contract.py tests/test_system_contract.py tests/test_contract_inventory_check.py tests/test_public_api_docs_alignment.py`
- `/config/clawd/.venv_smoke_gate/bin/python scripts/contract_inventory_check.py --repo . --light`
- `/config/clawd/.venv_smoke_gate/bin/python scripts/contract_inventory_check.py --repo .`

## Nächster exakter Task
- Slice 112 — `POST /api/v1/notifications/unsubscribe` als nächsten kleinsten Subscription-Write-Follow-up gegen den historischen Notifications-Contract auditieren und nur den minimalen landingfähigen Scope ziehen.
