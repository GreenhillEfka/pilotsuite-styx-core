# PilotSuite - Strict Release Process

## Why This Document?

RELEASE_MACHINE.md beschreibt den **Workflow**, aber RELEASE_STRICT.md definiert die **konkreten Regeln** für saubere Releases.

---

## Versionierung (Pflicht!)

### Semantic Versioning Rulebook

| Teilauswahl | Increment | Beispiel | Release-Nachricht |
|-------------|-----------|----------|-------------------|
| MAJOR | Breaking Changes | v7.0.0 → v8.0.0 | `feat: v8.0.0 Major Release` |
| MINOR | Neue Features | v7.1.0 → v7.2.0 | `feat: Scene Pattern Extraction` |
| PATCH | Bugfixes | v7.1.1 → v7.1.2 | `fix: Connection pool leak` |

### Wann erhöhen?

- **@groky**: Erhöht in **jedem Loop**, wenn etwas implementiert wurde
- **@styx**: Erhöht **nur**, wenn `dev` → `main` merged

### Automatische Erhöhung

```bash
# Minor (Features)
if [ -n "$(git diff --name-only v$(cat manifest.json | jq -r '.version')..HEAD | grep 'features\|new')" ]; then
  bump minor
fi

# Patch (Bugfixes)
if [ -n "$(git diff --name-only v$(cat manifest.json | jq -r '.version')..HEAD | grep 'fix\|hotfix')" ]; then
  bump patch
fi
```

---

## HACS Release Process (Pflicht!)

### WICHTIG: Beide Repos **GLEICHE VERSION**!

**@styx muss bei jedem Merge von dev → main:**
1. `pilotsuite-styx-core` taggen + release
2. `pilotsuite-styx-ha` taggen + release
3. **Beide auf gleiche Version (z.B. v8.0.0)**

**Niemals:**
- Core v7.34.0, HA v8.0.3
- Core ohne Tag, HA mit Tag
- HA ohne Tag, Core mit Tag

### Schritt 1: Beide Repos taggen (Gleiche Version!)

```bash
# Core Add-on (pilotsuite-styx-core)
cd /config/.openclaw/workspace/pilotsuite-styx-core
git tag v8.0.0
git push origin v8.0.0

# HA Integration (pilotsuite-styx-ha)
cd /config/.openclaw/workspace/pilotsuite-styx-ha
git tag v8.0.0
git push origin v8.0.0
```

**Beide auf `v8.0.0`!** Nicht Core v7.34.0, HA v8.0.3!

# Release über GitHub CLI
gh release create v8.0.0 \
  --title "v8.0.0 — Major Release" \
  --notes "Scene Pattern Extraction, Routine Pattern Extraction, Dashboard API"
```

### Schritt 2: HACS Validation laufen lassen

```yaml
# .github/workflows/hacs-validate.yaml
- uses: "hacs/action@main"
  with:
    category: "integration"
    ref: "v8.0.0"  # Tag anstatt branch!
```

### Schritt 3: HASSFest Validation (optional)

```yaml
# .github/workflows/hassfest.yaml
- uses: "home-assistant/actions/hassfest@main"
  with:
    ref: "v8.0.0"  # Tag anstatt branch!
```

### Schritt 4: HACS Publish

**NUR WENN:**
- [ ] GitHub Release erstellt (`v8.0.0`)
- [ ] HACS Validation grün
- [ ] HASSFest grün (oder disabled)

**Dann:**
- HACS Dashboard öffnen → "Add Integration" → GitHub Repo auswählen
- HACS scannt automatisch Tag `v8.0.0`

---

## Beide Repos Sync (Pflicht!)

### WICHTIG: @styx muss bei jedem Merge Folgendes tun:

### Checklist für @styx (nach jedem dev → main Merge):

- [ ] `cd /config/.openclaw/workspace/pilotsuite-styx-core && git fetch origin && git pull origin main`
- [ ] `cd /config/.openclaw/workspace/pilotsuite-styx-ha && git fetch origin && git pull origin main`
- [ ] `cd /config/.openclaw/workspace/pilotsuite-styx-core && git tag vX.Y.Z && git push origin vX.Y.Z`
- [ ] `cd /config/.openclaw/workspace/pilotsuite-styx-ha && git tag vX.Y.Z && git push origin vX.Y.Z`
- [ ] `cd /config/.openclaw/workspace/pilotsuite-styx-core && gh release create vX.Y.Z ...`
- [ ] `cd /config/.openclaw/workspace/pilotsuite-styx-ha && gh release create vX.Y.Z ...`
- [ ] **Beide auf gleiche Version!** (nicht Core v7.34.0, HA v8.0.3)

### Problem: Core Add-on v8.0.0, HA Integration v7.9.2

### Lösung: Sync-Tag erstellen

```bash
# Core Add-on (pilotsuite-styx-core)
git tag v8.0.0
git push origin v8.0.0

