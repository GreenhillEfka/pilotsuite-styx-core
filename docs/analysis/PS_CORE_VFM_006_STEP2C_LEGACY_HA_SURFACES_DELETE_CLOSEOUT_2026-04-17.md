# PS Core — VFM-006 Step 2c legacy HA surfaces delete closeout

**Date:** 2026-04-17  
**Lane:** PilotClaw / Core  
**Status:** ✅ DONE

## Why this slice exists

The earlier Step 2c slices established two facts:
- the legacy HA-owned top-level Core-repo surfaces no longer drove workflows or shipped archives
- the active Core worktree no longer had live consumers for those paths outside the paths themselves plus proof docs/tests

That made a clean delete slice safer and more honest than leaving dead redirect stubs parked in the repo.

## Artifacts removed

- `copilot_core/config_flow.py`
- `copilot_core/manifest.json`
- `copilot_core/hacs.json`
- `copilot_core/ui/accessibility.py`
- `copilot_core/ui/admin_dashboard.py`
- `copilot_core/ui/analytics_dashboard.py`
- `copilot_core/ui/lovelace_cards.py`
- `copilot_core/ui/mobile_optimization.py`
- `copilot_core/ui/onboarding.py`
- `copilot_core/ui/theme_manager.py`
- `copilot_core/ui/README.md`

## Proof update

The temporary redirect/tombstone proof files were replaced with one direct closeout proof:
- `tests/test_vfm006_step2c_legacy_ha_surfaces_removed.py`

## Blocker removed

The active Core repo no longer contains the stale top-level HA-owned `config_flow`, metadata, or `ui/` surfaces at all.

This removes the remaining repo-side Core/HA boundary drift for the currently bounded VFM-006 Step 2c set.

## Verification

```bash
cd /config/clawd/team/worktrees/pilotsuite-styx-core-current
/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_vfm006_step2c_legacy_ha_surfaces_removed.py
```

## Next exact pull

Continue **P-CORE-002 / VFM-006** with the next bounded reconciliation pass on any remaining docs or release notes that still describe those removed top-level HA-owned Core-repo surfaces as if they exist.
