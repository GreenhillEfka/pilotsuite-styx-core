# Core RC Prep — 2026-03-27

## Purpose
Explizites Release-Candidate-Prep-Artefakt für die Core-Lane.

**Boundary:**
- Dies ist **Repo/Dev-Readiness**.
- **Kein Release, kein Install, kein Live-Test.**
- Release-Governance bleibt: **Builder -> Review -> Release**.
- **Authoritative Core repo:** `/config/clawd/team/repos/pilotsuite-styx-core`

## RC Scope
### Change area
Contract-Härtung für:
- Zone Truth Sync
- Dashboard Read Models
- Brain Read Model
- Classification Authority
- Core Contract Bundle Runner

### Changed artifacts
#### Core code
- `copilot_core/rootfs/usr/src/app/copilot_core/api/v1/zone_automation.py`
- `copilot_core/rootfs/usr/src/app/copilot_core/core/brain_read_model.py`
- `copilot_core/rootfs/usr/src/app/copilot_core/core/dashboard_read_models.py`
- `copilot_core/rootfs/usr/src/app/copilot_core/core/taxonomy.py`
- `copilot_core/rootfs/usr/src/app/copilot_core/hub/habitus_zones.py`
- `copilot_core/rootfs/usr/src/app/copilot_core/hub/zone_automation.py`

#### Test / runner / review artifacts
- `tests/test_brain_read_model_contract.py`
- `tests/test_dashboard_read_models_contract.py`
- `tests/test_taxonomy_contract.py`
- `tests/test_zone_truth_sync_contract.py`
- `scripts/run_core_contract_bundle.sh`
- `docs/HA_RELEASE_CONTRACT_HANDOFF_2026-03-27.md`

## Branch / coordinated ref
- **Branch:** `main`
- **Paired functional Core cutover ref:** `8b017a74`
- **Live repo-head snapshots:** exported separately via the release-manifest/export scripts when needed

## What is now hardened
### 1) Zone Truth persistence
- `zone_type`, `enabled_modules`, `ha_entities` werden im Core explizit mitgeführt
- HA→Core zone sync ist nicht mehr nur auf ad-hoc config attrs angewiesen

### 2) Dashboard read model truth chain
- Zone Summary zählt `zone_type` statt `mode`
- Zone Detail übernimmt `zone_type` + `enabled_modules`
- Zone Detail gruppiert Entities via Taxonomy / Classification Authority
- Zone Detail spiegelt Modul-Configs aus `zone_automation` nur für aktivierte Module
- System Overview übernimmt per-Zone-Modulzustände und Brain-Snapshots robuster

### 3) Taxonomy correction
- `balkon` / `balcony` / `loggia` / `patio` / `deck` -> `terrace`
- `garden` / `garten` / `garage` -> `outside`

### 4) Brain snapshot fallback
- gecachte Brain-Graph-Daten bleiben sichtbar, auch wenn der Service fehlt

### 5) Reproducible contract bundle
- Ein expliziter Runner bündelt die aktuellen Core-Contract-Suites
- Runner ist auf eine passende Testumgebung gehärtet
- Runner räumt Workspace-Contract-`tmp/*.jsonl` vorab auf, damit Integrationstests isoliert laufen

## Evidence
### Contract bundle command
```bash
./scripts/run_core_contract_bundle.sh
```

### Latest result
- **32 Tests grün**
- **0 Warnings**

### Bundled suites
- `tests/test_dashboard_read_models_contract.py`
- `tests/test_zone_dashboard_contract.py`
- `tests/test_brain_read_model_contract.py`
- `tests/test_taxonomy_contract.py`
- `tests/test_zone_truth_sync_contract.py`
- `tests/test_core_wiring_contract.py`
- `tests/test_event_processor_import_contract.py`
- `tests/integration/test_workspace_ha_core_contract.py`

## Risks / review focus
### 1) Wide touch surface in `dashboard_read_models.py`
- Datei bündelt jetzt mehrere Truth-Verkettungen
- Review soll besonders auf unerwünschte Seiteneffekte in bestehenden Consumer-Pfaden achten

### 2) Zone sync metadata semantics
- `enabled_modules`/`ha_entities` werden jetzt explizit persistiert
- Review soll prüfen, ob bestehende Serializer/Consumers implizite alte Annahmen hatten

### 3) Runner environment selection
- Runner pickt jetzt gezielt eine passende Testumgebung
- Review soll bestätigen, dass diese Auswahl in der Team-Umgebung stabil und gewollt ist

## Required review input before RC cut
### Builder self-check
- [x] Contract suites geschrieben/ergänzt
- [x] Bundle-Runner grün
- [x] HA-Release-Handoff erstellt
- [x] Exakter Commit-Schnitt für den 15.2.0-Kandidaten erstellt (`8b017a74`)
- [x] Final changelog/release note input vorbereiten (`docs/CORE_GITHUB_RELEASE_NOTES_INPUT_2026-03-27.md`)

### Reviewer should verify
- [ ] Truth chain passt zu `docs/ZONE_TRUTH_CONTRACT.md`
- [ ] Keine Consumer-Regressions in Dashboard-/API-Lane
- [ ] Runner choice / env assumptions sind akzeptabel
- [ ] HA-Lane kann den Handoff als Review-Input direkt verwenden

## Explicit non-claims
- Kein Release erzeugt
- Kein Install durchgeführt
- Kein Live-Test durchgeführt
- Kein Live-Erfolg behauptet

## Recommended next step
1. Review dieses RC-Preps gegen Commit **`8b017a74`** + Contract bundle
2. Danach nur noch Review-/Release-Governance-Entscheidung, ob der Commit der RC-Anker bleibt oder ein weiterer Core-Fix nötig ist
3. Erst nach Review in Release-Governance übergehen
