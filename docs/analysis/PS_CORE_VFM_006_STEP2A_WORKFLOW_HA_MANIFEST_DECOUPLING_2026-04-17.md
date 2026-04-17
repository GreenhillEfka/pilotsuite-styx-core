# PS Core — VFM-006 Step 2a workflow HA-manifest decoupling

**Date:** 2026-04-17  
**Lane:** PilotClaw / Core  
**Status:** ✅ DONE

## Why this slice exists

`PS_CORE_VFM_006_STEP2_PATH_TRUTH_RECONCILIATION_2026-04-17.md` proved that the active Core workflow surfaces still treated the stale top-level HA-owned path `copilot_core/manifest.json` as if it were live shipped Core truth.

That blocked the next extraction pass, because release/version automation was still wired to the wrong boundary.

## Artifacts changed

- `.github/workflows/release.yml`
- `.github/workflows/sync-versions.yml`

## Blocker removed

### `release.yml`
The release workflow no longer depends on stale top-level HA metadata or nonexistent legacy Core version files.

It now uses the actual add-on version surfaces:
- `VERSION`
- `addons/pilotsuite/app/VERSION`
- `addons/pilotsuite/config.yaml`

The ZIP verification step now checks those same shipped add-on surfaces instead of probing `copilot_core/manifest.json`.

### `sync-versions.yml`
The HA sync workflow no longer rewrites HA metadata through `copilot_core/manifest.json` in an outdated repo/path model.

It now:
- checks out `${{ github.repository_owner }}/pilotsuite-styx-ha`
- reads HA metadata from `custom_components/pilotsuite/manifest.json`
- syncs that manifest plus HA root `VERSION`
- derives Core truth from the add-on surfaces `addons/pilotsuite/app/VERSION` and `addons/pilotsuite/config.yaml`

## Resulting boundary truth

The active workflow surfaces no longer use `copilot_core/manifest.json` as authoritative shipped Core metadata.

This narrows the remaining Step-2 cleanup to the actual stale top-level HA-owned `copilot_core/` surfaces themselves, instead of leaving hidden workflow dependence behind.

## Next exact pull

Continue **P-CORE-002 / VFM-006** with the next bounded extraction/deprecation prep for the remaining stale top-level HA-owned surfaces under `copilot_core/`, starting with the non-workflow legacy files that still present HA integration boundary drift.

## Verification

Executed in the Core worktree:

```bash
cd /config/clawd/team/worktrees/pilotsuite-styx-core-current
rg -n "copilot_core/manifest\.json|copilot_core/VERSION|copilot_core/rootfs/usr/src/app/VERSION|copilot_core/config\.yaml" \
  .github/workflows/release.yml .github/workflows/sync-versions.yml || true
python3 - <<'PY'
from pathlib import Path
checks = {
    '.github/workflows/release.yml': {
        'must_have': [
            'addons/pilotsuite/app/VERSION',
            'addons/pilotsuite/config.yaml',
            'pilotsuite-styx-core/addons/pilotsuite/app/VERSION',
            'pilotsuite-styx-core/addons/pilotsuite/config.yaml',
        ],
        'must_not_have': [
            'copilot_core/manifest.json',
            'copilot_core/VERSION',
            'copilot_core/rootfs/usr/src/app/VERSION',
            'copilot_core/config.yaml',
        ],
    },
    '.github/workflows/sync-versions.yml': {
        'must_have': [
            'addons/pilotsuite/app/VERSION',
            'addons/pilotsuite/config.yaml',
            'custom_components/pilotsuite/manifest.json',
            'pilotsuite-styx-ha',
        ],
        'must_not_have': [
            'copilot_core/manifest.json',
            'copilot_core/VERSION',
            'GreenhillEfka/Home-Assistant-Copilot',
        ],
    },
}
for path, rules in checks.items():
    text = Path(path).read_text(encoding='utf-8')
    for token in rules['must_have']:
        assert token in text, f'MISSING in {path}: {token}'
    for token in rules['must_not_have']:
        assert token not in text, f'STALE in {path}: {token}'
    print(f'workflow-surface-check=ok {path}')
PY
```

Observed result:
- no stale `copilot_core/manifest.json` / legacy version-path references remain in either workflow
- `workflow-surface-check=ok` for both workflow files
