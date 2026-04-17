# PS Core — VFM-006 Step 2 path-truth reconciliation

**Date:** 2026-04-17  
**Lane:** PilotClaw / Core  
**Status:** ✅ DONE

## Why this note exists

`VFM-005_BOUNDARY_HARDENING_PLAN.md` still names the Step-2 extraction targets as:

- `addons/pilotsuite/app/copilot_core/config_flow.py`
- `addons/pilotsuite/app/copilot_core/manifest.json`
- `addons/pilotsuite/app/copilot_core/hacs.json`
- `addons/pilotsuite/app/copilot_core/ui/`

At the current repo truth, those files do **not** exist in the add-on tree.

If PilotClaw continued from that outdated path list, the next VFM-006 slice would target the wrong surfaces.

## Current file truth

### Add-on tree (named in the plan)
These Step-2 targets are absent:
- `addons/pilotsuite/app/copilot_core/config_flow.py` ❌
- `addons/pilotsuite/app/copilot_core/manifest.json` ❌
- `addons/pilotsuite/app/copilot_core/hacs.json` ❌
- `addons/pilotsuite/app/copilot_core/ui/` ❌

### Actual stale HA-owned surfaces still present in the repo
These still exist under the top-level `copilot_core/` tree:
- `copilot_core/config_flow.py`
- `copilot_core/manifest.json`
- `copilot_core/hacs.json`
- `copilot_core/ui/`
- `copilot_core/README.md`

This matches the earlier inventory truth in:
- `docs/VFM-006_HA_SURFACE_INVENTORY_2026-04-15.md`

## Active blocker discovered

Core workflow/release surfaces still depend on the stale top-level HA manifest path:

### `.github/workflows/release.yml`
- reads `copilot_core/manifest.json`
- bumps `copilot_core/manifest.json`
- verifies ZIP contents against `copilot_core/manifest.json`
- also references legacy `copilot_core/VERSION` and `copilot_core/rootfs/usr/src/app/VERSION`

### `.github/workflows/sync-versions.yml`
- reads and rewrites HA version metadata via `copilot_core/manifest.json` in the HA repo sync path

## Reconciled Step-2 truth

**Do not** start VFM-006 Step 2 against nonexistent add-on-tree files.

**Do** treat the real Step-2 Core-side cleanup target as:
- stale HA-owned surfaces under top-level `copilot_core/`
- plus the workflow/runtime assumptions that still treat `copilot_core/manifest.json` as shipped Core truth

## Next exact pull

**VFM-006 Step 2a**
- remove workflow/runtime dependence on stale top-level HA metadata, starting with `copilot_core/manifest.json`
- then prepare extraction/deprecation of the remaining legacy HA-owned top-level `copilot_core/` surfaces

## Verification

```bash
cd /config/clawd/team/worktrees/pilotsuite-styx-core-current
ls addons/pilotsuite/app/copilot_core/config_flow.py addons/pilotsuite/app/copilot_core/manifest.json addons/pilotsuite/app/copilot_core/hacs.json
find copilot_core -maxdepth 2 \( -name 'config_flow.py' -o -name 'manifest.json' -o -name 'hacs.json' -o -path 'copilot_core/ui' -o -path 'copilot_core/ui/*' \) | sort
grep -Rni "copilot_core/manifest.json\|copilot_core/config_flow.py\|copilot_core/hacs.json\|copilot_core/ui" .github/workflows
```
