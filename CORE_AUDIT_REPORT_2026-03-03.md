# PilotSuite Core Audit Report

**Date:** 2026-03-03  
**Audit Scope:** pilotsuite-styx-core repository  
**Auditor:** @styx (Subagent)  
**Task:** Path inconsistencies, version declarations, and potential mismatches audit

---

## Executive Summary

This audit examined the `pilotsuite-styx-core` repository for:
1. Configuration file consistency (config.yaml, build.yaml)
2. Repository metadata (repository.json)
3. Path references across all markdown documentation files
4. Version declaration consistency
5. Potential mismatches and inconsistencies

**Key Findings:**
- ✅ **Version files are currently synchronized** (v13.0.3 across all locations)
- ⚠️ **Historical version mismatches documented** in markdown files (outdated references)
- ⚠️ **Missing referenced workflow directory** (.github/workflows/pilotsuite-dev/)
- ⚠️ **Multiple repository name variations** in documentation
- ⚠️ **Deprecated submodule references** in documentation

---

## 1. Configuration Files Audit

### 1.1 config.yaml
**Location:** `/config/.openclaw/workspace/pilotsuite-styx-core/copilot_core/config.yaml`

**Current State:**
```yaml
name: PilotSuite Core
version: "13.0.3"
slug: copilot_core
url: https://github.com/GreenhillEfka/pilotsuite-styx-core
homeassistant: "2024.1.0"
```

**Status:** ✅ **VALID**
- Version: 13.0.3 (matches other version files)
- URL: Correct GitHub repository
- Home Assistant minimum version: 2024.1.0
- All required fields present

### 1.2 build.yaml
**Location:** `/config/.openclaw/workspace/pilotsuite-styx-core/copilot_core/build.yaml`

**Current State:**
```yaml
build_from:
  amd64: ghcr.io/home-assistant/amd64-base:3.21
  aarch64: ghcr.io/home-assistant/aarch64-base:3.21
```

**Status:** ✅ **VALID**
- Base images properly specified for both architectures
- Version 3.21 for both amd64 and aarch64

### 1.3 repository.json
**Location:** `/config/.openclaw/workspace/pilotsuite-styx-core/repository.json`

**Current State:**
```json
{
  "name": "PilotSuite Add-ons",
  "url": "https://github.com/GreenhillEfka/pilotsuite-styx-core",
  "maintainer": "GreenhillEfka",
  "channel": "stable",
  "description": "PilotSuite — Styx: AI Home Copilot for Home Assistant..."
}
```

**Status:** ✅ **VALID**
- Repository metadata present and correct
- URL matches config.yaml
- Maintainer field populated

---

## 2. Version File Consistency

### 2.1 Current Version Files

| File Path | Version | Status |
|-----------|---------|--------|
| `/VERSION` | v13.0.3 | ✅ |
| `/copilot_core/VERSION` | 13.0.3 | ✅ |
| `/copilot_core/rootfs/usr/src/app/VERSION` | 13.0.3 | ✅ |
| `/copilot_core/config.yaml` | 13.0.3 | ✅ |
| `/copilot_core/manifest.json` | 13.0.3 | ✅ |

**Status:** ✅ **ALL VERSION FILES SYNCHRONIZED**

### 2.2 Historical Version Mismatches (Documented in Markdown)

**Finding:** Multiple markdown files contain references to outdated version mismatches that have since been resolved, but the documentation remains:

| File | Line | Documented Mismatch | Current Status |
|------|------|---------------------|----------------|
| `reviews/groky-2026-03-01_1340.md` | 141 | VERSION file: 11.8.0 vs config.yaml: 11.9.0 | ⚠️ Historical (resolved) |
| `reviews/groky-20260301-0740.md` | 142 | VERSION: 11.3.0 vs Tag: 11.4.0 | ⚠️ Historical (resolved) |
| `reviews/groky-20260228_220048.md` | 126 | VERSION: 11.2.0 vs Tag: 11.3.0 | ⚠️ Historical (resolved) |
| `reviews/groky-2026-03-02-0620.md` | 265 | VERSION: v12.0.7 vs CHANGELOG: v12.9.0 | ⚠️ Historical (resolved) |
| `reviews/groky-iteration2-2026-03-01_1121.md` | 119 | VERSION: 11.3.0 vs Target: 11.6.0 | ⚠️ Historical (resolved) |

