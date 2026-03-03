# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Projektueberblick

**PilotSuite Core Add-on** ist das Gehirn + Stimme der PilotSuite-Plattform. Es laeuft als Home Assistant Add-on (Docker Container) mit Flask/Waitress REST-API auf Port **8909** und bundled Ollama LLM auf Port **11435** (intern).

**Gegenstueck:** [pilotsuite-styx-ha](../pilotsuite-styx-ha) -- HACS Integration (Sensoren, Module, Dashboard)

- **Framework:** Flask 3.0.2 (Web) + Waitress 3.0.0 (WSGI)
- **Sprache:** Python 3.11+
- **Lizenz:** Privat, alle Rechte vorbehalten
- **Version:** Muss in `copilot_core/config.yaml`, `copilot_core/manifest.json` und `copilot_core/rootfs/usr/src/app/VERSION` uebereinstimmen

---

## Entwicklungskommandos

```bash
# Tests ausfuehren (alle)
PYTHONPATH=copilot_core/rootfs/usr/src/app .venv/bin/python -m pytest copilot_core/rootfs/usr/src/app/tests -v --tb=short -x

# Einzelnen Test ausfuehren
PYTHONPATH=copilot_core/rootfs/usr/src/app .venv/bin/python -m pytest copilot_core/rootfs/usr/src/app/tests/test_mood_service.py -v -x

# Tests mit Coverage
PYTHONPATH=copilot_core/rootfs/usr/src/app .venv/bin/python -m pytest copilot_core/rootfs/usr/src/app/tests -v --tb=short --cov=copilot_core/rootfs/usr/src/app/copilot_core --cov-report=term-missing -x

# Syntax-Check (alle Python-Dateien)
.venv/bin/python -m py_compile $(find copilot_core/rootfs/usr/src/app -name '*.py')

# Smoke Test (Flask App erstellen)
PYTHONPATH=copilot_core/rootfs/usr/src/app .venv/bin/python -c "from copilot_core.app import create_app; app = create_app(); print('ok')"
```

---

## Architektur

### Zwei Entry Points (kritisches Design-Detail)

- **`main.py`** (Produktion): Laedt `/data/options.json`, nutzt `init_services()` + `register_blueprints()` aus `core_setup.py`. Registriert **55+ Blueprints** (22 nested + 35+ standalone).
- **`app.py`** (Tests): Flask App Factory mit `api_v1` Blueprint aus `api/v1/blueprint.py`. Registriert nur die **22 nested Blueprints** unter `/api/v1`.
- **Konsequenz:** Tests ueber `app.py` sehen nur Endpoints unter `/api/v1`, nicht die Standalone-Blueprints aus `core_setup.py`. Standalone-Endpoints muessen separat getestet werden.

### Neural Pipeline

```
HA Events --> Event Ingest --> Brain Graph --> Habitus Miner --> Candidates
                                  |               |
                              Neurons          Patterns
                                  |               |
                              Mood Engine    Vorschlaege --> HA Repairs UI
```

1. **Event Ingest**: N3-Envelopes von HA (batched, dedupliziert, idempotent)
2. **Brain Graph**: SQLite WAL, exponential Decay, Pruning (max 500 Nodes, 1500 Edges)
3. **Habitus Miner**: Association Rule Mining mit Wilson-Confidence, zone-basiert
4. **Mood Engine v3.0**: 6 diskrete Zustaende (Softmax + EMA Hysterese) + 5 kontinuierliche Dimensionen
5. **Candidates**: Governed Lifecycle (pending -> offered -> accepted/dismissed)
6. **Neurons**: 25+ in 3 Schichten (Context -> State -> Mood), 60s Evaluationsintervall

### Service-Dict Pattern (`core_setup.py`)

Zentraler Verdrahtungs-Hub — alle Services werden in einem Dict gesammelt und an Blueprints uebergeben:

```python
services = init_services(config=options)   # 24+ Services, jeder in try/except
register_blueprints(app, services)          # Blueprints auf Flask-App
```

**Error Boundary:** Jeder Service ist in try/except gewrappt. Fehlgeschlagene Services werden `None` gesetzt — Blueprint-Code muss damit umgehen:

```python
# In init_services():
try:
    services["my_service"] = MyService(...)
except Exception:
    _LOGGER.exception("Failed to init MyService")
    # services["my_service"] bleibt None
```

### init_services / register_blueprints

- **Nested** (`api/v1/blueprint.py`): Relative Prefixes unter `/api/v1` (22 Blueprints)
- **Standalone** (`core_setup.register_blueprints()`): Absolute Prefixes direkt auf App (35+ via data-driven `_SIMPLE_BLUEPRINTS` Loop + individuell)
- `conversation_bp` existiert absichtlich an `/api/v1/chat/*` UND `/chat/*` (Legacy-Kompatibilitaet)
- **Neue Blueprints:** Standalone in `register_blueprints()` registrieren, es sei denn rein unter `/api/v1`

### Token-Validierung (`api/security.py`)

`validate_token(request)` gibt `True` (gueltig) oder `False` (ungueltig) zurueck. Bevorzugt den `@require_token` Decorator verwenden:

```python
from copilot_core.api.security import require_token

@bp.route("/api/v1/my-endpoint", methods=["POST"])
@require_token
def my_endpoint():
    # Token ist bereits validiert — bei ungueltigem Token wird 401 zurueckgegeben
    ...
```

Alternativen:
- `@optional_token` — setzt `flask.g.token_valid` fuer bedingte Logik
- `validate_token(request)` — manuell pruefen (True/False)

