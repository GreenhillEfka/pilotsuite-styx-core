# PS Core Slice 126 — Backend UI Module Read Model Alignment

## Ziel
`GET /api/v1/backend/modules` auf dieselbe kanonische `ModuleRegistry`-Wahrheit ziehen wie die übrigen Modul-Surfaces, damit globale Modulzustände im Backend UI nicht länger als statische Platzhalter neben der bereits truth-backed Zonen-Read-Side stehen.

## Führende Artefakte
- `/config/clawd/team/worktrees/pilotsuite-styx-core-current/copilot_core/rootfs/usr/src/app/copilot_core/api/v1/backend_ui.py`
- `/config/clawd/team/worktrees/pilotsuite-styx-core-current/tests/test_backend_ui_contract.py`
- `/config/clawd/team/worktrees/pilotsuite-styx-core-current/TASKBOARD.md`
- `/config/clawd/agents/pilotclaw/TASKLOG.md`

## Gelandeter Diff
- `backend_ui` ergänzt kleine Modulkarten-Helper für die globale Modul-Read-Side:
  - bekannte Backend-UI-Modulkarten (`presence`, `light`) bleiben mit kompatiblen Beschreibungs-/Config-Feldern erhalten,
  - unbekannte, aber in `ModuleRegistry` oder Zone-Overrides sichtbare Module werden generisch und deterministisch projiziert statt still zu fehlen.
- `GET /api/v1/backend/modules` liest `state` jetzt direkt aus `ModuleRegistry` statt aus fest verdrahteten Platzhaltern.
- Dieselbe Surface projiziert zusätzlich lesbare Governance-Metadaten:
  - `global_state`
  - `zones_enabled`
  - `zone_overrides`
  - `has_zone_overrides`
- Die Zählwerte leiten sich aus derselben kanonischen Zonen-Read-Side ab wie Slice 125, damit globale Modulkarten und zonenscharfe Modulantworten nicht auseinanderlaufen.

## Verifikation
- `pytest -q tests/test_backend_ui_contract.py copilot_core/rootfs/usr/src/app/tests/test_module_registry_zones.py` → `23 passed in 0.97s`
- `python3.14 scripts/contract_inventory_fast_check.py --repo .` → `PASS`

## Ergebnis
Die Backend-UI-Modulkarten lesen ihre globalen Zustände jetzt restart-sicher aus der kanonischen `ModuleRegistry`-Wahrheit und zeigen zugleich, ob zonenspezifische Overrides existieren und in wie vielen Zonen ein Modul effektiv aktiv ist. Damit driftet die globale Backend-UI-Modulansicht nicht länger gegen die bereits gelandete Zonen-Read-Side.

## Nächster exakter Slice
**Slice 127:** `PUT /api/v1/backend/modules/<module_id>` auf dieselbe `ModuleRegistry`-Wahrheit ziehen, damit Backend-UI-Globalmodule nicht nur truth-backed gelesen, sondern auch kanonisch geschrieben werden statt `state` weiter nur zu loggen.

## Success Signal
- `GET /api/v1/backend/modules` zeigt keine statischen Global-State-Platzhalter mehr
- zonenscharfe Overrides und globale Modulzustände sind in derselben Backend-UI-Surface lesbar gekoppelt
- der nächste Schritt bleibt ein kleiner Write-Side-Folgeslice ohne Meta-Drift
