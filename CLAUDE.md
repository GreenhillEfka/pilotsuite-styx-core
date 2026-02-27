# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Projektueberblick

**PilotSuite Core Add-on** ist das Backend fuer die PilotSuite-Plattform. Es laeuft als Home Assistant Add-on auf Port **8909** und stellt eine Flask/Waitress REST-API bereit.

**Gegenstueck:** [pilotsuite-styx-ha](../pilotsuite-styx-ha) -- HACS Integration (Sensoren, Module, Dashboard)

- **Framework:** Flask (Web), Waitress (WSGI Server, 16 Threads, 300 Connections)
- **Sprache:** Python 3.11+
- **Deployment:** Home Assistant Add-on (Docker, Alpine 3.21)
- **Port:** 8909
- **Lizenz:** Privat, alle Rechte vorbehalten

---

## Entwicklungskommandos

```bash
# Syntax-Check
python -m py_compile $(find copilot_core/rootfs/usr/src/app -name '*.py')

# Alle Tests
PYTHONPATH=copilot_core/rootfs/usr/src/app python -m pytest copilot_core/rootfs/usr/src/app/tests -v --tb=short -x

# Einzelne Test-Datei
PYTHONPATH=copilot_core/rootfs/usr/src/app python -m pytest copilot_core/rootfs/usr/src/app/tests/test_brain_graph.py -v --tb=short

# Test nach Name
PYTHONPATH=copilot_core/rootfs/usr/src/app python -m pytest copilot_core/rootfs/usr/src/app/tests -v --tb=short -k "test_mood_engine"

# Tests mit Coverage
PYTHONPATH=copilot_core/rootfs/usr/src/app python -m pytest copilot_core/rootfs/usr/src/app/tests -v --tb=short --cov=copilot_core/rootfs/usr/src/app/copilot_core --cov-report=term-missing -x

# Smoke Test (App Factory)
PYTHONPATH=copilot_core/rootfs/usr/src/app python -c "from copilot_core.app import create_app; app = create_app(); print('ok')"

# Security Scan
bandit -r copilot_core/rootfs/usr/src/app/copilot_core -ll --skip B101,B404,B603
```

---

## Architektur

### Neural Pipeline (Datenflusskette)

```
HA Events → Event Ingest (/api/v1/events/ingest)
                ↓
         Brain Graph Store (SQLite + In-Memory)
                ↓
         Habitus Miner (Association Rule Mining)
                ↓
         Candidates (Vorschlaege mit Governance)
                ↓
         HA Repairs UI (User Approval)
                │
                ├── Neurons (14 Bewertungs-Neuronen)
                └── Mood Engine (6 Zustaende + 5 Dimensionen)
```

### Service-Initialisierung

**Einstiegspunkt:** `main.py` (Waitress) oder `app.py` (Flask App Factory fuer Tests)

**Boot-Kette:**
1. `main.py` laedt `/data/options.json` (HA Supervisor Config)
2. `_restructure_flat_config()` konvertiert flache Keys in verschachtelte Dicts
3. `init_services(config)` in `core_setup.py` erstellt 40+ Services — jeder in try/except (`ModuleErrorBoundary`)
4. `register_blueprints(app, services)` registriert 30+ Flask Blueprints
5. Preflight-Checks (Disk, Ollama, HA Supervisor)
6. Waitress startet auf Port 8909

**CopilotConfig Dataclass** (`app.py`): Definiert alle Default-Werte (Persistenz-Pfade, Limits, Feature-Flags). Wird aus `/data/options.json` befuellt.

### Blueprint-Registration (zwei Pfade)

**Pfad A — Relative Prefixes** (in `api/v1/blueprint.py`):
```python
bp = Blueprint('neurons', __name__, url_prefix='/neurons')
api_v1.register_blueprint(bp)
# Ergebnis: /api/v1/neurons
```

**Pfad B — Absolute Prefixes** (in `core_setup.register_blueprints()`):
```python
app.register_blueprint(brain_graph_bp)  # url_prefix="/api/v1/graph"
```

