# TASKBOARD — pilotsuite-styx-core-current

## Aktiver Stand
- [x] Slice 118 `POST /api/v1/notifications` für historische `data` → `action_data`-Kompatibilität und `channel`-Hint ohne Delivery-Reintro gehärtet und gelandet.

## Artefakte
- `pilotsuite_core/rootfs/usr/src/app/dashboard/api/v1/notifications.py`
- `tests/test_notifications_contract.py`
- `README.md`
- `docs/openapi.json`
- `docs/openapi.yaml`
- `docs/analysis/PS_CORE_SLICE_118_NOTIFICATIONS_ROOT_LEGACY_PAYLOAD_COMPAT_2026-04-08.md`
- `TASKBOARD.md`
- `/config/clawd/agents/pilotclaw/TASKLOG.md`

## Teststatus
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_notifications_contract.py tests/test_system_contract.py tests/test_contract_inventory_check.py tests/test_public_api_docs_alignment.py`
- `/config/clawd/.venv_smoke_gate/bin/python scripts/contract_inventory_check.py --repo . --light`
- `/config/clawd/.venv_smoke_gate/bin/python scripts/contract_inventory_check.py --repo .`

## Nächster exakter Task
- Slice 119 — `POST /api/v1/notifications` auf den kleinsten historischen `source`-Payload-Kompatibilitäts-Follow-up auditieren, ohne Dedup-, Rate-Limit- oder Delivery-Surface wieder einzuführen.
