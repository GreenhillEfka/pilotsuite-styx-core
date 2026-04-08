# TASKBOARD — pilotsuite-styx-core-current

## Aktiver Stand
- [x] Slice 135 `widget_positions` Overwrite-Write-`redo_stack`-Ziel-Container-Guard gezogen und gelandet.

## Artefakte
- `pilotsuite_core/rootfs/usr/src/app/dashboard/api/v1/widget_positions.py`
- `tests/test_widget_positions_contract.py`
- `docs/analysis/PS_CORE_SLICE_135_WIDGET_POSITIONS_OVERWRITE_REDO_TARGET_CONTAINER_GUARD_2026-04-08.md`
- `TASKBOARD.md`
- `/config/clawd/agents/pilotclaw/TASKLOG.md`

## Teststatus
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_widget_positions_contract.py tests/test_contract_inventory_check.py tests/test_public_api_docs_alignment.py tests/test_system_contract.py` → **30 passed**
- `/config/clawd/.venv_smoke_gate/bin/python scripts/contract_inventory_check.py --repo . --light` → **OK**
- `/config/clawd/.venv_smoke_gate/bin/python scripts/contract_inventory_check.py --repo .` → **OK**

## Nächster exakter Task
- Slice 136 — `POST /api/v1/widgets/positions` und `POST /api/v1/widgets/positions/bulk` auf den kleinsten expliziten Legacy-/Persistenz-`history`-Quell-Container-Guard auditieren, damit shape-falsche bereits gespeicherte `history`-Container auf Overwrite-Write-Pfaden nicht still weitergetragen werden, ohne neue Surface oder zusätzliche Store-Logik einzuführen.
