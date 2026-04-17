# PS Core — VFM-006 Step 2c legacy HA metadata tombstones

**Date:** 2026-04-17  
**Lane:** PilotClaw / Core  
**Status:** ✅ DONE

## Why this slice exists

Step 2a removed workflow dependence on stale top-level `copilot_core/manifest.json`.

Step 2b removed the same stale HA-owned surfaces from the shipped Core release archive.

But the core repo still advertised legacy HA ownership in-place through the repo-side metadata files themselves:
- `copilot_core/manifest.json`
- `copilot_core/hacs.json`

That left a repo-truth blocker: even though the files no longer drove release automation or shipped artifacts, a reader could still mistake them for live HA metadata.

## Artifacts changed

- `copilot_core/manifest.json`
- `copilot_core/hacs.json`
- `tests/test_vfm006_step2c_legacy_ha_metadata_tombstones.py`

## Blocker removed

The core repo no longer presents those two top-level metadata files as live HACS/custom-component ownership.

Both files are now explicit tombstones that:
- mark themselves as deprecated
- name `pilotsuite-styx-ha` as the owner repo
- point to the canonical HA paths under `custom_components/pilotsuite/`
- stop advertising active integration metadata fields like `config_flow`, `requirements`, `filename`, or `zip_release`

## Boundary effect

This is the first bounded repo-side deprecation prep inside Step 2c.

After this slice:
- workflow truth is clean
- shipped archive truth is clean
- repo-side metadata truth is now also clean for the two most misleading legacy HA metadata files

## Next exact pull

Continue **P-CORE-002 / VFM-006 Step 2c** on the remaining repo-side legacy HA runtime surfaces:
- `copilot_core/config_flow.py`
- `copilot_core/ui/`

## Verification

```bash
cd /config/clawd/team/worktrees/pilotsuite-styx-core-current
/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_vfm006_step2c_legacy_ha_metadata_tombstones.py
```
