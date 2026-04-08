# PS CORE SLICE 120 — `POST /api/v1/notifications` Integer-`priority`-Payload-Kompatibilität

## Kontext
- Arbeitsort: `/config/clawd/team/worktrees/pilotsuite-styx-core-current`
- Ausgangspunkt: letzter realer Stand aus `TASKBOARD.md` und `/config/clawd/agents/pilotclaw/TASKLOG.md`
- Pflichtbasis außerhalb des Worktrees bleibt weiter inkonsistent, weil mehrere vorgegebene Steuerdateien fehlen
- Slice 119 hatte historische `source`-Payloads bereits kompatibel gemacht, aber historische Integer-`priority`-Werte wurden im Root-Write noch nicht kontrolliert auf die schlanke Runtime-Wahrheit normalisiert

## Ziel
Den kleinsten landungsfähigen Follow-up für `POST /api/v1/notifications` ergänzen, sodass historische Integer-`priority`-Payloads weiter akzeptiert werden, ohne Delivery-, Dedup- oder weitere Manager-Surface wieder einzuführen.

## Gelandeter Scope
- historische Integer-`priority`-Werte werden auf die bestehende Runtime-Prioritätswahrheit normalisiert
- die Legacy-Map bleibt bewusst klein und projiziert `1 -> urgent`, `2 -> high`, `3 -> normal`, `4 -> low`
- boolesche `priority`-Payloads bleiben trotz Python-Int-Verwandtschaft kontrolliert invalid
- Feed-, Digest- und Stats-Sicht bleiben per Read-after-write mit derselben normalisierten Prioritätswahrheit synchron
- derselbe Minimal-Scope gilt wegen geteilter Write-Logik auch für `/api/v1/notifications/send`

## Nicht im Scope
- keine Reintroduktion von Delivery-, Pending-, Dedup- oder HA-Adapter-Surface
- keine neue freie Prioritäts-Skala außerhalb der bestehenden Runtime-Werte `low|normal|high|urgent`
- keine Änderung der öffentlichen Response-Form außerhalb der bereits vorhandenen `priority`-Normalisierung
- keine weitere Manager- oder Routing-Surface

## Artefakte
- `pilotsuite_core/rootfs/usr/src/app/dashboard/api/v1/notifications.py`
- `tests/test_notifications_contract.py`
- `README.md`
- `docs/openapi.json`
- `docs/openapi.yaml`
- `docs/analysis/PS_CORE_SLICE_120_NOTIFICATIONS_ROOT_INTEGER_PRIORITY_COMPAT_2026-04-08.md`
- `TASKBOARD.md`
- `/config/clawd/agents/pilotclaw/TASKLOG.md`

## Evidenz
- `POST /api/v1/notifications` akzeptiert historische Integer-`priority`-Payloads jetzt kontrolliert als Legacy-Hints statt sie pauschal mit `400 invalid_priority` abzulehnen
- die Runtime normalisiert Integer-Prioritäten auf dieselben kanonischen String-Werte, die Feed, Digest und Stats bereits zählen
- boolesche `priority`-Payloads bleiben explizit invalid und verhindern ungewollte Python-`bool`-als-`int`-Drift
- fokussierte Contract-Tests decken den Legacy-Root-Write mit Integer-`priority` plus Invalid-Bool-Guard gegen Drift ab
- README und `docs/openapi.*` beschreiben Root- und Send-Write jetzt konsistent mit demselben `data`-/`channel`-/`source`-/Integer-`priority`-Kompatibilitätsscope
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_notifications_contract.py tests/test_system_contract.py tests/test_contract_inventory_check.py tests/test_public_api_docs_alignment.py` → **29 passed**
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
- Slice 121 — `POST /api/v1/notifications/send` auf den kleinsten expliziten Integer-`priority`-Contract-Paritäts-Guard auditieren, damit der Alias-Pfad nicht gegen den Root-Write driftet, ohne Delivery-, Dedup- oder weitere Manager-Surface wieder einzuführen
