# Core Commit Prep — 2026-03-27

## Purpose
Ausführbare Commit-/Stage-Gruppierung für die aktuelle Core-Lane.

**Boundary:**
- Repo/Dev only
- kein Release
- kein Install
- kein Live-Test

## Current validated baseline
Vor Commit-Prep zuletzt grün:
```bash
./scripts/run_core_contract_bundle.sh
```

Result:
- **32 tests passed**
- **0 warnings**

## Working set
### Modified
- `copilot_core/rootfs/usr/src/app/copilot_core/api/v1/zone_automation.py`
- `copilot_core/rootfs/usr/src/app/copilot_core/core/brain_read_model.py`
- `copilot_core/rootfs/usr/src/app/copilot_core/core/dashboard_read_models.py`
- `copilot_core/rootfs/usr/src/app/copilot_core/core/taxonomy.py`
- `copilot_core/rootfs/usr/src/app/copilot_core/hub/habitus_zones.py`
- `copilot_core/rootfs/usr/src/app/copilot_core/hub/zone_automation.py`

### New
- `tests/test_brain_read_model_contract.py`
- `tests/test_dashboard_read_models_contract.py`
- `tests/test_taxonomy_contract.py`
- `tests/test_zone_truth_sync_contract.py`
- `scripts/run_core_contract_bundle.sh`
- `docs/HA_RELEASE_CONTRACT_HANDOFF_2026-03-27.md`
- `docs/CORE_RC_PREP_2026-03-27.md`
- `docs/CORE_RELEASE_INPUT_2026-03-27.md`
- `docs/CORE_BUILDER_HANDOFF_2026-03-27.md`
- `docs/CORE_COMMIT_PREP_2026-03-27.md`

## Preferred grouping

### Commit Group A — Core truth chain hardening
**Intent:** funktionale Core-Änderungen zusammenhalten

```bash
git add \
  copilot_core/rootfs/usr/src/app/copilot_core/api/v1/zone_automation.py \
  copilot_core/rootfs/usr/src/app/copilot_core/core/brain_read_model.py \
  copilot_core/rootfs/usr/src/app/copilot_core/core/dashboard_read_models.py \
  copilot_core/rootfs/usr/src/app/copilot_core/core/taxonomy.py \
  copilot_core/rootfs/usr/src/app/copilot_core/hub/habitus_zones.py \
  copilot_core/rootfs/usr/src/app/copilot_core/hub/zone_automation.py
```

**Suggested commit message:**
```text
feat(core): harden truth chain across zone sync, taxonomy, brain and dashboard read models
```

### Commit Group B — Contract regression evidence
**Intent:** neue Regression-Suites + reproduzierbarer Bundle-Runner

```bash
git add \
  tests/test_brain_read_model_contract.py \
  tests/test_dashboard_read_models_contract.py \
  tests/test_taxonomy_contract.py \
  tests/test_zone_truth_sync_contract.py \
  scripts/run_core_contract_bundle.sh
```

**Suggested commit message:**
```text
test(core): add contract bundle for truth-chain regression coverage
```

### Commit Group C — Review / handoff / RC prep docs
**Intent:** Review- und Release-Readiness-Artefakte getrennt von Code halten

```bash
git add \
  docs/HA_RELEASE_CONTRACT_HANDOFF_2026-03-27.md \
  docs/CORE_RC_PREP_2026-03-27.md \
  docs/CORE_RELEASE_INPUT_2026-03-27.md \
  docs/CORE_BUILDER_HANDOFF_2026-03-27.md \
  docs/CORE_COMMIT_PREP_2026-03-27.md
```

**Suggested commit message:**
```text
docs(core): prepare review handoff and rc input for contract hardening
```

## Squash option
Wenn ein einzelner sauberer Review-Commit bevorzugt wird:

```bash
git add \
  copilot_core/rootfs/usr/src/app/copilot_core/api/v1/zone_automation.py \
  copilot_core/rootfs/usr/src/app/copilot_core/core/brain_read_model.py \
  copilot_core/rootfs/usr/src/app/copilot_core/core/dashboard_read_models.py \
  copilot_core/rootfs/usr/src/app/copilot_core/core/taxonomy.py \
  copilot_core/rootfs/usr/src/app/copilot_core/hub/habitus_zones.py \
  copilot_core/rootfs/usr/src/app/copilot_core/hub/zone_automation.py \
  tests/test_brain_read_model_contract.py \
  tests/test_dashboard_read_models_contract.py \
  tests/test_taxonomy_contract.py \
  tests/test_zone_truth_sync_contract.py \
  scripts/run_core_contract_bundle.sh \
  docs/HA_RELEASE_CONTRACT_HANDOFF_2026-03-27.md \
  docs/CORE_RC_PREP_2026-03-27.md \
  docs/CORE_RELEASE_INPUT_2026-03-27.md \
  docs/CORE_BUILDER_HANDOFF_2026-03-27.md \
  docs/CORE_COMMIT_PREP_2026-03-27.md
```

**Suggested squash message:**
```text
feat(core): harden truth contracts and bundle release-readiness evidence
```

## Pre-commit checklist
- [ ] `git status` contains only intended files
- [ ] `./scripts/run_core_contract_bundle.sh` still green
- [ ] no generated `tmp/` artifacts returned
- [ ] docs remain clearly marked as repo/dev evidence, not live success claims

## Recommended next step
- Builder chooses either the 3-commit grouping or the squash option above.
- After staging choice, run the bundle once more and move into formal review.
