# PATH AUDIT REPORT — pilotsuite-styx-core
**Date:** 2026-03-03 10:00 CET  
**Auditor:** @styx (subagent)  
**Trigger:** HA zeigt Core Add-on 2x + Version-Mismatch (v12.x vs v13.x)

---

## 1. FILES CHECKED

### Core Configuration Files
| File | Path | Status |
|------|------|--------|
| `config.yaml` | `pilotsuite-styx-core/copilot_core/config.yaml` | ✅ Read |
| `build.yaml` | `pilotsuite-styx-core/copilot_core/build.yaml` | ✅ Read |
| `manifest.json` | `pilotsuite-styx-core/copilot_core/manifest.json` | ✅ Read |
| `VERSION` | `pilotsuite-styx-core/VERSION` | ✅ Read |
| `VERSION` | `pilotsuite-styx-core/copilot_core/VERSION` | ✅ Read |
| `repository.json` | `pilotsuite-styx-core/repository.json` | ✅ Read |

### HA Repository Files
| File | Path | Status |
|------|------|--------|
| `repository.json` | `pilotsuite-styx-ha/repository.json` | ✅ Read |
| `manifest.json` | `pilotsuite-styx-ha/custom_components/copilot_ha/manifest.json` | ✅ Read |
| `VERSION` | `pilotsuite-styx-ha/VERSION` | ✅ Read |

### Documentation Files Audited
- `CHANGELOG.md` - Version history checked
- `README.md` - Path references checked
- `AGENTS.md` - Repository structure verified
- All `*.md` files in root directory scanned for version/path references

---

## 2. VERSION INFORMATION

### Current Versions (All Synced ✅)

| Component | File | Version | Status |
|-----------|------|---------|--------|
| **Core** | `VERSION` | `v13.0.3` | ✅ |
| **Core** | `copilot_core/VERSION` | `13.0.3` | ✅ |
| **Core** | `copilot_core/config.yaml` | `13.0.3` | ✅ |
| **Core** | `copilot_core/manifest.json` | `13.0.3` | ✅ |
| **HA** | `VERSION` | `v13.0.3` | ✅ |
| **HA** | `custom_components/copilot_ha/manifest.json` | `13.0.3` | ✅ |

**All versions are synchronized at v13.0.3** ✅

---

## 3. PATH INCONSISTENCIES FOUND

### ✅ NO CRITICAL PATH INCONSISTENCIES

The audit found **NO active path inconsistencies** that would cause HA to show the add-on twice.

### Historical Issues (Already Resolved)

Previous audit reports mentioned these issues, which have been **fixed**:

| Issue | Location | Status | Fix |
|-------|----------|--------|-----|
| Duplicate `config.yaml` | `releases/v12.0.0-rc/config.yaml` | ✅ REMOVED | Commit 582a6c9 |
| Duplicate `manifest.json` | `releases/v12.0.0-rc/manifest.json` | ✅ REMOVED | Commit 582a6c9 |
| Version mismatch in manifest | `copilot_core/manifest.json` | ✅ FIXED | Now shows 13.0.3 |

### Legacy Workspace Copies (Not Active)

These paths contain outdated versions but are **NOT registered in HA**:

| Path | Version | Status |
|------|---------|--------|
| `/config/.openclaw/agents/styx/agent/pilotsuite-styx-core/` | v7.8.8 | ⚠️ Legacy |
| `/config/.openclaw/agents/styx/agent/styx-fork-core/` | v7.8.8 | ⚠️ Legacy |
| `/config/.openclaw/workspace-grok-4/pilotsuite-styx-core/` | v8.1.1 | ⚠️ Outdated |

**Recommendation:** These can be safely removed if no longer needed.

---

## 4. ROOT CAUSE ANALYSIS: Why HA Shows Add-on 2x

### Previous Root Cause (Fixed)
The duplicate add-on detection was caused by:
- **Duplicate `config.yaml`** in `releases/v12.0.0-rc/` directory
- HA scans ALL directories and reads every `config.yaml` it finds
- This caused HA to detect:
  - Once from `copilot_core/config.yaml` (v13.x)
  - Once from `releases/v12.0.0-rc/config.yaml` (v12.x)

### Current Status
✅ **FIXED** - The `releases/v12.0.0-rc/` directory has been removed.

**Verification:**
```bash
$ find /config/.openclaw/workspace/pilotsuite-styx-core/releases/ -name "config.yaml"
(no output - no config.yaml files found)

$ find /config/.openclaw/workspace/pilotsuite-styx-ha/releases/ -name "config.yaml"
(no output - no config.yaml files found)
```

---

## 5. PATH STRUCTURE VERIFICATION

### Correct Structure (Current)
```
pilotsuite-styx-core/
├── VERSION (v13.0.3)
├── repository.json
├── copilot_core/
│   ├── VERSION (13.0.3)
│   ├── config.yaml (version: "13.0.3")
│   ├── build.yaml
│   ├── manifest.json (version: "13.0.3")
│   └── rootfs/usr/src/app/
│       ├── VERSION (13.0.3)
│       └── copilot_core/ (runtime app)
└── releases/ (historical docs only, NO config.yaml)
```

