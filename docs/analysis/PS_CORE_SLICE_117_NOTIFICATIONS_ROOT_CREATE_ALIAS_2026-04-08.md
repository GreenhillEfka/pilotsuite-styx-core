# PS CORE SLICE 117 — `POST /api/v1/notifications`

## Kontext
- Arbeitsort: `/config/clawd/team/worktrees/pilotsuite-styx-core-current`
- Ausgangspunkt: letzter realer Stand aus `TASKBOARD.md` und `/config/clawd/agents/pilotclaw/TASKLOG.md`
- Pflichtbasis außerhalb des Worktrees bleibt weiter inkonsistent, weil mehrere vorgegebene Steuerdateien fehlen
- Slice 116 hatte bereits den minimalen Create-Write auf `POST /api/v1/notifications/send` gelandet, aber der historische Root-Create-Pfad fehlte weiter als öffentliche Runtime-Surface

## Ziel
Den kleinsten landungsfähigen Root-Create-Alias des historischen `v20`-Notifications-Contracts für `POST /api/v1/notifications` reintroduzieren, ohne schon die größere historische Payload-Kompatibilität mit `source`, `channel` oder `data` mitzuziehen.

## Gelandeter Scope
- `POST /api/v1/notifications` als Root-Create-Alias ergänzt
- Root-Pfad nutzt bewusst dieselbe minimale Validierungs- und Write-Logik wie `POST /api/v1/notifications/send`
- akzeptiert denselben reduzierten JSON-Scope:
  - `title`, `message`
  - optionale `priority`, `type`, `action_data`, `action_url`, `target_devices`, `target_users`, `tags`
- erzeugt genau eine neue Runtime-Notification mit `source = "api"`, `sent = true`, `read = false`, `dismissed = false`
- hält Feed-, Digest- und Stats-Sicht per Read-after-write synchron
- `POST /api/v1/notifications/send` bleibt als expliziter Alias-Pfad weiterhin öffentlich

## Nicht im Scope
- keine historische Integer-`priority`-Kompatibilität
- keine `channel`-/`data`-/`source`-Payload-Reprojektion
- keine Dedup-, Rate-Limit-, Delivery- oder HA-Adapter-Surface

## Artefakte
- `pilotsuite_core/rootfs/usr/src/app/dashboard/api/v1/notifications.py`
- `pilotsuite_core/rootfs/usr/src/app/dashboard/api/v1/blueprints_config.py`
- `tests/test_notifications_contract.py`
- `tests/test_contract_inventory_check.py`
- `README.md`
- `docs/openapi.json`
- `docs/openapi.yaml`
- `docs/analysis/PS_CORE_SLICE_117_NOTIFICATIONS_ROOT_CREATE_ALIAS_2026-04-08.md`
- `TASKBOARD.md`
- `/config/clawd/agents/pilotclaw/TASKLOG.md`

## Evidenz
- `POST /api/v1/notifications` ist im aktuellen `v20`-Worktree jetzt als minimaler Root-Create-Alias öffentlich gelandet
- Root- und Send-Pfad teilen dieselbe Runtime-Wahrheit statt zwei driftanfällige Create-Implementierungen zu pflegen
- fokussierte Contract-Tests decken Erfolgsfall und Invalid-Body auf dem Root-Pfad plus Read-after-write gegen Feed, Digest und Stats ab
- README, `docs/openapi.*` und Blueprint-Inventur führen `/api/v1/notifications` jetzt konsistent mit `GET` und `POST` als öffentliche Runtime-Surface
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_notifications_contract.py tests/test_system_contract.py tests/test_contract_inventory_check.py tests/test_public_api_docs_alignment.py` → **27 passed**
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
- Slice 118 — `POST /api/v1/notifications` auf den kleinsten historischen Payload-Kompatibilitäts-Follow-up für `data` → `action_data` und `channel`-Alias auditieren, ohne Delivery- oder Dedup-Surface wieder einzuführen
