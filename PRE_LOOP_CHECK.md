# Pre-Loop Version Check (Pflicht!)

## Warum?

Wenn an anderer Stelle entwickelt wurde (z.B. auf GitHub direkt), und wir lokal nicht updaten, entstehen:
- Merge Conflicts
- Vermischte Features
- Versionierung Chaos
- HACS/HA Konformitätsprobleme

---

## Pre-Loop Check (Every 10 min für @groky, Every 15 min für @styx)

### Schritt 1: Local Status Prüfen

```bash
# Core Add-on
cd /config/.openclaw/workspace/pilotsuite-styx-core
git fetch origin
git status

# HA Integration
cd /config/.openclaw/workspace/pilotsuite-styx-ha
git fetch origin
git status
```

**Check:**
- [ ] `git status` zeigt "your branch is up to date" oder "behind by X commits"
- [ ] Keine uncommitted changes (außer本地 docs/manifest updates)
- [ ] Branch: `dev` für @groky, `main` für @styx

### Schritt 2: Latest Release Prüfen

```bash
# Core Add-on
curl -s https://api.github.com/repos/GreenhillEfka/pilotsuite-styx-core/releases/latest | jq -r '.tag_name'

# HA Integration
curl -s https://api.github.com/repos/GreenhillEfka/pilotsuite-styx-ha/releases/latest | jq -r '.tag_name'
```

**Check:**
- [ ] Latest Release ist mit lokalem Tag synced
- [ ] Keine "stale" Tags (local: vX.Y.Z, GitHub: vX.Y.(Z-1))

### Schritt 3: Branch Status

**@groky (dev Branch):**
- [ ] `git checkout dev` oder `git checkout dev/autopilot-YYYY-MM-DD`
- [ ] `git pull origin dev` (oder `git pull origin dev/autopilot-YYYY-MM-DD`)
- [ ] Latest Commit ist von gestern oder heute

**@styx (main Branch):**
- [ ] `git checkout main`
- [ ] `git pull origin main`
- [ ] Latest Release Tag ist gepusht (GitHub Release existiert)

### Schritt 4: Version Sync

**Beide Repos müssen gleiche Version haben!**

| HA Integration | Core Add-on | Status |
|----------------|-------------|--------|
| v8.0.0 | v7.34.0 | ❌ MISMATCH! @styx muss syncen |
| v8.0.2 | v7.34.0 | ✅ OK (v8.x für HA, v7.x für Core) |

**Lösung bei Mismatch:**
1. @styx merge latest `dev` → `main`
2. Tag erstellen (vX.Y.Z)
3. GitHub Release erstellen
4. Beide repos auf vX.Y.Z syncen

**⚠️ WICHTIG:** Core Add-on (v7.x.x) und HA Integration (v8.x.x) haben **unterschiedliche Major-Versionen**, aber sie sind **kompatibel**!

---

## HASSFest Status (Blocker?)

### Aktueller Stand (2026-02-25):

**Problem:** `KeyError: 'codeowners'` in HASSFest

**Ursache:** HASSFest erwartet andere Manifest-Struktur

**Workaround:** HASSFest temporarily disabled (HACS-only)

### Haben wir das geklärt?

**Nein — HASSFest ist noch disabled!**

**Empfehlung:**
1. HASSFest wieder aktivieren mit korrekter `manifest.json` Struktur
2. Oder: `manifest.json` so anpassen, dass HASSFest passt

**Check:**
```bash
cd /config/.openclaw/workspace/pilotsuite-styx-ha
cat manifest.json | jq '.codeowners'
```

**Wenn `null` oder nicht vorhanden:**
- HASSFest wird fehlschlagen
- Workaround: `manifest.json` anpassen oder HASSFest deaktiviert lassen

---

## Pre-Loop Checklist (Gesamt)

### @groky (Entwicklung)

- [ ] Pre-Loop Check: Local Status Prüfen
- [ ] Pre-Loop Check: Latest Release Prüfen
- [ ] Pre-Loop Check: Branch Status
- [ ] Pre-Loop Check: Version Sync
- [ ] Pre-Loop Check: HASSFest Status (Workaround bestätigt)
- [ ] **NEU:** `git checkout main && git pull origin main` (main syncen, bevor dev entwickelt wird)
- [ ] **NEU:** `git checkout dev` (zurück zu dev)

**Wenn irgendetwas rot ist → Stop! User fragen.**

### @styx (Release Manager)

- [ ] Pre-Loop Check: Local Status Prüfen
- [ ] Pre-Loop Check: Latest Release Prüfen
- [ ] Pre-Loop Check: Branch Status
- [ ] Pre-Loop Check: Version Sync
- [ ] Pre-Loop Check: HASSFest Status (Workaround bestätigt)

**Wenn irgendetwas rot ist → Stop! User fragen.**

---

## Telegram Report Template (Pre-Loop Check)

```
✅ Pre-Loop Check OK

Status:
- Local: ✅ Up to date
- Latest Release: v7.34.0 (Core) / v8.0.2 (HA)
- Branch: ✅ dev (groky) / main (styx)
- Version Sync: ✅ OK
- HASSFest: ⚠️ Workaround (HACS-only)

Next: Feature development / Release
```

---

*Letzte Aktualisierung: 2026-02-25*
*Verantwortlich: @groky & @styx*
