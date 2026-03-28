# Core Release Input — 2026-03-27

## Purpose
Vorbereitete Release-/Review-Eingabe für den nächsten Core-Release-Kandidaten.

**Nicht enthalten:**
- kein Versionsbump
- kein Tag
- kein Release
- kein Install
- kein Live-Test
- **Authoritative Core repo:** `/config/clawd/team/repos/pilotsuite-styx-core`

## Candidate scope summary
### Theme
Contract-Härtung der Core-Truth-Lane rund um:
- Zone Truth Sync
- Dashboard Read Models
- Classification Authority
- Brain Read Model
- Startup Wiring / Ingest Route Canonicalization
- Contract Bundle / Review-Readiness

### Candidate artifact set
#### Code
- `copilot_core/rootfs/usr/src/app/copilot_core/api/v1/zone_automation.py`
- `copilot_core/rootfs/usr/src/app/copilot_core/core/brain_read_model.py`
- `copilot_core/rootfs/usr/src/app/copilot_core/core/dashboard_read_models.py`
- `copilot_core/rootfs/usr/src/app/copilot_core/core/taxonomy.py`
- `copilot_core/rootfs/usr/src/app/copilot_core/core_setup.py`
- `copilot_core/rootfs/usr/src/app/copilot_core/homeassistant/zone_matcher.py`
- `copilot_core/rootfs/usr/src/app/copilot_core/hub/habitus_zones.py`
- `copilot_core/rootfs/usr/src/app/copilot_core/hub/zone_automation.py`
- `copilot_core/rootfs/usr/src/app/copilot_core/ingest/event_processor.py`

#### Tests / evidence
- `tests/test_brain_read_model_contract.py`
- `tests/test_core_wiring_contract.py`
- `tests/test_dashboard_read_models_contract.py`
- `tests/test_event_processor_import_contract.py`
- `tests/test_taxonomy_contract.py`
- `tests/test_zone_dashboard_contract.py`
- `tests/test_zone_truth_sync_contract.py`
- `tests/integration/test_workspace_ha_core_contract.py`
- `scripts/run_core_contract_bundle.sh`

#### Review / handoff docs
- `docs/HA_RELEASE_CONTRACT_HANDOFF_2026-03-27.md`
- `docs/CORE_RC_PREP_2026-03-27.md`
- `docs/CORE_15_2_0_SYNC_ANCHOR_2026-03-27.md`

## Evidence snapshot
### Command
```bash
./scripts/run_core_contract_bundle.sh
```

### Result
- **64 tests passed**
- **0 warnings**

## Proposed changelog input (draft, not applied)
```markdown
## [v15.2.0] - 2026-03-27

### Added
- **Core Contract Bundle Runner**: `scripts/run_core_contract_bundle.sh` bündelt die aktuellen Contract-Suites für Zone Truth, Dashboard Read Models, Taxonomy, Brain Read Model und Workspace HA↔Core Contract.
- **Contract Handoff / RC Prep Docs**: `docs/HA_RELEASE_CONTRACT_HANDOFF_2026-03-27.md` und `docs/CORE_RC_PREP_2026-03-27.md` als Review-/Release-Input-Artefakte.

### Changed
- **Zone Truth Sync**: `zone_type`, `enabled_modules` und HA-Entity-Topology werden im Core explizit persistiert.
- **Dashboard Read Models**: Zone Summary/Detail/SystemOverview hängen jetzt sauberer an Zone Truth, Taxonomy, Automation-Lane und Brain-Summary.
- **Classification Authority**: Terrasse/Balkon/Loggia/Patio/Deck werden kanonisch nach `terrace` aufgelöst; Garten/Garage bleiben `outside`.
- **Brain Read Model**: gecachte Graph-Snapshots bleiben auch ohne aktiven BrainGraph-Service sichtbar.
- **Startup / Ingest Wiring**: `events_ingest` bleibt kanonisch auf `/api/v1/events`, `event_processor` importiert wieder aus `copilot_core.core.brain_read_model`, und `map_homeassistant_topology()` ist wieder vorhanden.

### Tests
- Contract-Bundle aktuell grün: 64 Tests.
- Zusätzliche Hardening-/Truth-/Blueprint-Suites für Zone Health, Zone Aggregates, Scenes, Calendar, HomeKit, Conversation, MCP, Onyx, Weather, Styx Voice, Anomaly, Registry-Wiring und Habitus-Handoff sind grün.

### Documentation
- HA-Release-Review-Handoff und Core-RC-Prep ergänzt.
- Repo-lokales GitHub-Release-Notes-Input vorhanden: `docs/CORE_GITHUB_RELEASE_NOTES_INPUT_2026-03-27.md`.
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
- Geschützte Core-Truth-Lane bleibt auf dem funktionalen Pairing-Ref `8b017a74` stabil.
- Darüber hinaus wurden nächste Release-Slices für Zone Health, Zone Aggregates, Scenes, Calendar, HomeKit sowie einen größeren Optional-Blueprint-/Proposal-Hardening-Block gebaut.
- Repo-lokale GitHub-Release-Notes-/manifest-/pointer-Surfaces sind vorbereitet, damit Reviewer/Releaser ohne Ref-Drift arbeiten können.

## Recommended next step
- Reviewer/Releaser nimmt dieses Dokument + `docs/CORE_GITHUB_RELEASE_NOTES_INPUT_2026-03-27.md` + `docs/CORE_RC_PREP_2026-03-27.md` + `docs/CORE_RELEASE_QUEUE_STATUS_2026-03-28.md` + `docs/CORE_RELEASE_GOVERNANCE_CHECKLIST_2026-03-28.md` + `docs/CORE_REAL_RELEASE_RUNBOOK_2026-03-28.md` + Bundle-Evidence als Release-Prep-Paket.
- Geschützter funktionaler Pairing-Ref bleibt Commit **`8b017a74`**.
- Der Recovery-Stand `f1243375` bleibt historisch referenziert; aktueller Packaging-Head wird separat über Manifest/Entrypoint exportiert.
- Vor jedem echten Releaseversuch gilt strikt: `mache v15.2.0` → 5 Minuten warten → Release-Lock → `./scripts/check_15_2_0_release_gate.sh` erneut grün → Release workflow dispatch gemäß Runbook.
