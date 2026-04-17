# PS Core — VFM-006 installability guardrail smoke

**Date:** 2026-04-17  
**Lane:** PilotClaw / Core  
**Status:** ✅ DONE

## Why this slice exists

After VFM-006 Step 2a through Step 2d removed the stale top-level HA-owned repo surfaces from Core, the remaining risk was boundary regression:

- Core add-on install surfaces could drift away from one another
- workflows could silently fall back to deleted local HA metadata paths
- Python import resolution could still depend on the removed top-level HA surfaces instead of the real add-on package under `addons/pilotsuite/app/`

This smoke closes that proof gap.

## Artifacts changed

- `tests/test_vfm006_installability_guardrail_smoke.py`
- `docs/analysis/PS_CORE_VFM_006_INSTALLABILITY_GUARDRAIL_SMOKE_2026-04-17.md`

## Guardrails proven

### 1. Core install surfaces remain canonical

The smoke asserts the active Core install/version surfaces still agree on one release value:

- `VERSION`
- `addons/pilotsuite/app/VERSION`
- `addons/pilotsuite/config.yaml`

### 2. HA metadata ownership stays externalized

The smoke proves the surviving HA-owned metadata path remains externalized to the HA repo:

- `sync-versions.yml` checks out `pilotsuite-styx-ha`
- HA manifest sync still targets `custom_components/pilotsuite/manifest.json` inside that HA repo
- no local Core-repo resurrection of `copilot_core/manifest.json`, `copilot_core/hacs.json`, `copilot_core/config_flow.py`, or local `custom_components/pilotsuite/*` metadata surfaces is allowed

### 3. Add-on import path still resolves cleanly

The smoke proves a clean add-on-style import resolves `copilot_core` from:

- `addons/pilotsuite/app/copilot_core/__init__.py`

and that runtime version resolution still comes from the add-on version file instead of any deleted legacy HA-owned top-level metadata surface.

## Blocker removed

The smoke immediately exposed one real regression, the root `VERSION` file was still at `20.0.3` while the canonical add-on surfaces already read `20.0.8`.

That drift is now fixed, and VFM-006 has explicit installability proof that the Core repo cleanup did **not** break canonical add-on version truth, HA manifest ownership routing, or the surviving add-on import-path assumptions.

## Verification

```bash
cd /config/clawd/team/worktrees/pilotsuite-styx-core-current
python3 -m py_compile tests/test_vfm006_installability_guardrail_smoke.py
/config/clawd/.venv_smoke_gate/bin/python -m pytest -q \
  tests/test_vfm006_step2c_legacy_ha_surfaces_removed.py \
  tests/test_vfm006_installability_guardrail_smoke.py
rm -f /tmp/pilotsuite-vfm006-installability.zip
git archive --worktree-attributes --format=zip --prefix=pilotsuite-styx-core/ -o /tmp/pilotsuite-vfm006-installability.zip HEAD
unzip -Z1 /tmp/pilotsuite-vfm006-installability.zip | grep -E '^pilotsuite-styx-core/(VERSION|addons/pilotsuite/app/VERSION|addons/pilotsuite/config.yaml)$'
if unzip -Z1 /tmp/pilotsuite-vfm006-installability.zip | grep -Eq '^pilotsuite-styx-core/copilot_core/(config_flow\.py|manifest\.json|hacs\.json|README\.md|ui/)'; then
  echo fail
  exit 1
fi
echo clean
```

## Next exact pull

Carry the now-complete VFM-006 Step-2 closeout into the canonical shared logs and then pull the next prepared Core implementation packet behind the restored add-on/HA boundary truth.
