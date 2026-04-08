# PS CORE SLICE 118 — `POST /api/v1/notifications` Legacy-Payload-Kompatibilität

## Kontext
- Arbeitsort: `/config/clawd/team/worktrees/pilotsuite-styx-core-current`
- Ausgangspunkt: letzter realer Stand aus `TASKBOARD.md` und `/config/clawd/agents/pilotclaw/TASKLOG.md`
- Pflichtbasis außerhalb des Worktrees bleibt weiter inkonsistent, weil mehrere vorgegebene Steuerdateien fehlen
- Slice 117 hatte den Root-Create-Alias bereits gelandet, aber historische Request-Payloads mit `data` und `channel` wurden noch nicht kompatibel angenommen

## Ziel
Den kleinsten landungsfähigen Payload-Kompatibilitäts-Follow-up für `POST /api/v1/notifications` ergänzen, sodass historische `data`-Bodies weiter auf die schlanke Runtime-Form passen und `channel` als Legacy-Hint akzeptiert wird, ohne Delivery-, Dedup- oder Routing-Surface wieder einzuführen.

## Gelandeter Scope
- historische `data`-Payload wird als Alias auf `action_data` akzeptiert
- explizites `action_data` bleibt die kanonische moderne Eingabe und behält Vorrang
- historischer `channel`-Payload wird als kompatibler String-Hint validiert und akzeptiert
- `channel` wird bewusst nicht in eine neue Delivery- oder Routing-Wahrheit umprojiziert
- Root-Write hält trotz Legacy-Payload Feed-, Digest- und Stats-Sicht per Read-after-write synchron
- derselbe Minimal-Scope gilt wegen geteilter Write-Logik auch für `/api/v1/notifications/send`

## Nicht im Scope
- keine Reintroduktion von Delivery-Routing, HA-Adapter oder Pending-Write-Surface
- keine Dedup- oder Rate-Limit-Logik
- keine historische `source`- oder Integer-`priority`-Kompatibilität
- keine Änderung der öffentlichen Response-Form

## Artefakte
- `pilotsuite_core/rootfs/usr/src/app/dashboard/api/v1/notifications.py`
- `tests/test_notifications_contract.py`
- `README.md`
- `docs/openapi.json`
- `docs/openapi.yaml`
- `docs/analysis/PS_CORE_SLICE_118_NOTIFICATIONS_ROOT_LEGACY_PAYLOAD_COMPAT_2026-04-08.md`
- `TASKBOARD.md`
- `/config/clawd/agents/pilotclaw/TASKLOG.md`

## Evidenz
- `POST /api/v1/notifications` nimmt historische `data`-Bodies jetzt kontrolliert als `action_data` an
- historischer `channel`-Input bleibt als Request-Hint kompatibel, ohne im Read-Model eine neue Delivery-Surface zu erzeugen
- fokussierte Contract-Tests decken den Legacy-Root-Write plus Invalid-Channel-Guard ab
- README und `docs/openapi.*` beschreiben Root- und Send-Write jetzt konsistent mit demselben Legacy-Kompatibilitätsscope
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_notifications_contract.py tests/test_system_contract.py tests/test_contract_inventory_check.py tests/test_public_api_docs_alignment.py` → **28 passed**
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
- Slice 119 — `POST /api/v1/notifications` auf den kleinsten historischen `source`-Payload-Kompatibilitäts-Follow-up auditieren, ohne Dedup-, Rate-Limit- oder Delivery-Surface wieder einzuführen
