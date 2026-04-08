# TASKBOARD — pilotsuite-styx-core-current

## Aktiver Stand
- [x] Slice 120 `POST /api/v1/notifications` für historische Integer-`priority`-Payload-Kompatibilität ohne Dedup-, Delivery- oder weitere Manager-Surface gehärtet und gelandet.

## Artefakte
- `pilotsuite_core/rootfs/usr/src/app/dashboard/api/v1/notifications.py`
- `tests/test_notifications_contract.py`
- `README.md`
- `docs/openapi.json`
- `docs/openapi.yaml`
- `docs/analysis/PS_CORE_SLICE_120_NOTIFICATIONS_ROOT_INTEGER_PRIORITY_COMPAT_2026-04-08.md`
- `TASKBOARD.md`
- `/config/clawd/agents/pilotclaw/TASKLOG.md`

## Teststatus
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_notifications_contract.py tests/test_system_contract.py tests/test_contract_inventory_check.py tests/test_public_api_docs_alignment.py` → **29 passed**
- `/config/clawd/.venv_smoke_gate/bin/python scripts/contract_inventory_check.py --repo . --light` → **OK**
- `/config/clawd/.venv_smoke_gate/bin/python scripts/contract_inventory_check.py --repo .` → **OK**

## Nächster exakter Task
- Slice 121 — `POST /api/v1/notifications/send` auf den kleinsten expliziten Integer-`priority`-Contract-Paritäts-Guard auditieren, damit der Alias-Pfad nicht gegen den Root-Write driftet, ohne Delivery-, Dedup- oder weitere Manager-Surface wieder einzuführen.