Token-Quellen (Prioritaet): `X-Auth-Token` Header > `Authorization: Bearer` > `COPILOT_AUTH_TOKEN` Env > `/data/options.json: auth_token`

### NeuronManager Callback-Pattern

Multi-Listener-Pattern — mehrere Callbacks pro Event (kein Ueberschreiben):

```python
neuron_manager.on_mood_change(webhook_push_callback)  # Listener 1
neuron_manager.on_mood_change(eventbus_callback)       # Listener 2
```

---

## Docker Build + Runtime

- **Dockerfile:** `copilot_core/Dockerfile` — HA Add-on Base Image, Python 3.11+, Alpine
- **Dependencies:** Alle in Dockerfile definiert (keine requirements.txt). Hauptpakete: Flask 3.0.2, Waitress 3.0.0, Pydantic 2.12.5, neo4j, numpy, websockets
- **Ollama:** Bundled im Container (Alpine edge Package oder Binary-Download)
- **Ollama Models:** `/share/pilotsuite/ollama/models` — NICHT `/data/` (verhindert Backup-Bloat)
- **Startup:** `start_dual.sh` → Ollama Daemon (Port 11435) → Model Pull (`qwen3:0.6b`) → Flask/Waitress (Port 8909)
- **Health Check:** `curl -sf http://localhost:8909/health` alle 30s
- **Konfiguration:** `/data/options.json` (HA Add-on Mount, generiert aus `config.yaml` Optionen)

---

## Tests

Tests in `copilot_core/rootfs/usr/src/app/tests/` (105+ Dateien). `conftest.py` stellt autouse-Fixtures bereit:

- **`reset_auth_token_cache`**: Setzt `_token_cache` in `security.py` vor/nach jedem Test zurueck (60s TTL wuerde sonst State-Leaking verursachen)
- **`reset_circuit_breakers`**: Setzt `ha_supervisor_breaker`, `ollama_breaker`, `cloud_api_breaker` zurueck (offene Breaker wuerden Folgetests beeinflussen)

---

## Hinweise fuer KI-Assistenten

- Neue Services: In `init_services()` initialisieren, in try/except wrappen, im services-Dict zurueckgeben
- Port ist immer 8909 (`PORT` Env-Variable); Ollama intern 11435
- Persistenz: `/data/` (HA Add-on Mount), Ollama Models unter `/share/`
- `datetime.now(timezone.utc)` statt `datetime.utcnow()` (deprecated seit Python 3.12)
- Dokumentation in Deutsch bevorzugt
- Commit-Messages: `feat:`, `fix:`, `chore:` Prefix
- Releases: Immer paired mit pilotsuite-styx-ha (gleiche Versionsnummer)

### Thread-Sicherheit

Flask/Waitress bedient Requests in mehreren Threads:
- Double-Checked Locking fuer Singletons verwenden (siehe `LLMProvider`, `ModuleRegistry`)
- Das `services`-Dict ist read-only nach Initialisierung
- SQLite WAL-Modus mit `busy_timeout=5000` verwenden

### Circuit Breaker

Zwei konfigurierte Instanzen schuetzen vor kaskadierenden Fehlern:
- `ha_supervisor`: 5 Fehler / 30s Recovery (HA Supervisor API)
- `ollama`: 3 Fehler / 60s Recovery (Ollama LLM API)

### Projektprinzipien

| Prinzip | Bedeutung |
|---------|-----------|
| **Local-first** | Alles lokal, kein Cloud-API-Call |
| **Privacy-first** | PII-Redaktion, bounded Storage, opt-in |
| **Governance-first** | Vorschlaege vor Aktionen, Human-in-the-Loop |
| **Safe Defaults** | Max 500 Nodes, 1500 Edges, Persistenz opt-in |

---

## Wichtige Dateien

| Datei | Beschreibung |
|-------|-------------|
| `copilot_core/rootfs/usr/src/app/main.py` | Produktions-Entry-Point |
| `copilot_core/rootfs/usr/src/app/copilot_core/app.py` | Test-Entry-Point / App Factory |
| `copilot_core/rootfs/usr/src/app/copilot_core/core_setup.py` | Service-Init + Blueprint-Registration (zentraler Hub) |
| `copilot_core/rootfs/usr/src/app/copilot_core/api/v1/blueprint.py` | Nested Blueprint-Registry |
| `copilot_core/rootfs/usr/src/app/copilot_core/api/security.py` | Token-Validierung + Decorators |
| `copilot_core/rootfs/usr/src/app/copilot_core/neurons/manager.py` | NeuronManager Pipeline |
| `copilot_core/rootfs/usr/src/app/copilot_core/mood/engine.py` | Unified Mood Engine v3.0 |
| `copilot_core/rootfs/usr/src/app/copilot_core/brain_graph/store.py` | Brain Graph SQLite Store |
| `copilot_core/rootfs/usr/src/app/templates/dashboard.html` | Dashboard SPA |
| `copilot_core/config.yaml` | HA Add-on Manifest (Optionen + Schema) |
| `copilot_core/Dockerfile` | Container-Build (Dependencies, Ollama) |
| `copilot_core/rootfs/usr/src/app/start_dual.sh` | Startup: Ollama + Flask |
| `docs/ARCHITECTURE_DUAL_REPO.md` | Dual-Repo Gesamtkonzept |
| `docs/API_REFERENCE.md` | API-Endpunkte Dokumentation |
