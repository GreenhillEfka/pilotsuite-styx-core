# Core Real Release Runbook — 2026-03-28

## Purpose
Konkrete Runbook-Oberfläche für einen **echten** Core-Release-Cut der vorbereiteten Linie **`v15.2.0`**.

**Boundary:**
- dieses Dokument selbst erzeugt **keinen** Release
- dieses Dokument selbst nimmt **keinen** Release-Lock
- dieses Dokument selbst überspringt **nicht** die 5-Minuten-Regel

## Scope
- **Repo:** `/config/clawd/team/repos/pilotsuite-styx-core`
- **Proposed visible release version:** `v15.2.0`
- **Protected functional pairing ref:** `8b017a74`
- **Current real-cut-ready repo/dev gate:** `./scripts/check_15_2_0_release_gate.sh`
- **Exact current-head handoff surface for real cut discussion:** workspace release entrypoint

## Canonical release mechanism
Der kanonische Release-Pfad für dieses Repo ist der GitHub Actions Workflow:
- `.github/workflows/release.yml`
- Trigger: `workflow_dispatch`
- Required input: `version` im Format `X.Y.Z`

Der Workflow erledigt:
1. Version-Input validieren
2. `VERSION`, `copilot_core/VERSION`, `copilot_core/rootfs/usr/src/app/VERSION` auf die Zielversion setzen
3. `copilot_core/manifest.json` auf die Zielversion setzen
4. Version-Konsistenz prüfen
5. den Bump committen
6. `vX.Y.Z` taggen
7. `main` + Tags pushen
8. GitHub Release erstellen
9. ZIP-Asset bauen und hochladen
10. ZIP-Inhalt prüfen

## Mandatory governance sequence before any real cut
Do **all** of the following in order:

1. Post the exact group-thread announcement:
   ```text
   mache v15.2.0
   ```
2. Wait **5 minutes**
3. Treat the Core lane/repo as release-locked during that waiting window, preferably by creating the repo-local lock file with the **actual group-thread announcement timestamp**:
   ```bash
   ./scripts/create_15_2_0_release_lock.sh <owner> <announcement_at_utc>
   ```
   Example:
   ```bash
   ./scripts/create_15_2_0_release_lock.sh pilotclaw 2026-03-28T03:45:00Z
   ```
4. Rerun:
   ```bash
   ./scripts/check_15_2_0_release_gate.sh
   ```
   If a lock file is present, the gate will validate it via `./scripts/check_15_2_0_release_lock.sh`.
5. Only proceed if the gate is still green and the lane remains clean/validated/lane-ready

If cleanliness or validation breaks during the waiting window, abort the cut, clear any active repo-local lock with `./scripts/clear_15_2_0_release_lock.sh`, and push the lane back to builder/reviewer work.

## Pre-cut operator checklist
- [ ] `mache v15.2.0` posted in the correct group thread
- [ ] 5-minute wait fully elapsed
- [ ] repo-local `RELEASE_LOCK.md` created for the active cut window with the real group-thread announcement timestamp (recommended via `./scripts/create_15_2_0_release_lock.sh <owner> <announcement_at_utc>`)
- [ ] no competing release window is active on this repo/lane
- [ ] `./scripts/check_15_2_0_release_gate.sh` is green
- [ ] reviewer/releaser packet is current:
  - `docs/CORE_15_2_0_RELEASER_PREP_POINTER_2026-03-27.md`
  - `docs/CORE_RELEASE_QUEUE_STATUS_2026-03-28.md`
  - `docs/CORE_RELEASE_GOVERNANCE_CHECKLIST_2026-03-28.md`
  - `docs/CORE_GITHUB_RELEASE_NOTES_INPUT_2026-03-27.md`
- [ ] workspace release entrypoint reflects the exact current HEAD

## Preferred real-cut path: GitHub Actions UI
1. Open GitHub → **Actions** → **Release**
2. Click **Run workflow**
3. Enter version:
   ```text
   15.2.0
   ```
4. Start the workflow on `main`
5. Watch it until all release steps are green

## Optional CLI path (only if governance/operator wants CLI)
```bash
gh workflow run release.yml -f version=15.2.0
```

Then monitor the run and verify success before claiming the cut complete.

## Release notes source
Use this repo-local input as the primary notes/changelog drafting surface:
- `docs/CORE_GITHUB_RELEASE_NOTES_INPUT_2026-03-27.md`

If the workflow-generated GitHub release text is too minimal, the releaser should copy the curated bullets from that document into the final release notes.

## Post-cut verification
After the workflow succeeds, verify at minimum:
1. GitHub Release `v15.2.0` exists
2. Tag `v15.2.0` exists on the expected commit created by the workflow
3. ZIP asset uploaded successfully
4. Release page title/body are acceptable
5. version files and manifest on the release commit match `15.2.0`

## Abort / rollback posture
Abort the cut immediately if any of the following occurs before workflow dispatch:
- release gate is not green
- worktree / repo-dev lane no longer reflects the intended state
- competing release window appears
- governance wait/lock rule was not satisfied

If aborting after a repo-local lock was created, clear it explicitly:
```bash
./scripts/clear_15_2_0_release_lock.sh
```

If the workflow itself fails mid-cut, do **not** improvise a silent retry/cut in parallel. Stabilize the failure, keep the lane coordinated, and decide the next step explicitly.

## Fallback posture
Do **not** default to manual `gh release create` / ad-hoc tag pushing while the canonical workflow is available.
Manual fallback is only for an explicit workflow failure / GitHub Actions outage decision, and should be documented as an exception.

## Exact next step from today’s posture
- No release yet.
- If governance wants the real cut next: `mache v15.2.0` → wait 5 minutes → release lock → rerun `./scripts/check_15_2_0_release_gate.sh` → dispatch the Release workflow with version `15.2.0`.
