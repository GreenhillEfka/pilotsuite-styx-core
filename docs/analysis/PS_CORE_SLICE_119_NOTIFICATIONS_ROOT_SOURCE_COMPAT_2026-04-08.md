# PS CORE SLICE 119 — `POST /api/v1/notifications` Source-Payload-Kompatibilität

## Kontext
- Arbeitsort: `/config/clawd/team/worktrees/pilotsuite-styx-core-current`
- Ausgangspunkt: letzter realer Stand aus `TASKBOARD.md` und `/config/clawd/agents/pilotclaw/TASKLOG.md`
- Pflichtbasis außerhalb des Worktrees bleibt weiter inkonsistent, weil mehrere vorgegebene Steuerdateien fehlen
- Slice 118 hatte bereits historische `data`- und `channel`-Payloads kompatibel gemacht, aber historischer `source`-Input wurde noch nicht angenommen

## Ziel
Den kleinsten landungsfähigen Follow-up für `POST /api/v1/notifications` ergänzen, sodass historische `source`-Payloads weiter akzeptiert werden, ohne Dedup-, Rate-Limit-, Delivery- oder Routing-Surface wieder einzuführen.

## Gelandeter Scope
- historischer `source`-Payload wird als optionaler String-Hint akzeptiert
- expliziter `source` wird whitespace-getrimmt und auf die bestehende lowercase-Filterlogik normalisiert
- fehlt `source`, bleibt die kanonische Runtime-Wahrheit weiter `api`
- Feed-, Digest- und Stats-Sicht bleiben per Read-after-write mit derselben `source`-Wahrheit synchron
- derselbe Minimal-Scope gilt wegen geteilter Write-Logik auch für `/api/v1/notifications/send`

## Nicht im Scope
- keine Reintroduktion von Dedup-, Rate-Limit-, Pending-Write-, Delivery- oder HA-Adapter-Surface
- keine freie Reprojektion von `channel` in das Read-Model
- keine historische Integer-`priority`-Kompatibilität
- keine Änderung der öffentlichen Response-Form außerhalb des bereits vorhandenen `source`-Felds

## Artefakte
- `pilotsuite_core/rootfs/usr/src/app/dashboard/api/v1/notifications.py`
- `tests/test_notifications_contract.py`
- `README.md`
- `docs/openapi.json`
- `docs/openapi.yaml`
- `docs/analysis/PS_CORE_SLICE_119_NOTIFICATIONS_ROOT_SOURCE_COMPAT_2026-04-08.md`
- `TASKBOARD.md`
- `/config/clawd/agents/pilotclaw/TASKLOG.md`

## Evidenz
- `POST /api/v1/notifications` akzeptiert historische `source`-Payloads jetzt kontrolliert als String-Hint statt sie pauschal auf `api` festzunageln
- übergebene `source`-Werte werden auf dieselbe lowercase-Form normalisiert, die der bestehende Feed-Filter schon nutzt
- fehlende `source`-Payloads bleiben kompatibel beim bisherigen Default `api`
- fokussierte Contract-Tests decken Root-Write mit `data`-/`channel`-/`source`-Legacy-Hints plus Invalid-Source-Guard ab
- README und `docs/openapi.*` beschreiben Root- und Send-Write jetzt konsistent mit demselben Legacy-Kompatibilitätsscope
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_notifications_contract.py tests/test_system_contract.py tests/test_contract_inventory_check.py tests/test_public_api_docs_alignment.py`
- `/config/clawd/.venv_smoke_gate/bin/python scripts/contract_inventory_check.py --repo . --light`
- `/config/clawd/.venv_smoke_gate/bin/python scripts/contract_inventory_check.py --repo .`

## Bekannte Inkonsistenz
- `/config/clawd/AGENTS.md` fehlt weiterhin
- `/config/clawd/team/PILOTSUITE_EXECUTION_FOUNDATION.md` fehlt weiterhin
- `/config/clawd/team/PILOTSUITE_PROGRESS_LEDGER.md` fehlt weiterhin
- `/config/clawd/team/shared/PILOTSUITE_RECONSOLIDATED_MASTER_WORKPLAN_2026-04-04.md` fehlt weiterhin
- `/config/clawd/team/shared/PILOTSUITE_ONE_LEAD_EXECUTION_STANDARD_2026-04-04.md` fehlt weiterhin
- Slice deshalb erneut vom letzten realen Artefaktstand aus Taskboard/Tasklog fortgeführt

## Nächster exakter Task
- Slice 120 — `POST /api/v1/notifications` auf den kleinsten historischen Integer-`priority`-Payload-Kompatibilitäts-Follow-up auditieren, ohne Delivery-, Dedup- oder weitere Manager-Surface wieder einzuführen
