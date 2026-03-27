# Core Review Packet — 2026-03-27

## Purpose
Kompaktes Review-Paket für die aktuelle Core-Lane.

**Boundary:** Repo/Dev only.
**Not included:** release, install, live-test.
**Authoritative Core repo:** `/config/clawd/team/repos/pilotsuite-styx-core`

## Reviewer start here
### 1) Validate the evidence
```bash
./scripts/run_core_contract_bundle.sh
```
Expected baseline:
- **35 tests passed**
- **0 warnings**

### 2) Review the code scope
#### Core truth chain
- `copilot_core/rootfs/usr/src/app/copilot_core/api/v1/zone_automation.py`
- `copilot_core/rootfs/usr/src/app/copilot_core/core/brain_read_model.py`
- `copilot_core/rootfs/usr/src/app/copilot_core/core/dashboard_read_models.py`
- `copilot_core/rootfs/usr/src/app/copilot_core/core/taxonomy.py`
- `copilot_core/rootfs/usr/src/app/copilot_core/hub/habitus_zones.py`
- `copilot_core/rootfs/usr/src/app/copilot_core/hub/zone_automation.py`

#### Regression evidence / runner
- `tests/test_brain_read_model_contract.py`
- `tests/test_dashboard_read_models_contract.py`
- `tests/test_taxonomy_contract.py`
- `tests/test_zone_truth_sync_contract.py`
- `scripts/run_core_contract_bundle.sh`

### 3) Review the support docs
- `docs/HA_RELEASE_CONTRACT_HANDOFF_2026-03-27.md`
- `docs/CORE_RC_PREP_2026-03-27.md`
- `docs/CORE_RELEASE_INPUT_2026-03-27.md`
- `docs/CORE_BUILDER_HANDOFF_2026-03-27.md`
- `docs/CORE_COMMIT_PREP_2026-03-27.md`
- `docs/CORE_15_2_0_SYNC_ANCHOR_2026-03-27.md`

### 4) Use the current sync decision
- authoritative paired Core cutover ref for HA releaser-prep: `cf3e8ac1`
- current repo `HEAD`: `cf3e8ac1`
- this ref supersedes `1d4fc18f` because newer functional startup/import/metrics hardening is validated green on current `HEAD`

## What changed
### Zone truth chain
- `zone_type`, `enabled_modules`, `ha_entities` explicitly persisted in the Core lane
- HA→Core sync no longer relies only on ad-hoc metadata attachment

### Dashboard read models
- Zone Summary counts `zone_type` instead of incorrectly aggregating `mode`
- Zone Detail keeps `zone_type` + `enabled_modules`
- Zone Detail groups entities via Classification Authority
- Zone Detail mirrors automation module configs only for enabled modules
- System Overview carries per-zone module states and robust brain snapshot payloads

### Classification authority
- balcony/loggia/patio/deck resolve canonically to `terrace`
- garden/garage remain `outside`

### Brain read model
- cached graph growth stays visible when live service is absent

### Contract-bundle runner
- reproducible bundle runner for the current contract suites
- cleans workspace tmp artifacts before and after the run
- leaves no `tmp/` repo noise behind

## Reviewer checklist
### Functional
- [ ] Zone truth metadata survives sync -> hub -> read model path
- [ ] Taxonomy role grouping in Zone Detail is sensible for current consumers
- [ ] System Overview module-state derivation matches automation semantics
- [ ] Brain snapshot normalization is safe for dict and `to_dict()` payloads

### Hygiene
- [ ] Bundle runner stays green from clean repo state
- [ ] No generated tmp artifacts remain after bundle run
- [ ] Docs clearly separate dev/repo evidence from release/install/live

### Cross-lane usefulness
- [ ] HA lane can use `HA_RELEASE_CONTRACT_HANDOFF_2026-03-27.md` directly as review input
- [ ] RC prep + release input docs are sufficient for Builder -> Review -> Release

## Exact next step after review
- If accepted: use `docs/CORE_COMMIT_PREP_2026-03-27.md` to stage/commit or squash the change-set for formal review/release-candidate prep.
- If not accepted: annotate the failing file/path and feed that back into the Core lane as the next exact task.
