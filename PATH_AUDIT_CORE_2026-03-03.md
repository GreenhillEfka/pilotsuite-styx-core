# PATH AUDIT REPORT - pilotsuite-styx-core

**Datum:** 2026-03-03 13:20 GMT+1  
**Audit-Fokus:** NUR pilotsuite-styx-core Add-on  
**Auftrag:** Pfad-Inkonsistenzen, Version, Fix-Vorschläge

---

## 1. VERSION AUS CONFIG.YAML

| Datei | Version | Status |
|-------|---------|--------|
| `copilot_core/config.yaml` | **13.0.3** | ✅ |
| `copilot_core/VERSION` | 13.0.3 | ✅ |
| `copilot_core/rootfs/usr/src/app/VERSION` | 13.0.3 | ✅ |
| `VERSION` (root) | v13.0.3 | ✅ |

**✅ Version konsistent: 13.0.3**

---

## 2. CONFIG.YAML PRÜFUNG

### Repository-Pfade
| Feld | Wert | Status |
|------|------|--------|
| `url` | `https://github.com/GreenhillEfka/pilotsuite-styx-core` | ✅ Korrekt |
| `slug` | `copilot_core` | ✅ |
| `name` | `PilotSuite Core` | ✅ |

### Panel-Konfiguration
| Feld | Wert | Status |
|------|------|--------|
| `panel_icon` | `mdi:brain` | ✅ |
| `panel_title` | `Styx` | ✅ |
| `ingress` | `true` | ✅ |
| `ingress_port` | `8909` | ✅ |

### API Endpoints
- **Keine API-Endpunkte in config.yaml definiert** (erwartet – Endpoints sind im Code)
- Port `8909` ist korrekt konfiguriert
- `webui`: `http://[HOST]:[PORT:8909]/` ✅

### Optionen
- `conversation_ollama_url`: `http://localhost:11435` ✅
- `searxng_base_url`: `http://192.168.30.18:4041` ✅

**✅ config.yaml: Keine Pfad-Inkonsistenzen**

---

## 3. BUILD.YAML PRÜFUNG

```yaml
build_from:
  amd64: ghcr.io/home-assistant/amd64-base:3.21
  aarch64: ghcr.io/home-assistant/aarch64-base:3.21
```

**✅ build.yaml: Keine Pfade, keine Inkonsistenzen**

---

## 4. REPOSITORY.JSON PRÜFUNG

```json
{
  "name": "PilotSuite Add-ons",
  "url": "https://github.com/GreenhillEfka/pilotsuite-styx-core",
  "maintainer": "GreenhillEfka",
  "channel": "stable",
  "description": "PilotSuite — Styx: AI Home Copilot..."
}
```

**✅ repository.json: URL konsistent mit config.yaml**

---

## 5. *.MD FILES – PFAD-REFERENZEN

### Kritische Pfad-Referenzen in MD-Dateien

#### ✅ KORREKTE Pfade (konsistent mit aktueller Struktur)

| Datei | Pfad-Referenz | Status |
|-------|---------------|--------|
| `AGENTS.md` | `copilot_core/config.yaml` | ✅ |
| `AGENTS.md` | `copilot_core/build.yaml` | ✅ |
| `AGENTS.md` | `copilot_core/rootfs/usr/src/app/` | ✅ |
| `AGENTS.md` | `copilot_core/rootfs/usr/src/app/copilot_core/` | ✅ |
| `AGENTS.md` | `copilot_core/rootfs/usr/src/app/templates/` | ✅ |
| `AGENTS.md` | `copilot_core/rootfs/usr/src/app/static/` | ✅ |
| `AGENTS.md` | `copilot_core/rootfs/usr/src/app/start_dual.sh` | ✅ |
| `AGENTS.md` | `copilot_core/rootfs/usr/src/app/tests/` | ✅ |
| `docs/ARCHITECTURE.md` | `/api/v1/dashboard/...` | ✅ (API-Pfad) |
| `docs/API_COMPLETE.md` | `http://localhost:8909` | ✅ |

#### ⚠️ PROBLEMATISCHE Pfade

