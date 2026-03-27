# Core Builder Handoff — 2026-03-27

## Role posture
- **Lane:** Core
- **Role:** builder/owner handoff note
- **Boundary:** Repo/Dev only
- **Non-claims:** no release, no install, no live-test
- **Authoritative Core repo:** `/config/clawd/team/repos/pilotsuite-styx-core`

## Why this handoff exists
This note is the explicit restart anchor for the Core lane if the current writer pauses, times out, or hands over for review/commit-prep.

## Current state
### Exact committed anchor
- **Branch:** `main`
- **Commit:** `8b017a74`

### What is already done
- Core contract hardening completed across:
  - Zone Truth Sync
  - Dashboard Read Models
  - Classification Authority
  - Brain Read Model
  - Startup Wiring / Ingest Route Canonicalization
  - Optional Dependency Degradation (metrics + zone health)
  - Contract Bundle Runner
- Review/support artifacts already prepared:
  - `docs/HA_RELEASE_CONTRACT_HANDOFF_2026-03-27.md`
  - `docs/CORE_RC_PREP_2026-03-27.md`
  - `docs/CORE_RELEASE_INPUT_2026-03-27.md`

### Green evidence
Run:
```bash
./scripts/run_core_contract_bundle.sh
```

Current result:
- **36 tests passed**
- **0 warnings**

## Modified/untracked artifact set
### Committed code files in `8b017a74`
- `copilot_core/rootfs/usr/src/app/copilot_core/api/v1/zone_automation.py`
- `copilot_core/rootfs/usr/src/app/copilot_core/core/brain_read_model.py`
- `copilot_core/rootfs/usr/src/app/copilot_core/core/dashboard_read_models.py`
- `copilot_core/rootfs/usr/src/app/copilot_core/core/taxonomy.py`
- `copilot_core/rootfs/usr/src/app/copilot_core/core_setup.py`
- `copilot_core/rootfs/usr/src/app/copilot_core/homeassistant/zone_matcher.py`
- `copilot_core/rootfs/usr/src/app/copilot_core/hub/habitus_zones.py`
- `copilot_core/rootfs/usr/src/app/copilot_core/hub/zone_automation.py`
- `copilot_core/rootfs/usr/src/app/copilot_core/ingest/event_processor.py`
- `copilot_core/rootfs/usr/src/app/copilot_core/api/v1/metrics.py`
- `copilot_core/rootfs/usr/src/app/copilot_core/api/v1/zone_health.py`
- `copilot_core/rootfs/usr/src/app/copilot_core/homeassistant/__init__.py`

### New tests / runner / docs
- `tests/test_brain_read_model_contract.py`
- `tests/test_core_wiring_contract.py`
- `tests/test_dashboard_read_models_contract.py`
- `tests/test_event_processor_import_contract.py`
- `tests/test_taxonomy_contract.py`
- `tests/test_zone_dashboard_contract.py`
- `tests/test_zone_truth_sync_contract.py`
- `tests/test_metrics_blueprint_contract.py`
- `tests/test_zone_health_blueprint_contract.py`
- `scripts/run_core_contract_bundle.sh`
- `docs/HA_RELEASE_CONTRACT_HANDOFF_2026-03-27.md`
- `docs/CORE_RC_PREP_2026-03-27.md`
- `docs/CORE_RELEASE_INPUT_2026-03-27.md`

### Generated noise / do not commit blindly
- `tmp/`
  - produced by contract/integration runs
  - review and clean before commit/release prep

## Exact next task for the next writer
### Review / follow-up pass
1. Review commit **`8b017a74`** against the packet in `docs/CORE_REVIEW_PACKET_2026-03-27.md`
2. Re-run:
   ```bash
   ./scripts/run_core_contract_bundle.sh
   ```
3. If review is green, keep `8b017a74` as the Core handoff anchor
4. If review finds a sharp blocker, cut one follow-up Core-only fix commit on top

## Risks / watch-outs
- `dashboard_read_models.py` is the broadest touch surface in this lane
- `zone_automation.py` now persists explicit zone-truth metadata (`zone_type`, `enabled_modules`, `ha_entities`)
- `scripts/run_core_contract_bundle.sh` now enforces a stronger environment selection and tmp cleanup; review should confirm this is acceptable team-wide
- `tmp/` exists after runs and must not be mistaken for release content

## Suggested commit grouping
### Group 1 — Core truth chain
- `api/v1/zone_automation.py`
- `hub/zone_automation.py`
- `hub/habitus_zones.py`
- `core/taxonomy.py`
- `core/dashboard_read_models.py`
- `core/brain_read_model.py`
- `core_setup.py`
- `homeassistant/zone_matcher.py`
- `ingest/event_processor.py`

### Group 2 — Regression evidence
- `tests/test_brain_read_model_contract.py`
- `tests/test_core_wiring_contract.py`
- `tests/test_dashboard_read_models_contract.py`
- `tests/test_event_processor_import_contract.py`
- `tests/test_taxonomy_contract.py`
- `tests/test_zone_dashboard_contract.py`
- `tests/test_zone_truth_sync_contract.py`
- `tests/test_metrics_blueprint_contract.py`
- `tests/test_zone_health_blueprint_contract.py`
- `scripts/run_core_contract_bundle.sh`

### Group 3 — Review / handoff docs
- `docs/HA_RELEASE_CONTRACT_HANDOFF_2026-03-27.md`
- `docs/CORE_RC_PREP_2026-03-27.md`
- `docs/CORE_RELEASE_INPUT_2026-03-27.md`
- `docs/CORE_BUILDER_HANDOFF_2026-03-27.md`

## Single-writer reminder
If another writer takes over the Core lane, this document is the handoff anchor. Preserve single-writer discipline and continue from the exact next task above.
