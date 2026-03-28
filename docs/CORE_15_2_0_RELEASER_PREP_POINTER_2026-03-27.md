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
- `docs/HA_RELEASE_CONTRACT_HANDOFF_2026-03-27.md`

## Repo-local validation companions
- `scripts/export_15_2_0_release_manifest.sh`
- `scripts/check_15_2_0_sync_anchor_consistency.sh`
- `scripts/run_core_contract_bundle.sh`
- `scripts/check_15_2_0_releaser_pointers.sh`

## Machine-readable workspace exports
- `/config/clawd/team/workspaces/pilotsuite-stxy-sandbox/handoff/core_release_entrypoint.json`
- `/config/clawd/team/workspaces/pilotsuite-stxy-sandbox/handoff/core_workspace_target.json`
- `/config/clawd/team/workspaces/pilotsuite-stxy-sandbox/handoff/core_release_pairing.json`
- `/config/clawd/team/workspaces/pilotsuite-stxy-sandbox/handoff/core_workspace_harness_evidence.json`
- `/config/clawd/team/workspaces/pilotsuite-stxy-sandbox/handoff/core_rc_input_chain.json`

## Exact next step
Use this pointer as the single repo-local Core entrypoint for review/releaser/HA coordination. Before handoff/cutover discussion, run:
1. `./scripts/export_15_2_0_release_manifest.sh`
2. `./scripts/check_15_2_0_releaser_pointers.sh`
3. `./scripts/check_15_2_0_sync_anchor_consistency.sh`
4. `./scripts/run_core_contract_bundle.sh`

Only update this pointer when one of these exact fields changes:
1. authoritative Core source/provenance
2. paired Core cutover ref
3. primary Core release-readiness artifacts
4. machine-readable export surfaces
5. validation command set