| Datei | Zeile | Problematischer Pfad | Issue |
|-------|-------|---------------------|-------|
| `AGENTS.md` | 19 | `/Users/andreas/pilotsuite-styx-core/...` | **Hardcoded lokaler Pfad** – funktioniert nur auf Entwicklungsrechner |
| `docs/RELEASE_DEPLOYMENT_GUIDE.md` | 50,53,69,72,84,97,123,142 | `/path/to/pilotsuite-styx-ha`<br>`/path/to/pilotsuite-styx-core` | **Platzhalter-Pfade** – sollten durch konkrete Pfade ersetzt werden |
| `docs/RELEASE_DEPLOYMENT_GUIDE.md` | 180 | `/path/to/pilotsuite-styx-ha/custom_components/ai_home_copilot/manifest.json` | **Veralteter Component-Name** (`ai_home_copilot` → `copilot_ha` oder `pilotsuite`) |
| `docs/QUICK_START_GUIDE.md` | 17,150 | `ai_home_copilot` | **Veralteter Name** |
| `docs/USER_MANUAL.md` | 405 | `ai_home_copilot.*` | **Veralteter Name** |
| `docs/GITHUB_RELEASE_GUIDELINES.md` | 53,125,263 | `custom_components/pilotSuite_rag_conversation` | **Veralteter Component-Name** |
| `docs/RELEASE_V12.1.0_PLAN.md` | 125,143,150 | `custom_components/pilotSuite_rag_conversation` | **Veralteter Component-Name** |
| `docs/RELEASE_V12.2.0_PLAN.md` | 94-110 | `custom_components/pilotSuite_rag_conversation` | **Veralteter Component-Name** |
| `docs/RAG_ARCHITECTUR.md` | 292,342 | `pilotSuite_rag_conversation` | **Veralteter Component-Name** |
| `README.md` | 35,37 | `custom_components/pilotsuite/` | ⚠️ Unklar – sollte `copilot_ha` sein? |
| `pilotsuite-repos-bericht.md` | 130-131,234-244 | `ai_home_copilot`, `custom_components/ai_home_copilot/*` | **Veralteter Name** |
| `CORE_AUDIT_REPORT_2026-03-03.md` | 160-161,178-179 | `ai_home_copilot_hacs_repo`, `ha-copilot-repo`, `styx-fork-core`, `sync-styx` | **Deprecated Submodule-Referenzen** |
| `GROKY_RELEASE_WORKFLOW.md` | 84,109,111,188 | `custom_components/copilot_ha`, `custom_components/ai_home_copilot` | **Inkonsistente Namen** |
| `VECTOR_STORE_QUICKREF.md` | 161 | `cd /path/to/app` | **Platzhalter-Pfad** |
| `DEVELOPMENT_PLAN.md` | 62,75 | `custom_components/ai_home_copilot` | **Veralteter Name** |

---

## 6. ZUSAMMENFASSUNG DER PFAD-INKONSISTENZEN

### 🔴 KRITISCH (müssen gefixt werden)

| Nr | Problem | Betroffene Dateien | Fix |
|----|---------|-------------------|-----|
| 1 | **Hardcoded lokaler Entwicklungspfad** | `AGENTS.md:19` | `/Users/andreas/pilotsuite-styx-core/...` → `/config/.openclaw/workspace/pilotsuite-styx-core/...` |
| 2 | **Veralteter HA Component-Name** (`ai_home_copilot`, `pilotSuite_rag_conversation`) | `docs/*.md` (10+ Dateien), `README.md`, `pilotsuite-repos-bericht.md` | `ai_home_copilot` → `copilot_ha` (oder aktuellen Namen verwenden) |
| 3 | **Platzhalter-Pfade** (`/path/to/...`) | `docs/RELEASE_DEPLOYMENT_GUIDE.md`, `VECTOR_STORE_QUICKREF.md` | Durch konkrete Pfade ersetzen oder als Code-Beispiele kennzeichnen |

### 🟡 WARNUNG (sollten gefixt werden)

| Nr | Problem | Betroffene Dateien | Fix |
|----|---------|-------------------|-----|
| 4 | **Deprecated Submodule-Referenzen** | `CORE_AUDIT_REPORT_2026-03-03.md` | Dokumentation als historisch markieren oder entfernen |
| 5 | **Inkonsistente Component-Namen** | `GROKY_RELEASE_WORKFLOW.md` | Einheitlichen Namen verwenden (`copilot_ha`) |

---

## 7. KONKRETE FIX-VORSCHLÄGE