**Warum zwei Pfade?** Pfad A nutzt den `api_v1`-Parent-Blueprint. Blueprints die direkt auf der App registriert werden, brauchen den vollstaendigen Prefix, um `/api/v1/api/v1/...` Dopplung zu vermeiden.

### Brain Graph

- In-Memory + SQLite (WAL Mode) mit `busy_timeout=5000`
- Nodes: Entities, Zonen, Devices, Persons, Concepts (max 500, konfigurierbar bis 5000)
- Edges: temporal, causal, spatial Beziehungen (max 1500, konfigurierbar bis 15000)
- Exponentieller Decay: `score * exp(-ln(2) * age / half_life)` (24h Nodes, 12h Edges)
- Pruning alle 60 Minuten (entfernt Nodes unter `node_min_score`)
- PII-Redaktion auf Labels (Emails, IPs, URLs)

### Unified Mood Engine v3.0

- **6 diskrete Zustaende:** relax, focus, active, night, away, neutral (Softmax + EMA Hysterese)
- **5 kontinuierliche Dimensionen:** comfort, frugality, joy, energy, stress (je 0.0–1.0)
- **Entity Dependencies:** Entities → Rollen (motion, illuminance, media, climate, presence, energy_meter) → Dimensions
- **Persistenz:** SQLite WAL-Mode, 30-Tage Rolling Window, max 1 Write/Minute pro Zone
- **Hysterese:** EMA Alpha ~0.3, Dwell-Time ~5 Min, Softmax Temperature 1.0

### EventBus

Zentraler Pub/Sub (`event_bus.py`):
- `zone.updated` → Brain Graph Node Erstellung
- `event.ingested` → Habitus Mining Trigger
- `neuron.evaluated` → Mood Update
- `habitus.pattern` → Candidate Erstellung

---

## Konventionen

### Service-Dict Pattern

`init_services(config)` in `core_setup.py` initialisiert alle Services und gibt ein Dict zurueck:

```python
services = init_services(config=options)
# services["brain_graph_service"], services["candidate_store"], etc.
```

Das Dict ist read-only nach Initialisierung. Neue Services muessen in `init_services()` erstellt und im Dict zurueckgegeben werden.

### Error Boundary Pattern

Jeder Service wird in try/except initialisiert:

```python
try:
    services["brain_graph_service"] = BrainGraphService(...)
except Exception:
    _LOGGER.exception("Failed to init BrainGraphService")
    # Abhaengige APIs pruefen mit services.get("brain_graph_service")
```

Ein fehlerhafter Service stoppt nicht den gesamten Boot.

### Token-Validierung

- `validate_token(request)` aus `api/security.py`
- Akzeptiert: `X-Auth-Token: <token>` oder `Authorization: Bearer <token>`
- Token aus Env `COPILOT_AUTH_TOKEN` oder `/data/options.json`
- Allowlist ohne Auth: `/`, `/health`, `/ready`, `/version`, `/api/v1/status`, `/api/v1/capabilities`

### Thread-Sicherheit

Flask/Waitress bedient Requests in 16 Threads:
- Double-Checked Locking fuer Singletons (siehe `LLMProvider`)
- `BrainGraphStore._write_lock` (threading.Lock) fuer SQLite-Writes
- Das `services`-Dict ist read-only nach Initialisierung
- SQLite WAL-Modus mit `busy_timeout=5000`

### Circuit Breaker

Schuetzen vor kaskadierenden Fehlern:
- `ha_supervisor`: 5 Fehler / 30s Recovery
- `ollama`: 3 Fehler / 60s Recovery

### Dateistruktur

