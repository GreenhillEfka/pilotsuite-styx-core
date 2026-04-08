# PS Core Slice 122 — `POST /api/v1/notifications/send` Invalid-`channel`-/Invalid-`source`-Paritäts-Guard

## Kontext
- Slice 121 hat den Alias-Write `POST /api/v1/notifications/send` für historische `data`-, `channel`-, `source`- und Integer-`priority`-Hints explizit gegen den Root-Write abgesichert.
- Der kleinste verbleibende Drift-Risikopunkt lag danach auf fehlerhaften Legacy-Hints: Für den Root-Write gab es bereits explizite Invalid-`channel`- und Invalid-`source`-Guards, für `/send` aber noch keinen fokussierten Contract-Guard.
- README und `docs/openapi.*` mussten dafür nicht erweitert werden, weil sich der öffentliche Scope nicht verändert.

## Gelandeter Minimal-Slice
- `notifications.py` bündelt die Legacy-Hint-Validierung für beide Create-Pfade jetzt explizit über eine gemeinsame Helper-Stelle
- fokussierter Parametrized-Contract-Test deckt auf `/api/v1/notifications/send` jetzt explizit ab:
  - Invalid-`channel` als Shape-Fehler
  - Invalid-`channel` als Leerstring
  - Invalid-`source` als Shape-Fehler
  - Invalid-`source` als Leerstring
- fehlerhafte Legacy-Hints erzeugen auf dem Alias-Pfad kontrolliert dieselben `400 invalid_channel`-/`400 invalid_source`-Antworten wie beim Root-Write
- bei Fehlern bleibt der In-Memory-Notification-Stand unverändert und driftet nicht gegen Feed, Digest oder Stats

## Warum kein größerer Umbau
- Root- und Send-Write teilen bereits dieselbe schlanke Create-Logik.
- Der offene Rest war kein neuer Runtime-Scope, sondern die explizite Absicherung gegen spätere Alias-Regressionen.
- Ein größerer Umbau hätte keinen zusätzlichen Contract-Gewinn gebracht.

## Artefakte
- `pilotsuite_core/rootfs/usr/src/app/dashboard/api/v1/notifications.py`
- `tests/test_notifications_contract.py`
- `docs/analysis/PS_CORE_SLICE_122_NOTIFICATIONS_SEND_INVALID_CHANNEL_SOURCE_PARITY_GUARD_2026-04-08.md`
- `TASKBOARD.md`
- `/config/clawd/agents/pilotclaw/TASKLOG.md`

## Tests
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_notifications_contract.py tests/test_system_contract.py tests/test_contract_inventory_check.py tests/test_public_api_docs_alignment.py` → **34 passed**
- `/config/clawd/.venv_smoke_gate/bin/python scripts/contract_inventory_check.py --repo . --light` → **OK**
- `/config/clawd/.venv_smoke_gate/bin/python scripts/contract_inventory_check.py --repo .` → **OK**

## Bekannte Inkonsistenzen
- `/config/clawd/AGENTS.md` fehlt weiterhin
- `/config/clawd/team/PILOTSUITE_EXECUTION_FOUNDATION.md` fehlt weiterhin
- `/config/clawd/team/PILOTSUITE_PROGRESS_LEDGER.md` fehlt weiterhin
- `/config/clawd/team/shared/PILOTSUITE_RECONSOLIDATED_MASTER_WORKPLAN_2026-04-04.md` fehlt weiterhin
- `/config/clawd/team/shared/PILOTSUITE_ONE_LEAD_EXECUTION_STANDARD_2026-04-04.md` fehlt weiterhin
- Slice daher erneut vom letzten realen Artefaktstand aus Taskboard/Tasklog fortgeführt

## Nächster exakter Task
- Slice 123 — `POST /api/v1/notifications/send` auf den kleinsten expliziten Invalid-`action_data`-/Legacy-`data`-Paritäts-Guard auditieren, damit der Alias-Pfad auch bei shape-falschen historischen Payloads nicht gegen den Root-Write driftet, ohne Delivery-, Dedup- oder weitere Manager-Surface wieder einzuführen.
