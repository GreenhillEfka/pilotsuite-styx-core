# PS Core — VFM-006 Step 2c legacy HA runtime redirects

**Date:** 2026-04-17  
**Lane:** PilotClaw / Core  
**Status:** ✅ DONE

## Why this slice exists

The first Step 2c slice removed the repo-side metadata lie by tombstoning:
- `copilot_core/manifest.json`
- `copilot_core/hacs.json`

The next remaining repo-side blocker was that the Core repo still visibly carried live-looking HA runtime surfaces:
- `copilot_core/config_flow.py`
- `copilot_core/ui/`

Even though Step 2b already removed them from shipped Core archives, the repo itself still needed bounded deprecation prep so those paths stop reading like active Core runtime ownership.

## Artifacts changed

- `copilot_core/config_flow.py`
- `copilot_core/ui/accessibility.py`
- `copilot_core/ui/admin_dashboard.py`
- `copilot_core/ui/analytics_dashboard.py`
- `copilot_core/ui/lovelace_cards.py`
- `copilot_core/ui/mobile_optimization.py`
- `copilot_core/ui/onboarding.py`
- `copilot_core/ui/theme_manager.py`
- `copilot_core/ui/README.md`
- `tests/test_vfm006_step2c_legacy_ha_runtime_redirects.py`

## Blocker removed

The Core repo no longer presents those paths as active Core runtime truth.

### `copilot_core/config_flow.py`
It is now an explicit redirect stub that:
- names `pilotsuite-styx-ha` as the owner repo
- points to `custom_components/pilotsuite/config_flow.py`
- prevents accidental treatment as live Core config-flow logic

### `copilot_core/ui/`
The legacy UI helper files now carry explicit redirect banners, and the directory now has a README that marks the whole surface as:
- HA-owned
- excluded from Core release archives
- pending migration review on the HA side

## Boundary effect

At this point Step 2c has covered the repo-side legacy HA surfaces named in the current bounded pull:
- metadata truth cleaned
- config-flow truth redirected
- UI directory truth redirected

## Next exact pull

Continue **P-CORE-002 / VFM-006** with the next bounded consolidation pass: decide whether the now-explicit legacy HA repo-side surfaces should stay as temporary redirect stubs until extraction, or be fully removed in the next clean delete slice.

## Verification

```bash
cd /config/clawd/team/worktrees/pilotsuite-styx-core-current
/config/clawd/.venv_smoke_gate/bin/python -m pytest -q \
  tests/test_vfm006_step2c_legacy_ha_metadata_tombstones.py \
  tests/test_vfm006_step2c_legacy_ha_runtime_redirects.py
```
