# HA Release Contract Handoff — 2026-03-27

## Purpose
Contract-seitiges Übergabe-/Review-Artefakt aus der Core-Lane für die HA-Release-Lane.

**Wichtig:**
- Das ist **Dev/Repo-Evidence**, kein Install- oder Live-Test.
- Release-Governance bleibt: **Builder -> Review -> Release**.
- **Kein Live-Test ohne Release.**
- **Authoritative Core repo:** `/config/clawd/team/repos/pilotsuite-styx-core`

## Scope of this handoff
Diese Übergabe bündelt den aktuellen Core-Contract-Stand, damit die HA-Lane einen sauberen Release-Kandidaten gegen belastbare Core-Contracts reviewen kann.

## Core Contract Evidence (grün)
### Reproduzierbarer Runner
```bash
./scripts/run_core_contract_bundle.sh
```

### Letztes Ergebnis
- **35 Tests grün**
- **0 Warnings**
- Kein Release, kein Install, kein Live-Test

### Enthaltene Suites
- `tests/test_dashboard_read_models_contract.py`
- `tests/test_brain_read_model_contract.py`
- `tests/test_taxonomy_contract.py`
- `tests/test_zone_truth_sync_contract.py`
- `tests/test_zone_dashboard_contract.py`
- `tests/test_core_wiring_contract.py`
- `tests/test_event_processor_import_contract.py`
- `tests/integration/test_workspace_ha_core_contract.py`

## Was in der Core-Lane contract-seitig gehärtet wurde
### 1) Zone Truth Persistenz
- `zone_type`, `enabled_modules` und HA-Entity-Topology werden im Core explizit persistiert
- Sync läuft nicht mehr nur über ad-hoc Attribute

**Artefakte:**
- `copilot_core/rootfs/usr/src/app/copilot_core/hub/zone_automation.py`
- `copilot_core/rootfs/usr/src/app/copilot_core/api/v1/zone_automation.py`
- `tests/test_zone_truth_sync_contract.py`

### 2) Dashboard Read Models auf Truth-Lane gezogen
- Zone Summary zählt `zone_type` statt fälschlich `mode`
- Zone Detail übernimmt `zone_type` + `enabled_modules`
- Zone Detail gruppiert Entities via Classification Authority
- Zone Detail spiegelt aktive Modul-Configs aus der Automation-Lane
- SystemOverview übernimmt per-Zone-Modulzustände und Brain-Summary robuster

**Artefakte:**
- `copilot_core/rootfs/usr/src/app/copilot_core/core/dashboard_read_models.py`
- `copilot_core/rootfs/usr/src/app/copilot_core/hub/habitus_zones.py`
- `tests/test_dashboard_read_models_contract.py`

### 3) Classification Authority geschärft
- Balkon/Loggia/Patio/Deck -> `terrace`
- Garten/Garage -> `outside`

**Artefakte:**
- `copilot_core/rootfs/usr/src/app/copilot_core/core/taxonomy.py`
- `tests/test_taxonomy_contract.py`

### 4) Brain Read Model Fallback gehärtet
- gecachte Graph-Snapshots bleiben sichtbar, auch ohne aktiven BrainGraph-Service

**Artefakte:**
- `copilot_core/rootfs/usr/src/app/copilot_core/core/brain_read_model.py`
- `tests/test_brain_read_model_contract.py`

## Aktuelle geänderte Core-Dateien in dieser Lane
- `copilot_core/rootfs/usr/src/app/copilot_core/api/v1/zone_automation.py`
- `copilot_core/rootfs/usr/src/app/copilot_core/core/brain_read_model.py`
- `copilot_core/rootfs/usr/src/app/copilot_core/core/dashboard_read_models.py`
- `copilot_core/rootfs/usr/src/app/copilot_core/core/taxonomy.py`
- `copilot_core/rootfs/usr/src/app/copilot_core/hub/habitus_zones.py`
- `copilot_core/rootfs/usr/src/app/copilot_core/hub/zone_automation.py`
- `scripts/run_core_contract_bundle.sh`

## Neue/ergänzte Contract Suites
- `tests/test_brain_read_model_contract.py`
- `tests/test_dashboard_read_models_contract.py`
- `tests/test_taxonomy_contract.py`
- `tests/test_zone_truth_sync_contract.py`

## Was die HA-Release-Lane jetzt daraus verwenden soll
### Review / Release-Readiness
Vor einem HA-Release-Kandidaten gegen die Core-Schnittstelle prüfen:
1. Zone-Definition-Sync sendet weiterhin:
   - `zone_id`
   - `name_de`
   - `zone_type`
   - `enabled_modules`
   - `entities`
2. HA erwartet nicht mehr implizit, dass Core fehlende Topology über example data errät
3. Terrasse/Balkon-Topologien sollen gegen `terrace` geprüft werden, nicht gegen `outside`
4. Read-Model-/Dashboard-Consumer dürfen `enabled_modules`, `zone_type`, `entities_by_role`, `modules.by_zone` und `modules.zone_states` erwarten

### Empfohlener Review-Call für HA-Lane
- Core-Contract-Bundle laufen lassen
- HA-Release-Kandidat dagegen reviewen
- erst danach Release-Gate / Install / Live-Test

## Bekannte Restpunkte
- Kein scharfer Contract-Blocker aus dem Core-Bundle-Stand
- Weiterer Bewegungsgrund für die HA-Lane wäre nur ein neuer explizit validierter Core cutover ref oder ein scharfer HA-seitiger Blocker

## Nächster sinnvoller Cross-Lane Schritt
- HA-Lane nimmt dieses Handoff als Review-Input für den nächsten HA-Release-Kandidaten
- Gepaarter Core cutover ref ist jetzt `cf3e8ac1`; ältere Refs wie `1d4fc18f` oder `a6eba8a2` sind für den aktuellen koordinierten Cutover veraltet
- Ein neuer Pairing-Ref gilt erst, wenn ein neuerer Ref explizit validiert und announced wird
