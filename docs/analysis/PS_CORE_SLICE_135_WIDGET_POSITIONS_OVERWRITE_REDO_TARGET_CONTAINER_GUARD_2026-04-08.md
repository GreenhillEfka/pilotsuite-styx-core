# PS Core Slice 135 — `widget_positions` Overwrite-Write `redo_stack`-Ziel-Container-Guard

## Stand
- Nach Slice 134 blieb auf den Overwrite-Write-Pfaden von `POST /api/v1/widgets/positions` und `POST /api/v1/widgets/positions/bulk` noch eine kleine Persistenzlücke offen.
- Beim Überschreiben einer bereits gespeicherten Widget-Position wurde ein shape-falscher persistierter `redo_stack`-Container bisher still zu `[]` repariert.
- Gelandet wurde deshalb nur der kleinste explizite Ziel-Container-Guard auf den bestehenden Overwrite-Pfaden, ohne neue Surface oder zusätzliche Store-Logik einzuführen.

## Gelandete Artefakte
- `pilotsuite_core/rootfs/usr/src/app/dashboard/api/v1/widget_positions.py`
- `tests/test_widget_positions_contract.py`
- `docs/analysis/PS_CORE_SLICE_135_WIDGET_POSITIONS_OVERWRITE_REDO_TARGET_CONTAINER_GUARD_2026-04-08.md`

## Gelandeter Scope
- `POST /api/v1/widgets/positions` validiert beim Überschreiben einer bestehenden Position den persistierten Ziel-Container `redo_stack` jetzt explizit vor dem Reset auf `[]`.
- `POST /api/v1/widgets/positions/bulk` behandelt denselben Legacy-Fall pro betroffenem Eintrag kontrolliert in `errors[]`, statt den Persistenzrest still zu reparieren.
- fehlende `redo_stack`-Container bleiben weiter minimal landingfähig; der Slice härtet nur den kleinsten Persistenz-Drift-Fall auf bestehenden Overwrite-Write-Pfaden.
- fehlerhafte Persistenz-Container bleiben bewusst unverändert liegen; der Slice erweitert weder Store-Reparatur noch öffentliche Surface.

## Test-Evidence
- `/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_widget_positions_contract.py tests/test_contract_inventory_check.py tests/test_public_api_docs_alignment.py tests/test_system_contract.py` → **30 passed**
- `/config/clawd/.venv_smoke_gate/bin/python scripts/contract_inventory_check.py --repo . --light` → **OK**
- `/config/clawd/.venv_smoke_gate/bin/python scripts/contract_inventory_check.py --repo .` → **OK**

## Nächster exakter Task
- Slice 136 — `POST /api/v1/widgets/positions` und `POST /api/v1/widgets/positions/bulk` auf den kleinsten expliziten Legacy-/Persistenz-`history`-Quell-Container-Guard auditieren, damit shape-falsche bereits gespeicherte `history`-Container auf Overwrite-Write-Pfaden nicht still weitergetragen werden, ohne neue Surface oder zusätzliche Store-Logik einzuführen.
