# Core Release Queue Status — 2026-03-28

## Purpose
Expliziter Queue-/Lock-/Versionsstatus für die Core-Lane.

**Boundary:**
- kein Release
- kein Tag
- kein Install
- kein Live-Test

## Lane verdict
- **Lane:** Core
- **Repo:** `/config/clawd/team/repos/pilotsuite-styx-core`
- **Version proposal for the next visible Core release:** `v15.2.0`
- **Release-readiness posture:** reviewer/releaser-ready on the current repo/dev lane
- **Protected functional pairing ref:** `8b017a74`
- **Current larger functional milestone above the protected pair ref:** `3e135e21`
- **Current docs/release-prep lane:** maintained on `main` above the protected pairing ref, with exact repo-head snapshot to be refreshed via the export surfaces before any real cut

## Evidence snapshot
Validated on the current repo/dev lane with:

```bash
./scripts/check_15_2_0_releaser_pointers.sh
./scripts/check_15_2_0_sync_anchor_consistency.sh
./scripts/run_core_contract_bundle.sh
```

Strict release gate for real-cut readiness:

```bash
./scripts/check_15_2_0_release_gate.sh
```

Optional release-lock helpers for a real cut window:

```bash
./scripts/create_15_2_0_release_lock.sh <owner> <announcement_at_utc>
./scripts/check_15_2_0_release_lock.sh
```

The gate refreshes workspace release surfaces itself and preserves a clean repo worktree by restoring the committed repo manifest after export. If `RELEASE_LOCK.md` exists, the gate validates it automatically instead of treating it as dirty drift.

Result:
- releaser-pointer check: **PASS**
- sync-anchor consistency check: **PASS**
- contract bundle: **64 passed / 0 warnings**
- worktree cleanliness: **clean**

## Queue / lock state
- **Current queue state:** unlocked
- **Current release announcement state:** no exact group-thread announce posted yet by Core for this cut
- **Current release-lock state:** no Core release lock taken yet
- **Collision posture:** do not start tag/release/install/restart actions while another lane holds the release window

## Mandatory release gate for any real cut
Before any actual Core release attempt, all of the following must happen in order:
1. Post the exact group-thread announcement: `mache v15.2.0`
2. Wait **5 minutes**
3. Treat the Core lane/repo as release-locked during that wait
4. Reconfirm cleanliness/validation/lane-readiness after the wait
5. Only then hand off or proceed into the real reviewer/releaser flow

If cleanliness or validation breaks during the wait window, abort the cut and push the lane back to builder/reviewer work.

## Packaging-snapshot caveat
The committed repo-local release manifest is a generated packaging surface and can lag the newest docs-only HEAD by one commit if docs are amended after export. Therefore, for real handoff/cut discussion, treat the freshly refreshed **workspace release entrypoint** as the exact repo-head snapshot surface. The strict gate script `./scripts/check_15_2_0_release_gate.sh` enforces exact workspace-entrypoint-to-HEAD alignment while keeping the repo worktree clean.

## Exact next step
- No release yet.
- If governance wants a real cut next, follow `docs/CORE_REAL_RELEASE_RUNBOOK_2026-03-28.md` exactly.
- The correct next visible move remains: `mache v15.2.0` in the group thread, then 5-minute wait + release lock + fresh validation rerun.
- If governance does **not** want a cut next, continue builder work on the next hard Core slice without touching release/tag/install paths.