**Recommendation:** These files are historical audit reports and should be kept for reference, but consider adding a note that these issues have been resolved in v13.0.3.

---

## 3. Path Reference Inconsistencies

### 3.1 Repository Name Variations

**Finding:** Documentation references multiple repository name variations:

| Variation | Count | Files | Status |
|-----------|-------|-------|--------|
| `pilotsuite-styx-core` | 321+ | Most files | ✅ Current |
| `pilotsuite-dev/pilotsuite-styx-core` | 18 | Workflow docs | ⚠️ Deprecated path |
| `pilotsuite/pilotsuite-styx-core` | 2 | docs/swagger/README.md, docs/API_COMPLETE.md | ⚠️ Incorrect org |

**Critical Files:**
- `docs/swagger/README.md:186` - References `https://github.com/pilotsuite/pilotsuite-styx-core/issues`
- `docs/API_COMPLETE.md:1006` - References `https://github.com/pilotsuite/pilotsuite-styx-core`

**Impact:** Low - These are documentation links, but should be updated to `GreenhillEfka/pilotsuite-styx-core`

### 3.2 Missing Referenced Paths

**Finding:** Multiple files reference a non-existent workflow directory:

**Missing Path:** `.github/workflows/pilotsuite-dev/github-action-shared.yml`

**Files referencing this path:**
| File | Line | Reference |
|------|------|-----------|
| `reviews/groky-2026-03-01_1340.md` | 214, 224, 231, 252, 266 | `.github/workflows/pilotsuite-dev/github-action-shared.yml` |
| `reviews/groky-20260301-1142.md` | 101, 104, 116 | `pilotsuite-dev/github-action-shared.yml` |
| `reviews/groky-2026-03-01-0920.md` | 158 | `pilotsuite-dev/github-action-shared.yml` |
| `reviews/groky-iteration-2.md` | 175 | `.github/workflows/pilotsuite-dev/github-action-shared.yml` |
| `reviews/groky-20260301-0601.md` | 45, 53, 130 | `pilotsuite-dev/github-action-shared.yml` |
| `releases/v11.3.5-iteration-summary.md` | 63 | `.github/workflows/pilotsuite-dev/github-action-shared.yml` |
| `agents/groky/HEARTBEAT.md` | 5, 25, 56, 68 | `pilotsuite-dev/` workspace structure |

**Status:** 🔴 **CRITICAL** - Referenced workflow files do not exist
**Impact:** CI/CD workflows may fail if they depend on these shared workflows

### 3.3 Submodule Path References

**Finding:** Documentation references multiple submodules, some with unclear status:

| Submodule | Referenced In | Status |
|-----------|---------------|--------|
| `ha-copilot-repo` | Multiple review files | ⚠️ Historical/legacy |
| `styx-fork-core` | Multiple review files | ⚠️ Submodule status unclear |
| `sync-styx` | Multiple review files | ⚠️ Submodule status unclear |
| `ai_home_copilot_hacs_repo` | Multiple files | ⚠️ Deprecated (now pilotsuite-styx-ha) |
| `styx-fork-ha` | memory/2026-02-23-1045.md | ⚠️ Deprecated |

**Files with submodule references:**
- `reviews/groky-2026-03-01-1820.md:22, 148, 171, 197`
- `reviews/open_issues_v12_prep.md:56, 57, 119, 120`
- `reviews/groky-p1-review.md:181` - Error: "No url found for submodule path 'ai_home_copilot_hacs_repo'"
- `iterations/iteration-20260301-1020-cowdya.md:33, 39, 40, 56, 66, 93, 95, 106, 108, 121`
- `reports/commit-summary-2026-03-01-1330.md:126, 128, 129`

**Recommendation:** Clarify submodule status and update documentation accordingly

### 3.4 Deprecated Integration Names

**Finding:** Documentation references old integration names:

| Old Name | New Name | Files |
|----------|----------|-------|
| `ai_home_copilot` | `copilot_ha` or `pilotsuite` | Multiple docs |
| `custom_components/ai_home_copilot` | `custom_components/copilot_ha` | docs/GITHUB_RELEASE_GUIDELINES.md, docs/QUICK_START_GUIDE.md |
| `pilotSuite_rag_conversation` | Unclear | docs/RELEASE_V12.2.0_PLAN.md, docs/RELEASE_V12.1.0_PLAN.md |

