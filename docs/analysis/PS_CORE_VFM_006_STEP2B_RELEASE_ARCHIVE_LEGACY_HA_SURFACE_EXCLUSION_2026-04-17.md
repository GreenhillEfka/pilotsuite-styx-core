# PS Core — VFM-006 Step 2b release-archive legacy HA-surface exclusion

**Date:** 2026-04-17  
**Lane:** PilotClaw / Core  
**Status:** ✅ DONE

## Why this slice exists

After Step 2a, Core workflow truth no longer depended on stale top-level HA-owned metadata paths.

But the release ZIP was still produced with `git archive`, which meant the stale top-level HA-owned files under `copilot_core/` would still ship unless they were explicitly excluded.

That kept the old boundary alive in the published Core artifact even after the workflow logic was corrected.

## Artifacts changed

- `.gitattributes`
- `.github/workflows/release.yml`

## Blocker removed

The Core release archive no longer ships these stale top-level HA-owned surfaces:
- `copilot_core/config_flow.py`
- `copilot_core/manifest.json`
- `copilot_core/hacs.json`
- `copilot_core/README.md`
- `copilot_core/ui/`

`release.yml` now also fails the ZIP verification step if any of those stale paths reappear in the archive.

## Mechanism

### `.gitattributes`
Added `export-ignore` rules so `git archive` excludes the stale HA-owned top-level surfaces from release ZIPs without forcing an immediate tree delete.

### `release.yml`
Extended ZIP verification so release automation now checks both:
- shipped add-on version truth is still present
- stale top-level HA-owned `copilot_core/` surfaces are absent

## Resulting boundary truth

Step 2a removed workflow dependence on stale HA-owned top-level metadata.

Step 2b now removes those same stale surfaces from the shipped Core archive, while keeping the repo-side extraction/deprecation pass bounded and reversible.

## Next exact pull

Continue **P-CORE-002 / VFM-006** with the next bounded repo-side extraction/deprecation prep for the remaining legacy top-level `copilot_core/` surfaces themselves, now that both workflow truth and release-archive truth are decoupled.

## Verification

```bash
cd /config/clawd/team/worktrees/pilotsuite-styx-core-current
rm -f /tmp/pilotsuite-step2b.zip
git archive --worktree-attributes --format=zip --prefix=pilotsuite-styx-core/ -o /tmp/pilotsuite-step2b.zip HEAD
unzip -Z1 /tmp/pilotsuite-step2b.zip | grep -E '^pilotsuite-styx-core/(VERSION|addons/pilotsuite/app/VERSION|addons/pilotsuite/config.yaml)$'
if unzip -Z1 /tmp/pilotsuite-step2b.zip | grep -Eq '^pilotsuite-styx-core/copilot_core/(config_flow\.py|manifest\.json|hacs\.json|README\.md|ui/)'; then
  echo fail
  exit 1
fi
echo clean
```
