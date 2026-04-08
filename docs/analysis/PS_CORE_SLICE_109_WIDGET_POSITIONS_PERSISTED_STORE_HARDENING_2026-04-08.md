# PS Core Slice 109 — `widget_positions` Persisted-Store Hardening

## Stand
- Trotz gelandeter Runtime-/Inventur-Surface aus Slice 98/99 blieb im dateibasierten `widget_positions`-Reload eine kleine Robustheitslücke offen.
- Der Loader übernahm bislang jeden gültigen JSON-Root blind; nicht-diktbasierte Persistenzdaten oder kaputte Einträge konnten dadurch die read-only `GET /api/v1/widgets/positions`-Surface beim Laden brechen.
- Auf ausdrückliche Rekonsolidierungs-Priorität wurde deshalb der kleinste saubere Rest am aktiven `widget_positions`-Slice vor dem nächsten Notifications-Follow-up geschlossen.

## Gelandete Artefakte
- `pilotsuite_core/rootfs/usr/src/app/dashboard/api/v1/widget_positions.py`
- `tests/test_widget_positions_contract.py`
- `docs/analysis/PS_CORE_SLICE_109_WIDGET_POSITIONS_PERSISTED_STORE_HARDENING_2026-04-08.md`
- `TASKBOARD.md`
- `/config/clawd/agents/pilotclaw/TASKLOG.md`

## Gelandeter Scope
- persisted `widget_positions`-JSON wird beim Reload jetzt strikt auf Dict-Shape normalisiert
- nicht-diktbasierte Root-Payloads oder defekte Einträge werden kontrolliert verworfen statt spätere Runtime-Fehler auszulösen
- fehlende `widget_id` innerhalb valider Store-Einträge wird aus dem Persistenz-Key nachgezogen
- fokussierter Contract-Test deckt gemischte Persistenzdaten gegen Reload-Drift ab

## Test-Evidence
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_widget_positions_contract.py tests/test_contract_inventory_check.py tests/test_public_api_docs_alignment.py tests/test_system_contract.py`
- `/config/clawd/.venv_smoke_gate/bin/python scripts/contract_inventory_check.py --repo . --light`
- `/config/clawd/.venv_smoke_gate/bin/python scripts/contract_inventory_check.py --repo .`

## Known Inconsistency
- `/config/clawd/AGENTS.md` fehlt weiterhin
- `/config/clawd/team/PILOTSUITE_EXECUTION_FOUNDATION.md` fehlt weiterhin
- `/config/clawd/team/PILOTSUITE_PROGRESS_LEDGER.md` fehlt weiterhin
- `/config/clawd/team/shared/PILOTSUITE_RECONSOLIDATED_MASTER_WORKPLAN_2026-04-04.md` fehlt weiterhin
- `/config/clawd/team/shared/PILOTSUITE_ONE_LEAD_EXECUTION_STANDARD_2026-04-04.md` fehlt weiterhin
- Slice deshalb erneut vom letzten realen Artefaktstand aus Taskboard/Tasklog fortgeführt

## Next Exact Task
- Slice 110 — `/api/v1/notifications/subscriptions` als nächsten kleinsten read-only Follow-up-Slice gegen den historischen Notifications-Contract auditieren und nur den minimalen landingfähigen Scope ziehen
