# Core Release Input — 2026-03-27

## Purpose
Vorbereitete Release-/Review-Eingabe für den nächsten Core-Release-Kandidaten.

**Nicht enthalten:**
- kein Versionsbump
- kein Tag
- kein Release
- kein Install
- kein Live-Test

## Candidate scope summary
### Theme
Contract-Härtung der Core-Truth-Lane rund um:
- Zone Truth Sync
- Dashboard Read Models
- Classification Authority
- Brain Read Model
- Contract Bundle / Review-Readiness

### Candidate artifact set
#### Code
- `copilot_core/rootfs/usr/src/app/copilot_core/api/v1/zone_automation.py`
- `copilot_core/rootfs/usr/src/app/copilot_core/core/brain_read_model.py`
- `copilot_core/rootfs/usr/src/app/copilot_core/core/dashboard_read_models.py`
- `copilot_core/rootfs/usr/src/app/copilot_core/core/taxonomy.py`
- `copilot_core/rootfs/usr/src/app/copilot_core/hub/habitus_zones.py`
- `copilot_core/rootfs/usr/src/app/copilot_core/hub/zone_automation.py`

#### Tests / evidence
- `tests/test_brain_read_model_contract.py`
- `tests/test_dashboard_read_models_contract.py`
- `tests/test_taxonomy_contract.py`
- `tests/test_zone_truth_sync_contract.py`
- `tests/integration/test_workspace_ha_core_contract.py`
- `scripts/run_core_contract_bundle.sh`

#### Review / handoff docs
- `docs/HA_RELEASE_CONTRACT_HANDOFF_2026-03-27.md`
- `docs/CORE_RC_PREP_2026-03-27.md`

## Evidence snapshot
### Command
```bash
./scripts/run_core_contract_bundle.sh
```

### Result
- **25 tests passed**
- **0 warnings**

## Proposed changelog input (draft, not applied)
```markdown
## [v15.0.x] - 2026-03-27

### Added
- **Core Contract Bundle Runner**: `scripts/run_core_contract_bundle.sh` bündelt die aktuellen Contract-Suites für Zone Truth, Dashboard Read Models, Taxonomy, Brain Read Model und Workspace HA↔Core Contract.
- **Contract Handoff / RC Prep Docs**: `docs/HA_RELEASE_CONTRACT_HANDOFF_2026-03-27.md` und `docs/CORE_RC_PREP_2026-03-27.md` als Review-/Release-Input-Artefakte.

### Changed
- **Zone Truth Sync**: `zone_type`, `enabled_modules` und HA-Entity-Topology werden im Core explizit persistiert.
- **Dashboard Read Models**: Zone Summary/Detail/SystemOverview hängen jetzt sauberer an Zone Truth, Taxonomy, Automation-Lane und Brain-Summary.
- **Classification Authority**: Terrasse/Balkon/Loggia/Patio/Deck werden kanonisch nach `terrace` aufgelöst; Garten/Garage bleiben `outside`.
- **Brain Read Model**: gecachte Graph-Snapshots bleiben auch ohne aktiven BrainGraph-Service sichtbar.

### Tests
- Neue Contract-Suites für Brain/Read Models/Taxonomy/Zone Truth.
- Contract-Bundle aktuell grün: 25 Tests.

### Documentation
- HA-Release-Review-Handoff und Core-RC-Prep ergänzt.
```

## Reviewer checklist
### Contract correctness
- [ ] `zone_type` wird entlang Sync -> Hub -> Read Models konsistent transportiert
- [ ] `enabled_modules` wird entlang Sync -> Automation -> Dashboard konsistent transportiert
- [ ] `entities_by_role` im Zone Detail entspricht der Classification Authority
- [ ] `SystemOverview.modules.by_zone` und `zone_states` spiegeln die Automation-Lane korrekt
- [ ] Brain-Summary-Fallback bleibt nicht leer, wenn nur Snapshot-Daten vorliegen

### Regression watch-outs
- [ ] Keine bestehenden Dashboard-Consumer erwarten das alte implizite Verhalten
- [ ] Keine HA-Lane verlässt sich auf frühere Balkon -> `outside` Annahme
- [ ] Runner löscht nur die bekannten Workspace-Contract-tmp-Dateien und nichts darüber hinaus
- [ ] Bundle läuft in Team-Umgebung reproduzierbar mit derselben Interpreter-Auswahl

### Release governance readiness
- [ ] Builder-Scope ist klar und begrenzt
- [ ] Review-Artefakte reichen für Builder -> Review -> Release
- [ ] Keine Live-/Install-Claims vermischen sich mit Repo-Evidence

## Release note input (short form)
- Core-Truth-Lane gehärtet: Zone Truth Sync, Dashboard Read Models, Taxonomy und Brain Read Model stärker auf einen konsistenten Contract gezogen.
- Neues Contract-Bundle liefert reproduzierbare Review-Evidence vor dem nächsten Release-Kandidaten.
- HA-Release-Lane bekommt ein explizites Contract-Handoff als Review-Grundlage.

## Recommended next step
- Reviewer nimmt dieses Dokument + `docs/CORE_RC_PREP_2026-03-27.md` + Bundle-Evidence als Review-Paket.
- Danach Builder entscheidet über Commit-/Squash-/RC-Vorbereitung.