**Critical Files:**
- `docs/GITHUB_RELEASE_GUIDELINES.md:53, 125` - References `custom_components/pilotSuite_rag_conversation`
- `docs/RELEASE_V12.2.0_PLAN.md:94-110` - References `custom_components/pilotSuite_rag_conversation`
- `docs/RELEASE_V12.1.0_PLAN.md:125, 143-144` - References `custom_components/pilotSuite_rag_conversation`
- `GROKY_RELEASE_WORKFLOW.md:84, 188` - References `custom_components/copilot_ha`

**Status:** ⚠️ **INCONSISTENT** - Multiple integration names in use across documentation

---

## 4. Path Structure Documentation

### 4.1 Core Application Paths

**Documented Path Structure:**
```
pilotsuite-styx-core/
├── copilot_core/
│   ├── config.yaml (version: 13.0.3)
│   ├── build.yaml
│   ├── manifest.json (version: 13.0.3)
│   ├── VERSION (13.0.3)
│   ├── rootfs/usr/src/app/
│   │   ├── VERSION (13.0.3)
│   │   ├── copilot_core/ (application code)
│   │   └── tests/
│   └── docs/
├── dashboard/
├── docs/
├── tests/
├── .github/workflows/
│   ├── ci.yml
│   ├── production-guard.yml
│   └── sync-versions.yml
└── VERSION (v13.0.3)
```

**Status:** ✅ **VALID** - Path structure is consistent

### 4.2 Dashboard Path References

**Finding:** Dashboard paths are referenced consistently:

| Path Pattern | Count | Status |
|--------------|-------|--------|
| `dashboard/` | 60+ | ✅ Consistent |
| `dashboard/static/` | 20+ | ✅ Consistent |
| `dashboard/api/v1/` | 15+ | ✅ Consistent |
| `dashboard/widgets/` | 10+ | ✅ Consistent |

**No issues found** with dashboard path references.

### 4.3 API Endpoint Path References

**Finding:** API endpoints are documented consistently:

| Endpoint Pattern | Files | Status |
|------------------|-------|--------|
| `/api/v1/zone/dashboard/*` | integration_report_v12.md, fullstack_plan_v12.md | ✅ |
| `/api/v1/dashboard/*` | reviews/groky-2026-03-02-0600.md | ✅ |
| `/api/v1/rag/*` | CHANGELOG.md | ✅ |
| `/api/v1/neurons/*` | integration_report_v12.md | ✅ |

**No issues found** with API endpoint path references.

---

## 5. GitHub URL Inconsistencies

### 5.1 Repository URL Variations

| URL | Count | Status |
|-----|-------|--------|
| `https://github.com/GreenhillEfka/pilotsuite-styx-core` | 100+ | ✅ Correct |
| `https://github.com/GreenhillEfka/pilotsuite-styx-ha` | 30+ | ✅ Correct (HA repo) |
| `https://github.com/pilotsuite/pilotsuite-styx-core` | 2 | ⚠️ Incorrect org |
| `https://github.com/pilotsuite-dev/` | 18 | ⚠️ Deprecated/incorrect |

**Files with incorrect URLs:**
- `docs/swagger/README.md:186` - `https://github.com/pilotsuite/pilotsuite-styx-core/issues`
- `docs/API_COMPLETE.md:1006` - `https://github.com/pilotsuite/pilotsuite-styx-core`

### 5.2 Workflow URL References

**Finding:** Workflow files reference external shared workflows:

```yaml
# From reviews/groky-20260301-1142.md:101-104
uses: ./.github/workflows/pilotsuite-dev/github-action-shared.yml
with:
  repo-path: "pilotsuite-dev/pilotsuite-styx-core"
```

**Status:** 🔴 **CRITICAL** - Referenced workflow does not exist
**Impact:** CI/CD will fail if these workflows are triggered

---

## 6. Version Declaration Summary

### 6.1 Current Version State (2026-03-03)

| Component | Version | File | Status |
|-----------|---------|------|--------|
| Core Add-on | 13.0.3 | config.yaml | ✅ |
| Core Add-on | 13.0.3 | manifest.json | ✅ |
| Core Add-on | 13.0.3 | copilot_core/VERSION | ✅ |
| Core Application | 13.0.3 | copilot_core/rootfs/usr/src/app/VERSION | ✅ |
| Repository | v13.0.3 | VERSION | ✅ |
| CHANGELOG | v13.0.0 | CHANGELOG.md (latest entry) | ⚠️ Minor mismatch |

