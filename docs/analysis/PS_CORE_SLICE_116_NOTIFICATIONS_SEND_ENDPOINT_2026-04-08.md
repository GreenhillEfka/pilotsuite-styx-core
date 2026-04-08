# PS CORE SLICE 116 — `POST /api/v1/notifications/send`

## Kontext
- Arbeitsort: `/config/clawd/team/worktrees/pilotsuite-styx-core-current`
- Ausgangspunkt: letzter realer Stand aus `TASKBOARD.md` und `/config/clawd/agents/pilotclaw/TASKLOG.md`
- Pflichtbasis außerhalb des Worktrees bleibt weiter inkonsistent, weil mehrere vorgegebene Steuerdateien fehlen

## Ziel
Den kleinsten landungsfähigen Notification-Create-Follow-up des historischen `v20`-Contracts für `POST /api/v1/notifications/send` reintroduzieren, ohne Delivery-Adapter, HA-Bridges oder größere Manager-Surface mitzuziehen.

## Gelandeter Scope
- `POST /api/v1/notifications/send` als minimaler API-Write-Slice ergänzt
- akzeptiert nur den kleinsten belastbaren JSON-Scope:
  - `title`, `message`
  - optionale `priority`, `type`, `action_data`, `action_url`, `target_devices`, `target_users`, `tags`
- validiert Pflichtfelder und den kleinsten historischen Enum-/Shape-Rahmen für Priorität, Typ und Listenfelder
- erzeugt genau eine neue Runtime-Notification mit `source = "api"`, `sent = true`, `read = false`, `dismissed = false`
- hält Feed-, Digest- und Stats-Sicht per Read-after-write synchron
- zieht bewusst keine zusätzliche Pending-Queue-Simulation, HA-Zustellung oder Root-POST-Alias-Surface mit

## Artefakte
- `pilotsuite_core/rootfs/usr/src/app/dashboard/api/v1/notifications.py`
- `pilotsuite_core/rootfs/usr/src/app/dashboard/api/v1/blueprints_config.py`
- `tests/test_notifications_contract.py`
- `tests/test_contract_inventory_check.py`
- `tests/test_public_api_docs_alignment.py`
- `README.md`
- `docs/openapi.json`
- `docs/openapi.yaml`
- `docs/analysis/PS_CORE_SLICE_116_NOTIFICATIONS_SEND_ENDPOINT_2026-04-08.md`
- `TASKBOARD.md`
- `/config/clawd/agents/pilotclaw/TASKLOG.md`

## Evidenz
- `POST /api/v1/notifications/send` ist im aktuellen `v20`-Worktree als kleinster historisch belastbarer Create-/Send-Follow-up gelandet
- der Slice bleibt bewusst lokal auf die bestehende In-Memory-Notifications-Wahrheit beschränkt statt alte Manager-/HA-Delivery-Pfade wieder einzuführen
- fokussierte Contract-Tests decken Erfolgsfall plus Validierungsfehler für Body, Pflichtfelder, Priority und Listen-Shapes gegen Drift ab
- README, `docs/openapi.*` und Blueprint-Inventur führen `/api/v1/notifications/send` jetzt konsistent als öffentliche Runtime-Surface
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_notifications_contract.py tests/test_system_contract.py tests/test_contract_inventory_check.py tests/test_public_api_docs_alignment.py` → **26 passed**
- `/config/clawd/.venv_smoke_gate/bin/python scripts/contract_inventory_check.py --repo . --light` → **OK**
- `/config/clawd/.venv_smoke_gate/bin/python scripts/contract_inventory_check.py --repo .` → **OK**

## Bekannte Inkonsistenz
- `/config/clawd/AGENTS.md` fehlt weiterhin
- `/config/clawd/team/PILOTSUITE_EXECUTION_FOUNDATION.md` fehlt weiterhin
- `/config/clawd/team/PILOTSUITE_PROGRESS_LEDGER.md` fehlt weiterhin
- `/config/clawd/team/shared/PILOTSUITE_RECONSOLIDATED_MASTER_WORKPLAN_2026-04-04.md` fehlt weiterhin
- `/config/clawd/team/shared/PILOTSUITE_ONE_LEAD_EXECUTION_STANDARD_2026-04-04.md` fehlt weiterhin
- Slice deshalb erneut vom letzten realen Artefaktstand aus Taskboard/Tasklog fortgeführt

## Nächster exakter Task
- Slice 117 — `POST /api/v1/notifications` als kleinsten Root-Create-Alias-Follow-up gegen denselben historischen Notifications-Contract auditieren und nur den minimalen landingfähigen Scope ziehen
