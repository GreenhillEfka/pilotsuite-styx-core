# Groky Release Workflow — Home Assistant / HACS konform

**Status:** v13.9.0 (2026-03-13)  
**Ziel:** Robuster Release-Workflow mit HA Conformance Check  
**Thinking-Standard:** `--think=high` (MAXIMALES THINKING FÜR ALLE AGENTEN)

---

## 🧠 THINKING-STANDARD (SEIT 2026-03-03)

**Alle Agenten arbeiten permanent mit `--think=high`:**

```bash
# Standard für alle Sub-Agenten Calls:
@styx --think=high <task>
@groky --think=high <task>
@cowdya --think=high <task>
```

**Warum?**
- ✅ **Gründliche Pfad-Prüfung** (keine übersehenen config.yaml Files)
- ✅ **Tiefe Root-Cause Analyse** statt Symptom-Bekämpfung
- ✅ **Weniger Fehler** durch maximal gründliches Arbeiten
- ✅ **Bessere Code-Quality** durch tiefes Verständnis

**Lesson Learned (2026-03-03):**
- ❌ Oberflächliches Thinking führte zu übersehenen duplicate config.yaml Files
- ❌ HA zeigte Add-on 2x weil nicht gründlich genug geprüft wurde
- ✅ Ab jetzt: IMMER `--think=high` für ALLE Tasks

---

## 📋 Workflow Overview

```
Dev Loop (Phase 1-6)  →  Code Build  →  HA Release Pipeline  →  HA Conformance  →  Dev Loop Phase 7
```

---

## 🚀 Dev Loop Phase 1-6 (Code Build)

### Phase 1: Repo Status
- `git fetch` → status check
- Changes? → dokumentieren

### Phase 2: Bugfix Round (P0)
- Error Isolation
- Connection Pooling

### Phase 3: Feature Extension (P1/P2)
- Neue Features, Endpunkte, APIs

### Phase 4: HA Conformance Check
- manifest.json valid
- HACS structure OK

### Phase 5: Release Notes
- CHANGELOG.md update
- RELEASE_NOTES.md update
- config.yaml version bump

### Phase 6: Status Report
- Telegram an Mensch

---

## 🏁 HA Release Pipeline (nach Phase 6!)

### Step 1: Version Bump

**CRITICAL: Duplicate Config Check!**
- ⚠️ **NEVER** place config.yaml or build.yaml in root directory!
- ⚠️ Root-level config files cause HA to show add-on TWICE!
- ✅ All add-on metadata belongs in `copilot_core/` subdirectory only

**Files zu updaten:**
1. `pilotsuite-styx-core/CHANGELOG.md` (neuer Eintrag x.y.z)
2. `pilotsuite-styx-core/RELEASE_NOTES.md` (neuer Release)
3. `pilotsuite-styx-core/VERSION` (vX.Y.Z)
4. `pilotsuite-styx-core/copilot_core/VERSION` (X.Y.Z)
5. `pilotsuite-styx-core/copilot_core/config.yaml` (version: "X.Y.Z")
6. `pilotsuite-styx-core/copilot_core/manifest.json` (domotz.version: X.Y.Z)
7. `pilotsuite-styx-ha/custom_components/copilot_ha/manifest.json` (version: X.Y.Z)

**Pre-Release Sync Script:**
```bash
# Auto-sync all version files before release
./scripts/sync-ha-core-versions.sh --dry-run  # preview changes
./scripts/sync-ha-core-versions.sh --force    # apply sync
```

### Step 2: Git Commit + Tag

```bash
git add -A
git commit -m "release: vX.Y.Z — [description]"
git push origin dev/groky-main
git checkout main
git merge dev/groky-main --no-ff -m "release: vX.Y.Z"
git tag -a vX.Y.Z -m "PilotSuite vX.Y.Z"
git push origin main
git push origin --tags --force
```

### Step 3: HA Conformance Check

```bash
cd /config/.openclaw/workspace/pilotsuite-styx-ha
hass check_config /tmp/ha-test
# oder hass --script validate custom_components/ai_home_copilot
```

✅ **ERST WENN HA CONFORMANCE OK IST → Phase 7 starten!**

### Step 4: Status Report (Telegram)

**Content:**
- Branch: main (HA-conform)
- Tag: vX.Y.Z
- Hassfest: ✓ compliant
- Files changed
- Testing
- Next: vX.Y+1.0

---

## 🚀 Dev Loop Phase 7 (System Integrity — nur nach HA Release!)

### Dashboard + UX Optimierung

- Dashboard endpoint testen (100 requests, error rate < 1%)
- Frontend/Backend API routes (17/17 OK)
- Config validation (YAML syntax OK)
- UX stress test (100 requests, error rate < 1%)

---

## 📝 Beispiel Release (v7.11.1)

### Files Changed:
- `copilot_core/llm_provider.py` — SearXNG integration
- `copilot_core/api/v1/llm_search.py` — New API endpoint
- `copilot_core/core_setup.py` — Blueprint registration + LLMProvider init
- `CHANGELOG.md`, `RELEASE_NOTES.md`, `config.yaml` — version bump

### Git Workflow:
1. `git commit -m "feat: SearXNG auto-integration, v7.11.1"`
2. `git push origin dev/groky-main --force`
3. `git checkout main`
4. `git merge dev/groky-main --no-ff`
5. `git tag -a v7.11.1`
6. `git push origin main`
7. `git push origin --tags --force`

### HA Conformance:
```bash
hass check_config /tmp/ha-test
# → ✓ compliant
```

### Status Report:
```
✅ PILOTSUITE CORE AUTO-RELEASE v7.11.1
Branch: main (HA-conform, direkt)
Tag: v7.11.1
Hassfest: ✓ compliant
```

---

## ⚠️ WICHTIG: Erst HA Release → Dann Phase 7!

- **Phase 7 (System Integrity)** kommt **ERST NACH** erfolgreichem HA Release!
- HA Conformance Check **MUST PASS** before Phase 7!
- **KEIN** direktes Push zu main ohne HA Conformance!

---

## 🔧 Version Sync Checklist (PRE-RELEASE)

Vor jedem Release-Tag MUSS folgendes synchronisiert sein:

- [ ] `VERSION` (root) — Hauptversionsdatei (vX.Y.Z)
- [ ] `copilot_core/VERSION` — Add-on runtime version (X.Y.Z)
- [ ] `copilot_core/config.yaml` — Add-on metadata version (X.Y.Z)
- [ ] `copilot_core/manifest.json` — Add-on manifest version (X.Y.Z)
- [ ] `custom_components/copilot_ha/manifest.json` — HA integration version (X.Y.Z)

**Script:** `scripts/sync-ha-core-versions.sh` (auto-sync vor release)

**Warnung:** Duplicate config.yaml Dateien im Root führen zu 2x Add-on in HA!

---

**Letzte Aktualisierung:** 2026-02-24 22:45  
**Entwickelt mit:** Groky Dev Check (every 10min)  
**Basiert auf:** pilotsuite-styx-core v7.11.1 + pilotsuite-styx-ha v7.10.1
