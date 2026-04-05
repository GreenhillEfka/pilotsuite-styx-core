# PS Core Slice 125 — Backend UI Zone-Module Read Model Alignment

## Ziel
`backend_ui`-Read-Side für Zonenmodule auf dieselbe kanonische Zone-Override-Wahrheit wie `module_control` ziehen, damit Zonenkarten und Zonendetail-Responses `state`, `global_state`, `override_state` und `has_override` direkt lesen statt sie weiter aus `enabled_modules`-/Template-Heuristik abzuleiten.

## Führende Artefakte
- `/config/clawd/team/worktrees/pilotsuite-styx-core-current/copilot_core/rootfs/usr/src/app/copilot_core/api/v1/backend_ui.py`
- `/config/clawd/team/worktrees/pilotsuite-styx-core-current/tests/test_backend_ui_contract.py`
- `/config/clawd/team/worktrees/pilotsuite-styx-core-current/TASKBOARD.md`
- `/config/clawd/agents/pilotclaw/TASKLOG.md`

## Gelandeter Diff
- `backend_ui` ergänzt jetzt kleine Read-Model-Helper für Zonenmodule:
  - Modul-Kandidaten werden aus Template-Defaults, `enabled_modules`, vorhandenen Zone-Overrides und Zonendetail-Daten vereinigt.
  - Für jedes Kandidatenmodul wird dieselbe kanonische Payload wie in Slice 123/124 gebaut: `state`, `global_state`, `override_state`, `has_override`.
- `GET /api/v1/backend/zones` liefert pro Zone jetzt zusätzlich:
  - `modules`: sortierte Zone-Module mit Override-Metadaten
  - `enabled_modules`: nur noch als abgeleitete Read-Side des effektiven Zustands (`state != off`)
- `GET /api/v1/backend/zones/<zone_id>/entities` liefert dieselbe Zonenmodul-Read-Side direkt mit, damit Zonendetails und Entity-Mapping-Caller keine Parallelheuristik mehr nachbauen müssen.
- Das `overview`-Payload im Backend-Zonen-Endpoint spiegelt dieselbe angereicherte Zonenliste, damit Top-Level- und Overview-Consumer nicht auseinanderlaufen.

## Verifikation
- `pytest -q tests/test_backend_ui_contract.py copilot_core/rootfs/usr/src/app/tests/test_module_registry_zones.py` → `23 passed in 0.97s`
- `python3.14 scripts/contract_inventory_fast_check.py --repo .` → `PASS`

## Ergebnis
Die `backend_ui`-Read-Side für Zonenmodule liest jetzt dieselbe kanonische Override-Wahrheit wie die Core-Surface aus Slice 123 und die Write-Surface aus Slice 124. `enabled_modules` bleibt kompatible Projektion, aber nicht mehr die einzige lesbare Wahrheit für Zone-Module.

## Nächster exakter Slice
**Slice 126:** `backend_ui`-Modulkarten (`GET /api/v1/backend/modules`) auf `ModuleRegistry`-Wahrheit ziehen, damit globale Modulzustände nicht länger als statische Platzhalter neben der jetzt kanonischen Zonen-Read-Side stehen.

## Success Signal
- Zonenliste und Zonendetail liefern dieselbe lesbare Override-Wahrheit
- `enabled_modules` ist klar als Projektion statt als kanonische Semantik erkennbar
- der nächste Schritt bleibt ein kleiner Read-Side-Folgeslice ohne Meta-Drift
