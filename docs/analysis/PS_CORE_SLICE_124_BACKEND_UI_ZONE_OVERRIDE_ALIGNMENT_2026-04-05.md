# PS Core Slice 124 — Backend UI Zone-Override Alignment

## Ziel
`/api/v1/backend/zones/<zone_id>/modules` auf dieselbe kanonische Zone-Override-Wahrheit wie `module_control` ziehen, damit `backend_ui` nicht länger parallel direkt auf `enabled_modules` schreibt und `active/learning/off` nur als TODO nebenher führt.

## Führende Artefakte
- `/config/clawd/team/worktrees/pilotsuite-styx-core-current/copilot_core/rootfs/usr/src/app/copilot_core/api/v1/backend_ui.py`
- `/config/clawd/team/worktrees/pilotsuite-styx-core-current/tests/test_backend_ui_contract.py`
- `/config/clawd/team/worktrees/pilotsuite-styx-core-current/copilot_core/rootfs/usr/src/app/tests/test_module_registry_zones.py`
- `/config/clawd/team/worktrees/pilotsuite-styx-core-current/TASKBOARD.md`

## Gelandeter Diff
- `backend_ui` hat jetzt gemeinsame JSON-/String-Validierungs-Helper für Mutationspfade; fehlende Bodies, leere IDs und invalide States kippen kontrolliert auf JSON-400 statt implizit zu brechen.
- `POST /api/v1/backend/zones/<zone_id>/modules` schreibt die Zonenwahrheit jetzt kanonisch über `ModuleRegistry`:
  - gleicher State wie global → expliziten Zone-Override löschen
  - abweichender State → expliziten Zone-Override persistieren
- Die Response der Zone-Modul-Mutation zeigt jetzt dieselbe lesbare Wahrheit wie `module_control`: `state`, `global_state`, `override_state`, `has_override`.
- `enabled_modules` im `HubZoneEngine`-Objekt wird nur noch als Read-Side-Projektion des effektiven Zustands gespiegelt, nicht mehr als parallele Schreibwahrheit benutzt.
- bestehende `backend_ui`-Mutationspfade für Module-/Model-Updates sind auf dieselbe JSON-Validierungsbasis gehärtet, damit die Contract-Basis der Surface wieder zum aktiven Rootfs-Pfad passt.

## Verifikation
- `pytest -q tests/test_backend_ui_contract.py` → `5 passed in 0.42s`
- `pytest -q tests/test_backend_ui_contract.py copilot_core/rootfs/usr/src/app/tests/test_module_registry_zones.py` → `23 passed in 0.86s`

## Ergebnis
Der `backend_ui`-Write-Pfad für Zonenmodule hängt jetzt an derselben kanonischen Override-Wahrheit wie die Core-Surface aus Slice 123. Damit endet die bisherige Parallel-Semantik aus `enabled_modules` plus ungelandeter TODO-Logik; die alte Engine-Struktur bleibt nur noch als kompatible Projektion erhalten.

## Nächster exakter Slice
**Slice 125:** `backend_ui`-Read-Side für Zonenmodule auf dieselbe kanonische Override-Wahrheit ziehen, damit Zonen-/Modulkarten `state`, `global_state`, `override_state` und `has_override` direkt lesen statt weiter aus Template-/`enabled_modules`-Heuristik abzuleiten.

## Success Signal
- `backend_ui` schreibt Zonenmodulzustände nicht mehr parallel in eine Schattenwahrheit
- effektiver Zustand und Override-Metadaten sind direkt im Backend-Response sichtbar
- der nächste Schritt ist ein klar abgegrenzter Read-Side-Slice statt erneuter Mutation-/Contract-Drift