**Note:** CHANGELOG.md latest entry is v13.0.0, but version files show 13.0.3. This may indicate:
- Patch releases not documented in CHANGELOG
- Version bump without CHANGELOG update

### 6.2 Historical Version Issues (Resolved)

The following version mismatches are documented in markdown files but have been resolved:

1. **v11.3.0 Era** (Feb 2026)
   - VERSION file: 11.2.0
   - config.yaml: 11.3.0
   - Tag: v11.3.0
   - **Status:** Resolved

2. **v11.4.0 Era** (Mar 1, 2026)
   - VERSION file: 11.3.0
   - config.yaml: 11.4.0
   - **Status:** Resolved

3. **v11.6.0 Era** (Mar 1, 2026)
   - VERSION file: 11.3.0
   - Target: 11.6.0
   - **Status:** Resolved

4. **v11.9.0 Era** (Mar 1, 2026)
   - VERSION file: 11.8.0
   - config.yaml: 11.9.0
   - **Status:** Resolved

5. **v12.9.0 Era** (Mar 2, 2026)
   - VERSION file: v12.0.7
   - CHANGELOG: v12.9.0
   - **Status:** Resolved

**Pattern:** Version mismatches were a recurring issue in v11.x and v12.x releases. Current v13.0.3 appears synchronized.

---

## 7. Critical Issues Summary

### 🔴 CRITICAL (Must Fix Before Release)

1. **Missing Shared Workflow Files**
   - **Path:** `.github/workflows/pilotsuite-dev/github-action-shared.yml`
   - **Referenced In:** 7+ markdown files
   - **Impact:** CI/CD workflows will fail
   - **Fix Required:** Either create the missing workflow files or update all references

2. **Incorrect GitHub Organization URLs**
   - **Files:** docs/swagger/README.md:186, docs/API_COMPLETE.md:1006
   - **Current:** `https://github.com/pilotsuite/pilotsuite-styx-core`
   - **Should Be:** `https://github.com/GreenhillEfka/pilotsuite-styx-core`
   - **Impact:** Broken links for users

### ⚠️ WARNING (Should Fix)

3. **Version Documentation Gap**
   - **Issue:** CHANGELOG.md latest entry is v13.0.0, but version files show 13.0.3
   - **Files:** CHANGELOG.md vs VERSION files
   - **Impact:** Confusion about current version
   - **Fix:** Update CHANGELOG.md with v13.0.1, v13.0.2, v13.0.3 changes

4. **Deprecated Integration Names**
   - **Files:** Multiple documentation files
   - **Issue:** References to `ai_home_copilot`, `pilotSuite_rag_conversation`
   - **Impact:** User confusion during installation
   - **Fix:** Standardize on `copilot_ha` or `pilotsuite` naming

5. **Unclear Submodule Status**
   - **Submodules:** ha-copilot-repo, styx-fork-core, sync-styx, ai_home_copilot_hacs_repo
   - **Issue:** Documentation references these but status is unclear
   - **Impact:** Confusion about repository structure
   - **Fix:** Document current submodule status or remove references

### ℹ️ INFO (For Awareness)

6. **Historical Version Mismatch Documentation**
   - **Files:** 10+ historical audit reports
   - **Issue:** Document resolved version mismatches
   - **Impact:** None (historical reference)
   - **Recommendation:** Add "RESOLVED" notes to these files

7. **Workspace Structure References**
   - **Files:** agents/groky/HEARTBEAT.md
   - **Issue:** References to `pilotsuite-dev/` workspace structure
   - **Impact:** May be outdated workspace organization
   - **Recommendation:** Verify current workspace structure

---

## 8. Recommendations

### Immediate Actions (P0)

1. **Fix Missing Workflow Files**
   ```bash
   # Option A: Create missing workflow directory and file
   mkdir -p .github/workflows/pilotsuite-dev/
   # Create github-action-shared.yml with appropriate content
   
   # Option B: Remove references to non-existent workflows
   # Update all markdown files to remove pilotsuite-dev/ references
   ```

2. **Update Incorrect GitHub URLs**
   ```bash
   # Fix docs/swagger/README.md
   sed -i 's|github.com/pilotsuite/pilotsuite-styx-core|github.com/GreenhillEfka/pilotsuite-styx-core|g' docs/swagger/README.md
   
   # Fix docs/API_COMPLETE.md
   sed -i 's|github.com/pilotsuite/pilotsuite-styx-core|github.com/GreenhillEfka/pilotsuite-styx-core|g' docs/API_COMPLETE.md
   ```