```
copilot_core/
├── Dockerfile               # Alpine 3.21 + Ollama bundled
├── config.yaml              # HA Add-on Manifest (Version, Ports, Schema)
├── rootfs/usr/src/app/
    ├── main.py              # Waitress Entry Point (Produktion)
    └── copilot_core/
        ├── app.py           # Flask App Factory (Tests/Standalone)
        ├── core_setup.py    # init_services() + register_blueprints() (~1200 Zeilen)
        ├── api/
        │   ├── security.py      # Token-Validierung
        │   ├── rate_limit.py    # Rate Limiting
        │   ├── performance.py   # Performance Middleware
        │   └── v1/
        │       ├── blueprint.py     # Blueprint-Registry (Pfad A)
        │       ├── conversation.py  # OpenAI-kompatible Chat API
        │       ├── events_ingest.py # Event-Eingang
        │       ├── mood.py          # Mood Endpoints
        │       ├── graph.py         # Brain Graph Endpoints
        │       ├── habitus.py       # Habitus Endpoints
        │       ├── candidates.py    # Candidate Endpoints
        │       ├── neurons.py       # Neuron Endpoints
        │       └── ...              # 30+ weitere Blueprints
        ├── brain_graph/     # Store, Service, Model, Render, API
        ├── habitus/         # Service + API
        ├── habitus_miner/   # Mining Engine
        ├── mood/            # Engine, Service, Models, API
        ├── neurons/         # 14 Bewertungs-Neuronen + Manager
        ├── candidates/      # Store + API
        ├── ingest/          # Event Processing Pipeline
        ├── hub/             # 15 Hub-Engines (Phase 5)
        ├── rag/             # RAG Pipeline + Embeddings
        ├── vector_store/    # Semantic Search
        ├── tags/            # Tag Registry (v0.2)
        ├── knowledge_graph/ # Entity-Beziehungen
        ├── llm_provider.py  # Ollama + Cloud Fallback
        ├── circuit_breaker.py
        ├── event_bus.py     # Zentraler Pub/Sub
        └── tests/           # 200+ Test-Dateien
```

---

## Hinweise fuer KI-Assistenten

- Flask-Blueprints mit relativen Prefixes werden in `api/v1/blueprint.py` registriert
- Standalone Blueprints mit `/api/v1/...` Prefix werden in `core_setup.register_blueprints()` registriert
- Neue Services muessen in `init_services()` initialisiert und im services-Dict zurueckgegeben werden
- Neue API-Endpoints brauchen `@require_token` Decorator (oder `@optional_token`)
- Port ist immer 8909 (Umgebungsvariable PORT)
- Persistenz unter `/data/` (HA Add-on Mount); Ollama-Modelle unter `/share/pilotsuite/ollama/models` (getrennt fuer Backup-Groesse)
- Default LLM: `qwen3:0.6b` (lightweight), optionales Qualitaetsmodell: `qwen3:4b`
- Interner Ollama-Port: 11435 (nicht 11434, um Konflikte mit externem Ollama zu vermeiden)
- Tests mit pytest, PYTHONPATH muss auf `copilot_core/rootfs/usr/src/app` zeigen
- Dokumentation in Deutsch bevorzugt

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
| `copilot_core/rootfs/usr/src/app/main.py` | Waitress Entry Point |
| `copilot_core/rootfs/usr/src/app/copilot_core/app.py` | Flask App Factory |
| `copilot_core/rootfs/usr/src/app/copilot_core/core_setup.py` | Service-Init + Blueprint-Registration |
| `copilot_core/rootfs/usr/src/app/copilot_core/api/v1/blueprint.py` | Blueprint-Registry (Pfad A) |
| `copilot_core/rootfs/usr/src/app/copilot_core/api/security.py` | Token-Validierung |
| `copilot_core/rootfs/usr/src/app/copilot_core/event_bus.py` | Zentraler Pub/Sub |
| `copilot_core/rootfs/usr/src/app/copilot_core/llm_provider.py` | Ollama + Cloud Fallback |
| `copilot_core/rootfs/usr/src/app/copilot_core/circuit_breaker.py` | Resilience Pattern |
| `copilot_core/config.yaml` | HA Add-on Manifest (Version, Config-Schema) |