### Fix 1: AGENTS.md – Hardcoded Pfad
**Datei:** `AGENTS.md`, Zeile 19  
**Alt:**
```markdown
`cd /Users/andreas/pilotsuite-styx-core/copilot_core/rootfs/usr/src/app && pytest -q tests/test_api_endpoints.py`
```
**Neu:**
```markdown
`cd copilot_core/rootfs/usr/src/app && pytest -q tests/test_api_endpoints.py`
```
*(Relativer Pfad – funktioniert überall)*

---

### Fix 2: docs/RELEASE_DEPLOYMENT_GUIDE.md – Platzhalter-Pfade
**Datei:** `docs/RELEASE_DEPLOYMENT_GUIDE.md` (mehrere Zeilen)  
**Alt:** `/path/to/pilotsuite-styx-ha`, `/path/to/pilotsuite-styx-core`  
**Neu:** 
- Option A: Konkrete Pfade verwenden:
  ```bash
  cd /config/.openclaw/workspace/pilotsuite-styx-ha
  cd /config/.openclaw/workspace/pilotsuite-styx-core
  ```
- Option B: Als Platzhalter kennzeichnen:
  ```bash
  cd <PATH_TO_PILOTSUITE-STYX-HA>
  cd <PATH_TO_PILOTSUITE-STYX-CORE>
  ```

---

### Fix 3: Veraltete Component-Namen in docs/*.md
**Betroffene Dateien:**
- `docs/QUICK_START_GUIDE.md`
- `docs/USER_MANUAL.md`
- `docs/GITHUB_RELEASE_GUIDELINES.md`
- `docs/RELEASE_V12.1.0_PLAN.md`
- `docs/RELEASE_V12.2.0_PLAN.md`
- `docs/RAG_ARCHITECTUR.md`
- `docs/RELEASE_DEPLOYMENT_GUIDE.md`
- `DEVELOPMENT_PLAN.md`
- `pilotsuite-repos-bericht.md`
- `GROKY_RELEASE_WORKFLOW.md`

**Alt:** `ai_home_copilot`, `pilotSuite_rag_conversation`  
**Neu:** `copilot_ha` (oder aktuellen Component-Namen verwenden)

**Beispiel (QUICK_START_GUIDE.md):**
```markdown
1. **HA Integration** (`copilot_ha`) - Sammelt Daten, zeigt Empfehlungen
```

---

### Fix 4: README.md – Component-Pfad
**Datei:** `README.md`, Zeilen 35-37  
**Alt:**
```bash
cp -r custom_components/pilotsuite /config/custom_components/
```
**Neu:**
```bash
cp -r custom_components/copilot_ha /config/custom_components/
```
*(Falls `copilot_ha` der aktuelle Name ist)*

---

### Fix 5: VECTOR_STORE_QUICKREF.md – Platzhalter
**Datei:** `VECTOR_STORE_QUICKREF.md`, Zeile 161  
**Alt:** `cd /path/to/app`  
**Neu:** `cd copilot_core/rootfs/usr/src/app`

---

## 8. EMPFEHLUNGEN

1. **Priorität P0 (sofort fixen):**
   - AGENTS.md: Hardcoded Pfad entfernen
   - RELEASE_DEPLOYMENT_GUIDE.md: Platzhalter-Pfade dokumentieren

2. **Priorität P1 (nächstes Release):**
   - Alle veralteten Component-Namen (`ai_home_copilot`, `pilotSuite_rag_conversation`) aktualisieren
   - README.md: Installationspfad prüfen und aktualisieren

3. **Priorität P2 (Dokumentation bereinigen):**
   - Deprecated Submodule-Referenzen als historisch markieren
   - Alte Release-Pläne (`RELEASE_V12.*.md`) archivieren oder löschen

---

## 9. FAZIT

**Version:** ✅ **13.0.3** (konsistent über alle Dateien)

**Config.yaml:** ✅ Keine Pfad-Inkonsistenzen

**Build.yaml:** ✅ Keine Probleme

**Repository.json:** ✅ URL konsistent

**MD-Dateien:** ⚠️ **11 Dateien mit veralteten Pfad-Referenzen**
- 3 kritische Issues (hardcoded Pfade, veraltete Names)
- 2 Warnungen (deprecated Referenzen)

**Gesamtzustand:** 🟡 **Gut, aber Dokumentations-Schulden vorhanden**

---

**Audit abgeschlossen.**  
**Nächste Schritte:** Fixes nach Priorität umsetzen.