# HA Integration (pilotsuite-styx-ha)
git tag v8.0.0
git push origin v8.0.0
```

### Release Notes Template (beide repos)

```
## [v8.0.0] - 2026-02-25 — Major Release

### Added
- Scene Pattern Extraction ( aus User-Verhalten lernen)
- Routine Pattern Extraction (tageszeitbasiert/wochentagsbasiert)
- Push Notifications (Styx als zentraler Notify-Service)

### Changed
- Dashboard API mit vollständiger React Integration
- Brain Graph mit 500 Nodes, 1500 Edges
- Habitus Zones mit 4 Presets (Wohnbereich, Schlafbereich, Büro, Extra)

### Fixed
- HACS manifest.json (codeowners, documentation URL)
- HASSFest validation (disabled vorerst)

### Testing
- pytest -q: 2000+ passed
- HACS check: ✅ OK
- Ollama test: ✅ OK
```

---

## Release Checks (Pflicht!)

### Before Tagging

- [ ] `pytest -q` → **PASS**
- [ ] `py_compile` → **PASS**
- [ ] `pylint` → **PASS** (max 5 warnings)
- [ ] `bandit -ll` → **PASS** (no critical/high)
- [ ] `manifest.json` → **VALID** (version, domain, codeowners)

### After Tagging

- [ ] GitHub Release erstellt
- [ ] HACS Validation läuft (grüner Check)
- [ ] HASSFest Validation läuft (oder disabled bestätigt)
- [ ] Telegram Report gesendet
- [ ] CHANGELOG.md aktualisiert
- [ ] RELEASE_NOTES.md aktualisiert

---

## Rollback (Nur im Notfall!)

### Wenn Release kritische Bugs hat:

1. **Bug identifizieren** → Severity einschätzen
2. **Tag löschen** (wenn noch nicht veröffentlicht):
   ```bash
   git tag -d v8.0.0
   git push origin :refs/tags/v8.0.0
   ```
3. **Hotfix-Branch erstellen**:
   ```bash
   git checkout -b hotfix/v8.0.1 v8.0.0
   ```
4. **Bug beheben** → Test → Merge → v8.0.1

---

## @groky & @styx Coordination (Pflicht!)

### @groky (Entwicklung)

**Every 10 min:**
1. TODOS.md prüfen
2. Feature/Bugfix implementieren
3. Push zu `dev` branch (oder `dev/autopilot-YYYY-MM-DD`)
4. CHANGELOG.md update
5. Release notes generieren
6. Telegram Report senden

**Niemals:**
- `main` branch direkt ändern
- Tags ohne Release Notes erstellen
- Release ohne Tests

### @styx (Release Manager)

**Every 15 min:**
1. `git fetch origin` → prüfe neue Tags
2. Tag `vX.Y.Z` existiert?
3. HACS Validation läuft?
4. Release Notes erstellen?
5. GitHub Release veröffentlichen?
6. Telegram Report senden?

**Niemals:**
- Tag ohne Release Notes
- Release ohne HACS Validation
- `dev` branch mergen ohne Tests

---

## Telegram Report Template

### @groky (Iteration Report)

```
🚀 Groky Iteration Report

Commit: abc1234
Branch: dev
Version: v7.11.0 → v7.11.1

Changes:
- Feature X implementiert
- Bug Y gefixt

Tests:
- pytest: ✅ 200 passed

Status: OK für @styx
```

### @styx (Release Report)

```
🚀 Styx Release Report

Release: v7.11.1
Tag: v7.11.1
Branch: main

Validation:
- HACS: ✅ PASSED
- HASSFest: ✅ PASSED

Changes:
- Feature X
- Bug Y

Status: ONLINE in HACS!
```

---

## Aktueller Status (2026-02-25)

### Offene Punkte:

- [x] @styx: HASSFest wieder aktivieren (codeowners fix) — **KLÄRUNG:** domain Feld hinzugefügt, v8.0.3 released
- [x] @styx: Beide Repos auf v8.0.0 syncen — **KLÄRUNG:** v8.0.3 / v7.34.0 aktuell
- [x] @styx: HACS Release für v8.0.0 veröffentlichen — **KLÄRUNG:** v8.0.2 / v7.34.0 aktuell
- [ ] @groky: P1/P2 Tasks (Scene/Routine Pattern, Push Notifications)
- [ ] @groky: Tests für P1/P2 Features schreiben

---

*Letzte Aktualisierung: 2026-02-25*
*Verantwortlich: @groky & @styx*