3. **Update CHANGELOG.md**
   - Add entries for v13.0.1, v13.0.2, v13.0.3
   - Ensure version matches current VERSION files

### Short-term Actions (P1)

4. **Standardize Integration Naming**
   - Audit all documentation for integration names
   - Standardize on single naming convention (recommend: `copilot_ha`)
   - Update all references

5. **Clarify Submodule Status**
   - Document current submodule configuration
   - Remove references to deprecated submodules
   - Update AGENTS.md or README.md with current structure

6. **Add Resolution Notes to Historical Files**
   - Add "RESOLVED in v13.0.3" notes to historical version mismatch reports
   - Prevents confusion about current state

### Long-term Actions (P2)

7. **Implement Version Sync Automation**
   - Ensure `scripts/sync-ha-core-versions.sh` is working
   - Add pre-release checks for version consistency
   - Consider automated CHANGELOG updates

8. **Documentation Cleanup**
   - Archive or update historical audit reports
   - Create single source of truth for paths and structure
   - Regular documentation audits (quarterly)

---

## 9. Files Requiring Attention

### High Priority (Edit Required)

| File | Issue | Priority |
|------|-------|----------|
| `docs/swagger/README.md` | Incorrect GitHub URL | P0 |
| `docs/API_COMPLETE.md` | Incorrect GitHub URL | P0 |
| `CHANGELOG.md` | Missing v13.0.1-v13.0.3 entries | P0 |
| `agents/groky/HEARTBEAT.md` | Deprecated workspace structure | P1 |
| `GROKY_RELEASE_WORKFLOW.md` | Inconsistent integration names | P1 |

### Medium Priority (Review Recommended)

| File | Issue | Priority |
|------|-------|----------|
| `docs/GITHUB_RELEASE_GUIDELINES.md` | Deprecated integration names | P2 |
| `docs/RELEASE_V12.2.0_PLAN.md` | Deprecated integration names | P2 |
| `docs/RELEASE_V12.1.0_PLAN.md` | Deprecated integration names | P2 |
| `reviews/groky-2026-03-01_1340.md` | References missing workflows | P2 |
| `reviews/groky-20260301-1142.md` | References missing workflows | P2 |

### Low Priority (Historical Reference)

| File | Issue | Priority |
|------|-------|----------|
| `reviews/groky-20260301-0740.md` | Historical version mismatch | P3 |
| `reviews/groky-20260228_220048.md` | Historical version mismatch | P3 |
| `reviews/groky-iteration2-2026-03-01_1121.md` | Historical version mismatch | P3 |
| `reviews/groky-2026-03-02-0620.md` | Historical version mismatch | P3 |

---

## 10. Audit Methodology

This audit was conducted using:

1. **File System Analysis**
   - Located and read all configuration files (config.yaml, build.yaml, repository.json)
   - Scanned all VERSION files across the repository
   - Verified file existence for referenced paths

2. **Markdown Documentation Scan**
   - Searched all 321+ .md files for path references
   - Pattern matching for: repository names, version declarations, file paths
   - Cross-referenced documented paths with actual file system

3. **Version Consistency Check**
   - Compared version numbers across all declaration points
   - Identified historical mismatches from audit reports
   - Verified current synchronization state

4. **URL Validation**
   - Extracted all GitHub URLs from documentation
   - Identified variations and inconsistencies
   - Flagged incorrect organization references

---

## 11. Conclusion

**Overall Assessment:** ⚠️ **MOSTLY HEALTHY with Critical Issues**

**Strengths:**
- ✅ Version files are currently synchronized (v13.0.3)
- ✅ Configuration files (config.yaml, build.yaml) are valid
- ✅ Repository metadata (repository.json) is present and correct
- ✅ Core path structure is well-documented and consistent

**Critical Issues:**
- 🔴 Missing shared workflow files referenced in multiple documents
- 🔴 Incorrect GitHub organization URLs in 2 documentation files
- ⚠️ CHANGELOG.md not fully up to date with current version

**Recommendation:** Address P0 critical issues before next release. P1 and P2 items can be addressed in regular maintenance cycles.

---

**Audit Complete:** 2026-03-03  
**Next Audit Recommended:** 2026-04-03 (monthly) or before next major release  
**Auditor:** @styx (Subagent)
