# Core Release Governance Checklist — 2026-03-28

## Purpose
Explizite Governance-/Reviewer-/Releaser-Checklist für die Core-Lane.

**Boundary:**
- kein Tag in diesem Dokument
- kein Release in diesem Dokument
- kein Install
- kein Live-Test

## Scope
Diese Checklist gilt für den vorbereiteten Core-Kandidaten **`v15.2.0`** bei geschütztem funktionalem Pairing-Ref **`8b017a74`**.

## Current posture
- Repo/dev lane ist auf Release-Prep getrimmt
- Version proposal für den nächsten sichtbaren Cut: **`v15.2.0`**
- Größerer funktionaler Milestone oberhalb des geschützten Pair-Refs: **`3e135e21`**
- Docs/release-prep lane läuft darüber auf `main`, aber jeder echte Cut braucht vorab eine frisch exportierte Snapshot-Oberfläche

## Builder checklist
- [ ] Worktree clean (an active `RELEASE_LOCK.md` is tolerated by the strict gate)
- [ ] Repo-lokale Manifest-/Pointer-/Handoff-Surfaces sind aktuell
- [ ] `./scripts/check_15_2_0_release_gate.sh` ist grün
- [ ] Workspace release entrypoint ist der exakte Current-HEAD-Snapshot für reale Handoff-/Cut-Diskussionen

## Reviewer / releaser input packet
- `docs/CORE_15_2_0_RELEASER_PREP_POINTER_2026-03-27.md`
- `docs/CORE_15_2_0_SYNC_ANCHOR_2026-03-27.md`
- `docs/CORE_15_2_0_BUILDER_HANDOFF_2026-03-27.md`
- `docs/CORE_REVIEW_PACKET_2026-03-27.md`
- `docs/CORE_RELEASE_INPUT_2026-03-27.md`
- `docs/CORE_GITHUB_RELEASE_NOTES_INPUT_2026-03-27.md`
- `docs/CORE_RELEASE_QUEUE_STATUS_2026-03-28.md`
- `docs/CORE_RELEASE_GOVERNANCE_CHECKLIST_2026-03-28.md`
- `docs/CORE_REAL_RELEASE_RUNBOOK_2026-03-28.md`
- `docs/HA_RELEASE_CONTRACT_HANDOFF_2026-03-27.md`

## Strict release gate commands
```bash
./scripts/check_15_2_0_release_gate.sh
```

Optional release-lock helpers for a real cut window:
```bash
./scripts/create_15_2_0_release_lock.sh <owner> <announcement_at_utc>
./scripts/check_15_2_0_release_lock.sh
./scripts/clear_15_2_0_release_lock.sh
```

Notes:
- the gate refreshes workspace release surfaces itself
- it keeps the repo worktree clean by restoring the committed repo manifest after export
- the workspace release entrypoint is treated as the exact current-head snapshot surface for real handoff/cut discussion
- if `RELEASE_LOCK.md` exists, the gate validates it automatically instead of treating it as dirty drift

## Mandatory real-release governance sequence
Before any actual release attempt, do **all** of the following in order:
1. Post the exact group-thread announcement: `mache v15.2.0`
2. Wait **5 minutes**
3. Treat the Core lane/repo as release-locked during that waiting window
4. Rerun `./scripts/check_15_2_0_release_gate.sh`
5. Only proceed if the gate is still green and the lane stays clean/validated/lane-ready

## Abort conditions
Abort the cut and push the lane back to builder/reviewer work if any of the following becomes true:
- worktree becomes dirty
- workspace release entrypoint no longer matches the exact current HEAD
- contract bundle stops passing
- paired-ref/readiness docs drift out of sync
- another lane/repo already holds the release window

## Lock lifecycle reminder
- create the lock only for an actual coordinated cut window
- validate it before a real cut claim
- clear it with `./scripts/clear_15_2_0_release_lock.sh` if the cut is aborted or once the coordinated window is explicitly closed

## Non-claims
- This checklist does **not** announce a release
- This checklist does **not** take a release lock by itself
- This checklist does **not** authorize skipping the 5-minute wait
