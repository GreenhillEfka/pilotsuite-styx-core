# PS Core — VFM-006 Step 2d legacy HA doc surface closeout

**Date:** 2026-04-17  
**Lane:** PilotClaw / Core  
**Status:** ✅ DONE

## Why this slice exists

After the Step 2c delete closeout, one stale top-level HA-owned doc surface still remained in the Core repo:

- `copilot_core/README.md`

It was already excluded from Core release archives in Step 2b, but the repo itself still carried HA/HACS integration installation guidance at a misleading top-level Core path.

## Artifacts changed

- removed `copilot_core/README.md`
- updated `CHANGELOG.md`
- extended `tests/test_vfm006_step2c_legacy_ha_surfaces_removed.py`

## Blocker removed

The active Core repo no longer presents a top-level HA integration README as if HA/HACS installation truth lives inside `copilot_core/`.

That closes the remaining release-facing repo doc surface from the bounded VFM-006 legacy HA cleanup pass.

## Verification

```bash
cd /config/clawd/team/worktrees/pilotsuite-styx-core-current
/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_vfm006_step2c_legacy_ha_surfaces_removed.py
```

## Next exact pull

Run the prepared **VFM-006 installability guardrail smoke** against the surviving HA-owned surfaces so boundary cleanup is proven not to have regressed canonical HA metadata/import assumptions.