### AGENTS.md Documentation
✅ **Accurate** - The `AGENTS.md` file correctly documents:
- Add-on metadata location: `copilot_core/config.yaml`, `copilot_core/build.yaml`
- Runtime app: `copilot_core/rootfs/usr/src/app/`
- Warning: "Do NOT place config.yaml or build.yaml in the root directory"

---

## 6. DOCUMENTATION VERSION REFERENCES

### Files with Historical v12.x References
These files contain historical references to v12.x versions (not problematic):

| File | Reference | Context |
|------|-----------|---------|
| `CHANGELOG.md` | v12.x versions | Historical changelog entries ✅ |
| `integration_check_v12.md` | v12.0.0 | Historical planning doc ℹ️ |
| `integration_report_v12.md` | v12.0.0 | Historical report ℹ️ |
| `fullstack_plan_v12.md` | v12.0.0, v12.1.0 | Historical plan ℹ️ |
| Various `reviews/*.md` | v12.x | Historical reviews ℹ️ |

**Status:** These are historical documents and do NOT affect runtime behavior.

### Files with Correct v13.x References
| File | Version | Status |
|------|---------|--------|
| `FEATURE_MATRIX.md` | v13.0.3 | ✅ Current |
| `VERSION` | v13.0.3 | ✅ Current |
| `CHANGELOG.md` | v13.0.0+ | ✅ Current |

---

## 7. RECOMMENDATIONS

### Immediate Actions (None Required)
✅ All critical issues have been resolved.

### Optional Cleanup
1. **Remove legacy workspace copies** (if no longer needed):
   ```bash
   rm -rf /config/.openclaw/agents/styx/agent/pilotsuite-styx-core/
   rm -rf /config/.openclaw/agents/styx/agent/styx-fork-core/
   rm -rf /config/.openclaw/workspace-grok-4/pilotsuite-styx-core/
   ```

2. **Archive historical v12.x documentation** (optional):
   - Move old planning docs to `docs/archive/` directory
   - Keep `CHANGELOG.md` as-is (historical record)

### Prevention
1. **Never commit `config.yaml` or `manifest.json` to `releases/` directory**
2. **Always run version sync script before releases:**
   ```bash
   ./scripts/sync-ha-core-versions.sh
   ```
3. **Verify with pre-release checklist:**
   ```bash
   # Check for duplicate config files
   find . -name "config.yaml" -type f
   find . -name "manifest.json" -type f
   
   # Verify all versions match
   grep '^version:' copilot_core/config.yaml
   grep '"version":' copilot_core/manifest.json
   cat VERSION
   ```

---

## 8. VERIFICATION COMMANDS

### Quick Version Check
```bash
# Core versions
cat /config/.openclaw/workspace/pilotsuite-styx-core/VERSION
grep '^version:' /config/.openclaw/workspace/pilotsuite-styx-core/copilot_core/config.yaml
grep '"version":' /config/.openclaw/workspace/pilotsuite-styx-core/copilot_core/manifest.json

# HA versions
cat /config/.openclaw/workspace/pilotsuite-styx-ha/VERSION
grep '"version":' /config/.openclaw/workspace/pilotsuite-styx-ha/custom_components/copilot_ha/manifest.json
```

**Expected Output:** All show `13.0.3` or `v13.0.3`

### Duplicate Config Check
```bash
# Should return NO results
find /config/.openclaw/workspace/pilotsuite-styx-core -name "config.yaml" -type f | grep -v copilot_core/config.yaml
find /config/.openclaw/workspace/pilotsuite-styx-ha -name "config.yaml" -type f
```

---

## 9. CONCLUSION

### Summary
✅ **ALL PATH INCONSISTENCIES RESOLVED**

| Check | Status |
|-------|--------|
| Version sync (Core + HA) | ✅ v13.0.3 |
| No duplicate config.yaml files | ✅ Verified |
| No duplicate manifest.json files | ✅ Verified |
| Correct file structure | ✅ Verified |
| Documentation accuracy | ✅ Accurate |

### Why HA Might Still Show Duplicate (If Issue Persists)
If HA still shows the add-on twice after this audit:

1. **HA Cache:** Restart Home Assistant to clear add-on cache
   ```bash
   ha core restart
   ```

2. **Repository Cache:** Remove and re-add the repository in HA:
   - Settings → Add-ons → Add-on Store
   - Remove PilotSuite repository
   - Re-add: `https://github.com/GreenhillEfka/pilotsuite-styx-core`
   - Refresh add-on store

3. **Check HA Supervisor Logs:**
   ```bash
   ha supervisor logs | grep -i "pilot\|copilot\|styx"
   ```

### Files Modified in This Audit
- None (audit only, no changes made)

### Previous Fixes Referenced
- Commit `582a6c9`: Removed duplicate `releases/v12.0.0-rc/` directory
- Commit `507ae87`: Fixed manifest.json version to 13.0.3

---

**Audit Complete:** 2026-03-03 10:00 CET  
**Next Review:** Before next release (v13.1.0)
