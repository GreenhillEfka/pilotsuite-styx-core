# TASKBOARD — pilotsuite-styx-core-current

## Aktiver Stand
- [x] Slice 108 `/api/v1/notifications/stats` als kleinsten read-only Metrics-Follow-up-Slice aus dem historischen `v20`-Notifications-Contract wieder öffentlich gelandet.

## Artefakte
- `README.md`
- `pilotsuite_core/rootfs/usr/src/app/dashboard/api/v1/notifications.py`
- `pilotsuite_core/rootfs/usr/src/app/dashboard/api/v1/blueprints_config.py`
- `docs/openapi.json`
- `docs/openapi.yaml`
- `tests/test_notifications_contract.py`
- `tests/test_contract_inventory_check.py`
- `tests/test_public_api_docs_alignment.py`
- `docs/analysis/PS_CORE_SLICE_108_NOTIFICATIONS_STATS_ENDPOINT_2026-04-08.md`

## Teststatus
- `pytest -q tests/test_notifications_contract.py tests/test_system_contract.py tests/test_contract_inventory_check.py tests/test_public_api_docs_alignment.py`
- `python3 scripts/contract_inventory_check.py --repo . --light`
- `python3 scripts/contract_inventory_check.py --repo .`

## Nächster exakter Task
- Slice 109 — `/api/v1/notifications/subscriptions` als nächsten kleinsten read-only Follow-up-Slice gegen den historischen Notifications-Contract auditieren und nur den minimalen landingfähigen Scope ziehen.
