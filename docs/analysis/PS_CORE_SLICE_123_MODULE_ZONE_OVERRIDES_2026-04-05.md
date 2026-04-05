# PS Core Slice 123 — Module Zone Overrides (2026-04-05)

## Ziel
Den bestehenden `ModuleRegistry`-Support für zonenspezifische Modulzustände (`active | learning | off`) als kanonische Core/API-Surface zugänglich machen, statt die Fähigkeit nur implizit im Storage zu halten.

## Gelieferter Slice
### API
`copilot_core/rootfs/usr/src/app/copilot_core/api/v1/module_control.py`
- `GET /api/v1/modules/zones/<zone_id>` — explizite Zone-Overrides einer Zone lesen
- `GET /api/v1/modules/zones/<zone_id>/<module_id>` — effektiven Zonenzustand inkl. `global_state`, `override_state`, `has_override` lesen
- `PUT /api/v1/modules/zones/<zone_id>/<module_id>` — Zone-Override erstellen/aktualisieren
- `DELETE /api/v1/modules/zones/<zone_id>/<module_id>` — Zone-Override löschen und sauber auf Global-Fallback zurückfallen

### Storage
`copilot_core/rootfs/usr/src/app/copilot_core/module_registry.py`
- `delete_zone_state(zone_id, module_id)` ergänzt, damit explizite Zone-Overrides kanonisch entfernbar sind

### Tests
- `tests/test_module_control_contract.py`
  - neue Zone-Override-Read/Write/Delete-Pfade
  - Validierungs-, Auth- und Runtime-Fehlerpfade
- `copilot_core/rootfs/usr/src/app/tests/test_module_registry_zones.py`
  - Delete-/Fallback-Verhalten der Zone-Overrides

## Verifikation
- `pytest -q tests/test_module_control_contract.py copilot_core/rootfs/usr/src/app/tests/test_module_registry_zones.py tests/test_ps_core_runtime_contract_inventory.py`
  - `59 passed in 27.13s`
- `python3.14 scripts/contract_inventory_fast_check.py --repo .`
  - `PASS`

## Warum dieser Slice jetzt
Nach Schließen der aktiven Contract-/Inventar-Lücke war laut Taskboard genau ein kleinster nicht-Contract-Core/API-Forward-Slice zu ziehen. Die Zone-Override-Surface ist dafür passend, weil:
- der zugrunde liegende Registry-Support bereits real existierte,
- `module_control` die kanonische Modul-Governance-Surface ist,
- und `backend_ui` dort bereits ein offenes TODO auf dieselbe Wahrheit hatte.

## Nächster exakter Schritt
**Slice 124 — `backend_ui` auf dieselbe kanonische Zone-Override-Wahrheit umstellen**, damit `/api/v1/backend/zones/<zone_id>/modules` nicht länger parallel auf `enabled_modules` + TODO-Semantik schreibt, sondern dieselbe `ModuleRegistry`-Quelle nutzt.
