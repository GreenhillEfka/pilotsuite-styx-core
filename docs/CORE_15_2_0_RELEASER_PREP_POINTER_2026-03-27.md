# Core 15.2.0 Releaser-Prep Pointer — 2026-03-27

## Role posture
- **Lane:** Core
- **Role:** builder/owner release-readiness pointer
- **Boundary:** repo/dev only
- **Non-claims:** no release, no install, no live-test

## Purpose
Give the Core repo a single repo-local pointer to the current authoritative Core release-readiness package, so reviewer/releaser/HA lanes can consume one stable Core entrypoint without ref/evidence drift.

## Authoritative Core repo
- `/config/clawd/team/repos/pilotsuite-styx-core`

## Current Core candidate state
- candidate version: `15.2.0`
- paired Core cutover ref for HA/releaser coordination: `8b017a74`
- exact live repo-head snapshot is exported via `docs/CORE_15_2_0_RELEASE_MANIFEST_2026-03-27.json` and the workspace release entrypoint when needed
- sync-anchor checker: PASS
- contract bundle on current packaging head: `64 passed / 0 warnings`
- builder stance: hold this cutover line unless a newer explicitly validated functional Core ref appears

## Primary Core release-readiness artifacts
- `docs/CORE_15_2_0_RELEASE_MANIFEST_2026-03-27.json`
- `docs/CORE_15_2_0_SYNC_ANCHOR_2026-03-27.md`
- `docs/CORE_15_2_0_BUILDER_HANDOFF_2026-03-27.md`
- `docs/CORE_REVIEW_PACKET_2026-03-27.md`
- `docs/CORE_RELEASE_INPUT_2026-03-27.md`
- `docs/CORE_GITHUB_RELEASE_NOTES_INPUT_2026-03-27.md`
- `docs/CORE_RELEASE_QUEUE_STATUS_2026-03-28.md`
- `docs/CORE_RELEASE_GOVERNANCE_CHECKLIST_2026-03-28.md`
- `docs/HA_RELEASE_CONTRACT_HANDOFF_2026-03-27.md`

## Repo-local validation companions
- `scripts/export_15_2_0_release_manifest.sh`
- `scripts/refresh_15_2_0_release_surfaces.sh`
- `scripts/check_15_2_0_sync_anchor_consistency.sh`
- `scripts/run_core_contract_bundle.sh`
- `scripts/check_15_2_0_releaser_pointers.sh`
- `scripts/check_15_2_0_release_gate.sh`

## Machine-readable workspace exports
- `/config/clawd/team/workspaces/pilotsuite-stxy-sandbox/handoff/core_release_entrypoint.json`
- `/config/clawd/team/workspaces/pilotsuite-stxy-sandbox/handoff/core_workspace_target.json`
- `/config/clawd/team/workspaces/pilotsuite-stxy-sandbox/handoff/core_release_pairing.json`
- `/config/clawd/team/workspaces/pilotsuite-stxy-sandbox/handoff/core_workspace_harness_evidence.json`
- `/config/clawd/team/workspaces/pilotsuite-stxy-sandbox/handoff/core_rc_input_chain.json`

## Exact next step
Use this pointer as the single repo-local Core entrypoint for review/releaser/HA coordination. Before handoff/cutover discussion, run:
1. `./scripts/refresh_15_2_0_release_surfaces.sh`
2. `./scripts/check_15_2_0_releaser_pointers.sh`
3. `./scripts/check_15_2_0_sync_anchor_consistency.sh`
4. `./scripts/run_core_contract_bundle.sh`
5. `./scripts/check_15_2_0_release_gate.sh`

Governance gate for any **real** release attempt:
1. post the exact group-thread announcement `mache v15.2.0`
2. wait **5 minutes**
3. treat the lane as release-locked during that window
4. rerun cleanliness/validation after the wait
5. abort the cut if cleanliness/validation breaks

Packaging note:
- the committed repo-local manifest is a generated snapshot surface and can lag the newest docs-only HEAD by one commit after docs refreshes; for real handoff/cut discussion, the strict gate refreshes the workspace release entrypoint and treats that workspace surface as authoritative for the exact current repo head while restoring the committed repo manifest to keep the worktree clean.

Only update this pointer when one of these exact fields changes:
1. authoritative Core source/provenance
2. paired Core cutover ref
3. primary Core release-readiness artifacts
4. machine-readable export surfaces
5. validation command set
