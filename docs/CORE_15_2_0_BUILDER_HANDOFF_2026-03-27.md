# Core 15.2.0 Builder Handoff — 2026-03-27

## Role posture
- **Lane:** Core
- **Role:** builder/owner handoff note
- **Boundary:** repo/dev only
- **Non-claims:** no release, no install, no live-test

## Candidate intent
Prepare the next Core recovery candidate as **v15.2.0** on top of the current repo worktree so the contract/truth lane is internally coherent and ready for independent review.

## What is already present in the worktree
The current worktree already contains contract-hardening edits across:
- `copilot_core/rootfs/usr/src/app/copilot_core/api/v1/zone_automation.py`
- `copilot_core/rootfs/usr/src/app/copilot_core/core/brain_read_model.py`
- `copilot_core/rootfs/usr/src/app/copilot_core/core/dashboard_read_models.py`
- `copilot_core/rootfs/usr/src/app/copilot_core/core/taxonomy.py`
- `copilot_core/rootfs/usr/src/app/copilot_core/hub/habitus_zones.py`
- `copilot_core/rootfs/usr/src/app/copilot_core/hub/zone_automation.py`

Current candidate theme:
- zone truth sync carries `zone_type`, `enabled_modules`, and HA entities more explicitly
- dashboard read models classify entities, expose enabled modules, and derive module states more coherently
- brain read model falls back to cached graph growth snapshots
- contract bundle remains the primary evidence path

## Version alignment applied
The canonical version files are now aligned to **15.2.0**:
- `VERSION`
- `copilot_core/VERSION`
- `copilot_core/manifest.json`

Notable correction included in this handoff:
- repo manifest version drift (`15.0.12`) has been corrected to the candidate version line

## Validation snapshot
Validated with:
```bash
./scripts/run_core_contract_bundle.sh
```

Result at handoff:
- **25 tests passed**
- **0 warnings**

## Risks / watch-outs
- This is still a builder candidate, not a release claim.
- The touched dashboard read model surface is broad and should receive explicit review.
- Review should verify downstream consumers tolerate the stronger zone/module metadata now exposed.

## Exact next step
1. Review the current Core worktree diff as the **15.2.0 candidate set**.
2. Stage intended code + tests + docs only.
3. Pass to independent review/release-readiness per governance.
4. Do not install/release before reviewer signoff.
