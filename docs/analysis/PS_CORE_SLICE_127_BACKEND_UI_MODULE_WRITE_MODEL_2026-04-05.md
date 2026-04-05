# PS Core Slice 127 — Backend UI Module Write Model Alignment

## Ziel
`PUT /api/v1/backend/modules/<module_id>` auf dieselbe kanonische `ModuleRegistry`-Wahrheit ziehen wie die bereits gelandete Backend-UI-Modul-Read-Side, damit globale Modulmutationen nicht länger nur geloggt, sondern restart-sicher persistiert werden.

## Führende Artefakte
- `/config/clawd/team/worktrees/pilotsuite-styx-core-current/copilot_core/rootfs/usr/src/app/copilot_core/api/v1/backend_ui.py`
- `/config/clawd/team/worktrees/pilotsuite-styx-core-current/tests/test_backend_ui_contract.py`
- `/config/clawd/team/worktrees/pilotsuite-styx-core-current/TASKBOARD.md`
- `/config/clawd/agents/pilotclaw/TASKLOG.md`

## Gelandeter Diff
- `PUT /api/v1/backend/modules/<module_id>` normalisiert den Pfad-`module_id` jetzt bewusst und schreibt `state` nicht mehr nur als Logzeile weg.
- Der State-Pfad persistiert globale Modulzustände jetzt kanonisch über `ModuleRegistry.set_state(...)`.
- Persistenzfehler auf der Registry-Write-Side liefern jetzt kontrollierte JSON-500-Responses statt stiller Erfolgs-Acks ohne echte Zustandsänderung.
- Die fokussierten Contracts verifizieren jetzt explizit:
  - erfolgreiche globale Modulmutation,
  - Read-after-write über `GET /api/v1/backend/modules` auf derselben Registry-Wahrheit,
  - kontrollierten Fehlerpfad bei fehlgeschlagenem Registry-Write.
- Bestehende `config`-Validierung und ACK-Semantik bleiben in diesem Minimal-Slice bewusst unverändert; der Slice zieht nur die globale Modul-State-Write-Side auf kanonische Wahrheit.

## Verifikation
- `pytest -q tests/test_backend_ui_contract.py copilot_core/rootfs/usr/src/app/tests/test_module_registry_zones.py` → `24 passed in 1.06s`
- `python3.14 scripts/contract_inventory_fast_check.py --repo .` → `PASS`

## Ergebnis
Die Backend-UI-Globalmodule sind jetzt nicht nur truth-backed lesbar, sondern schreiben ihren `active/learning/off`-State über dieselbe `ModuleRegistry`-Wahrheit, die bereits die Modul- und Zonen-Read-Side speist. Damit verschwindet der frühere Log-only-Schreibpfad, und Read-after-write bleibt innerhalb derselben Surface restart-sicher konsistent.

## Nächster exakter Slice
**Slice 128:** `GET /api/v1/backend/dashboard` auf dieselbe Modul-/Zonen-Wahrheit ziehen, damit Dashboard-Zählwerte und Übersichtsmetriken nicht länger neben den nun kanonischen Backend-UI-Modul- und Zonen-Surfaces driften.

## Success Signal
- `PUT /api/v1/backend/modules/<module_id>` persistiert globale Modulzustände statt sie nur zu loggen
- `GET /api/v1/backend/modules` zeigt denselben neuen Zustand direkt nach dem Write wieder
- Backend-UI-Globalmodule lesen und schreiben dieselbe kanonische `ModuleRegistry`-Wahrheit
