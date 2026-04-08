# TASKBOARD — pilotsuite-styx-core-current

## Aktiver Stand
- [x] Slice 109 `widget_positions` Persisted-Store-Härtung als kleinsten noch offenen Robustheitsrest der aktiven `dashboard.api.v1.widget_positions`-Surface gelandet.

## Artefakte
- `pilotsuite_core/rootfs/usr/src/app/dashboard/api/v1/widget_positions.py`
- `tests/test_widget_positions_contract.py`
- `docs/analysis/PS_CORE_SLICE_109_WIDGET_POSITIONS_PERSISTED_STORE_HARDENING_2026-04-08.md`
- `TASKBOARD.md`
- `/config/clawd/agents/pilotclaw/TASKLOG.md`

## Teststatus
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_widget_positions_contract.py tests/test_contract_inventory_check.py tests/test_public_api_docs_alignment.py tests/test_system_contract.py`
- `/config/clawd/.venv_smoke_gate/bin/python scripts/contract_inventory_check.py --repo . --light`
- `/config/clawd/.venv_smoke_gate/bin/python scripts/contract_inventory_check.py --repo .`

## Nächster exakter Task
- Slice 110 — `/api/v1/notifications/subscriptions` als nächsten kleinsten read-only Follow-up-Slice gegen den historischen Notifications-Contract auditieren und nur den minimalen landingfähigen Scope ziehen.
