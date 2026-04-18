# PILOTSUITE CORE — Rescueplan Sprint Zusammenfassung

**Datum:** 2026-04-18, Nachtrunde (Europe/Berlin)
**Lane:** PilotClaw Core Development

---

## FERTIG — Iteration 1 (Security + Stabilität)

### ✅ P0-001 Security — Option C (ALL GAPS)
**Artefakt:** `addons/pilotsuite/app/copilot_core/api/security.py`

**GAP-3** ✅ — `is_auth_required()` mit 30s TTL Cache
- `_auth_required_cache: tuple[bool, float]` + `_auth_lock`
- Kein Disk-I/O bei jedem Request mehr

**GAP-1** ✅ — Token Scope Enforcement
- `require_token(f, scopes=('read',))` kwarg + 403 bei fehlendem Scope
- `require_scope(*scopes)` Decorator für Post-Auth Scope-Gates

**GAP-4** ✅ — Admin Scope Enforcement
- `require_admin_token()` prüft `'admin'` in `g.token_scopes`
- Kein Admin-Zugriff ohne Admin-Scope auch wenn Token gültig

**GAP-5** ✅ — Token Lebensdauer
- Auto-Token File: `{token}\n{created_at_unix}`
- `_get_token_age()` + Age-Check in `validate_token()`
- 90 Tage Hard-Limit, 70 Tage Warnung (per env var konfigurierbar)

**Verification:**
```
tests/test_api_security_scope_contract.py → 6/6 passed ✅
tests/test_security_brute_force_protection_contract.py → 4/4 passed ✅
python3 -m py_compile security.py → OK ✅
```

### ✅ P1-007 Brain Graph Store Tests
**Status:** Bereits 13/13 grün (MEMORY.md outdated)

### ✅ P1-008 Tag System Tests
**Status:** Bereits 14/14 grün (MEMORY.md outdated)

---

## FERTIG — Iteration 2 (Voice Pipeline)

### ✅ P1-006 Voice STT/TTS
**Status:** Addon Voice Pipeline vollständig — Intent-Handling, Mood Engine, Context, TTS-Text
**Whisper:** `copilot_core/voice/stt_whisper.py` — Backend-1 (openai-whisper) + Backend-2 (whisper-cpp) + graceful degradation
**Piper:** `copilot_core/voice/tts_piper.py` — Synthese-Framework mit emotion/speed/pitch

---

## FERTIG — Iteration 3 (WebSocket + Visualization)

### ✅ P3-002 WebSocket Echtzeit
**Fix:** `init_websocket(app)` in `create_app()` eingebaut
**Artefakt:** `addons/pilotsuite/app/main.py`
- Flask-SocketIO-Support aktiv wenn verfügbar
- Graceful degradation wenn `flask-socketio` nicht installiert

### ✅ P3-003 Interaktive Graph-Visualisierung
**Fix:** `init_brain_graph_api(svc, renderer)` in `core_setup.py` nach Service-Init eingebaut
**Artefakt:** `addons/pilotsuite/app/copilot_core/core_setup.py`
- GraphService Singleton jetzt korrekt mit konfiguriertem Service versorgt
- Renderer mit `max_render_nodes=120`, `max_render_edges=300`
- `/graph/state`, `/graph/snapshot.svg`, `/graph/stats`, `/graph/nodes` verfügbar

---

## OFFEN — Iteration 4 (Architecture)

### ⚠️ P3-011 Hexagonale Architektur
**Status:** Pattern vorhanden (370 Zeilen `copilot_core/architecture/hexagonal.py`)
**Einschätzung:** Boundary-Enforcement braucht eigenständiges Refactoring — nicht punktuell fixbar
**Empfehlung:** Eigenständiger Task mit Andreas-Freigabe für architekturelle Deep-Dive

---

## TEST STAND

| Suite | Ergebnis |
|-------|---------|
| Base tests/ (86 files, ohne scope) | **80/80 passed** |
| Security scope contract | **6/6 passed** (standalone) |
| Brute force protection | **4/4 passed** |
| Brain graph store | **13/13 passed** |
| Tag system | **14/14 passed** |
| Voice contracts | **alle passed** |

**Test-Pollution-Hinweis:** 6 Security-Tests scheitern im gemeinsamen Run wegen existierendem `flask.request` Modul-Level-Caching. Lösung begonnen (`flask_request` → `request`), vollständige Behebung folgt in separatem Task.

---

## NÄCHSTER OFFENER PULL

P3-011 Hexagonale Architektur — eigenständiges Refactoring mit Andreas-Freigabe