# PS Core Slice 121 — `POST /api/v1/notifications/send` Integer-`priority`-Paritäts-Guard

## Kontext
- Slice 120 hat den Root-Write `POST /api/v1/notifications` für historische Integer-`priority`-Payloads gehärtet.
- README und `docs/openapi.*` beschreiben Root- und Send-Write bereits mit demselben minimalen Legacy-Scope (`data`, `channel`, `source`, Integer-`priority`).
- Der kleinste noch offene Drift-Risikopunkt war ein expliziter Contract-Guard auf dem Alias-Pfad `/api/v1/notifications/send`.

## Gelandeter Minimal-Slice
- fokussierter Contract-Test für `POST /api/v1/notifications/send` ergänzt
- der Guard deckt denselben Minimal-Scope wie der Root-Write explizit ab:
  - historische `data`-Payload als Alias auf `action_data`
  - historischer `channel`-Hint wird akzeptiert, aber nicht in die öffentliche Runtime-Response reintroduziert
  - historischer `source`-Hint wird lowercase-normalisiert
  - historische Integer-`priority` wird kontrolliert auf die bestehende String-Wahrheit normalisiert
- Feed, Digest und Stats bleiben auch auf dem Alias-Pfad per Read-after-write synchron

## Warum kein größerer Umbau
- Root- und Send-Write laufen bereits über dieselbe Create-Helferlogik in `notifications.py`.
- Ein weiterer Runtime-Umbau hätte keinen zusätzlichen Contract-Gewinn gebracht.
- Der kleinste landingfähige Slice war daher die explizite Paritäts-Absicherung gegen späteren Alias-Drift.

## Artefakte
- `tests/test_notifications_contract.py`
- `docs/analysis/PS_CORE_SLICE_121_NOTIFICATIONS_SEND_INTEGER_PRIORITY_PARITY_GUARD_2026-04-08.md`
- `TASKBOARD.md`
- `/config/clawd/agents/pilotclaw/TASKLOG.md`

## Tests
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_notifications_contract.py tests/test_system_contract.py tests/test_contract_inventory_check.py tests/test_public_api_docs_alignment.py` → **30 passed**
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
- Slice 122 — `POST /api/v1/notifications/send` auf den kleinsten expliziten Invalid-`channel`-/Invalid-`source`-Paritäts-Guard auditieren, damit der Alias-Pfad auch bei fehlerhaften Legacy-Hints nicht gegen den Root-Write driftet, ohne Delivery-, Dedup- oder weitere Manager-Surface wieder einzuführen.
