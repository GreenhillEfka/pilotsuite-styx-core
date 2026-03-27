# Core 15.2.0 Sync Anchor — 2026-03-27

## Role posture
- **Lane:** Core
- **Role:** builder/owner sync-anchor note
- **Boundary:** repo/dev only
- **Non-claims:** no release, no install, no live-test

## Current coordinated anchor
- authoritative Core repo: `/config/clawd/team/repos/pilotsuite-styx-core`
- current repo `HEAD`: `cf3e8ac1`
- authoritative paired Core cutover ref for HA release-prep: `cf3e8ac1`
- current Core repo gate: clean worktree
- sharp blocker: none

## Exact pairing decision
The paired Core target for the current HA cutover/releaser-prep path is now **`cf3e8ac1`**.

`cf3e8ac1` supersedes the prior pairing anchor `1d4fc18f` because newer **functional** Core fixes landed and validated green on current `HEAD`:
- `88d3e8ce` — decouple static HA zone imports from client deps
- `081ddb5d` — avoid eager optional API imports in `core_setup`
- `cf3e8ac1` — degrade metrics endpoints cleanly without monitoring deps

## Why `cf3e8ac1` is now authoritative for pairing
`cf3e8ac1` is the exact committed functional cutover anchor that:
- retains the restored startup wiring and canonical ingest routes from `1d4fc18f`
- decouples static HA zone imports from optional client dependencies
- avoids eager optional API imports in `core_setup`
- degrades metrics/health readiness endpoints cleanly when monitoring deps are absent
- sits on top of the truth-chain recovery set already prepared for 15.2.0

## Validation snapshot on current `HEAD`
Validated on current repo `HEAD` (`cf3e8ac1`) with:

```bash
./scripts/check_15_2_0_sync_anchor_consistency.sh
./scripts/run_core_contract_bundle.sh
pytest -q tests/test_metrics_blueprint_contract.py tests/test_core_wiring_contract.py
```

Results:
- sync-anchor checker: **PASS**
- contract bundle: **35 passed**
- targeted metrics/wiring checks: **5 passed**
- warnings: **0**

## Coordination effect
- HA releaser-prep package should now pair against `cf3e8ac1`
- refs older than `cf3e8ac1` (including `1d4fc18f` and `a6eba8a2`) are stale for coordinated cutover purposes
- current Core lane may keep developing on top of `main`, but any future HA pairing change must name a newer exact functional ref explicitly

## Exact next task
Keep Core development tied to the shared release-readiness path while preserving the current HA pairing on `cf3e8ac1` until a newer functional Core cutover ref is explicitly validated and announced.
