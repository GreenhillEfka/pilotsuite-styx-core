# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Projektueberblick

**PilotSuite Core Add-on** ist das Backend fuer die PilotSuite-Plattform. Es laeuft als Home Assistant Add-on auf Port **8909** und stellt eine Flask/Waitress REST-API bereit.

**Gegenstueck:** [pilotsuite-styx-ha](../pilotsuite-styx-ha) -- HACS Integration (Sensoren, Module, Dashboard)

- **Framework:** Flask (Web), Waitress (WSGI Server)
- **Sprache:** Python 3.11+
- **Deployment:** Home Assistant Add-on (Docker Container)
- **Port:** 8909
- **Lizenz:** Privat, alle Rechte vorbehalten

---

## Entwicklungskommandos

```bash
# Syntax-Check
python -m py_compile $(find copilot_core/rootfs/usr/src/app -name '*.py')

# Tests ausfuehren
PYTHONPATH=copilot_core/rootfs/usr/src/app python -m pytest copilot_core/rootfs/usr/src/app/tests -v --tb=short -x

# Tests mit Coverage
PYTHONPATH=copilot_core/rootfs/usr/src/app python -m pytest copilot_core/rootfs/usr/src/app/tests -v --tb=short --cov=copilot_core/rootfs/usr/src/app/copilot_core --cov-report=term-missing -x

# Security Scan
bandit -r copilot_core/rootfs/usr/src/app/copilot_core -ll --skip B101,B404,B603

# App erstellen (Smoke Test)
PYTHONPATH=copilot_core/rootfs/usr/src/app python -c "from copilot_core.app import create_app; app = create_app(); print('ok')"
```

---

## Architektur

### Neural Pipeline (Normative Kette)

```
HA Events --> Event Ingest --> Brain Graph --> Habitus Miner --> Candidates
                                  |               |
                              Neurons          Patterns
                                  |               |
                              Mood Engine    Vorschlaege --> HA Repairs UI
```

1. **Event Ingest**: Empfaengt Events von der HACS Integration (batched, dedupliziert)
2. **Brain Graph**: Zustandsgraph mit Nodes + Edges, exponential Decay, Snapshots
3. **Habitus Miner**: Pattern-Discovery mit Association Rules (Support, Confidence, Lift)
4. **Mood Engine**: Multidimensionale Stimmungsbewertung (Comfort, Joy, Frugality)
5. **Candidates**: Vorschlaege mit Governance-Workflow (pending -> offered -> accepted/dismissed)
6. **Neurons**: 12+ Bewertungs-Neuronen (Presence, Energy, Weather, Context, etc.)

### Brain Graph

- In-Memory Graph Store mit optionaler JSON-Persistenz
- Nodes: Entities, Zonen, Devices mit Score und Metadata
- Edges: Beziehungen mit Gewicht und Decay
- Max: 500 Nodes, 1500 Edges (konfigurierbar)
- Pruning, Patterns, SVG-Snapshots

### Habitus Mining

- Association Rule Mining aus Event-Streams
- Zone-basiertes Mining (Wohnbereich, Schlafbereich, etc.)
- Confidence-Scoring und Feedback-Loop
- Zeitbasierte, Trigger-basierte, sequenzielle und kontextuelle Muster

### Mood Engine

- 3D-Bewertung: Comfort, Joy, Frugality (je 0.0-1.0)
- Zone-spezifische Mood-Snapshots
- Exponential Smoothing fuer stabile Werte
- Suggestion-Suppression basierend auf Stimmung

---

## Konventionen

### Blueprint-Pattern (Flask)

Alle API-Endpunkte sind als Flask Blueprints organisiert:

```python
from flask import Blueprint
bp = Blueprint("modulname", __name__, url_prefix="/modulname")

@bp.get("/endpoint")
def get_endpoint():
    ...
```

Blueprints werden in `copilot_core/api/v1/blueprint.py` registriert (relative Prefixes unter `/api/v1`) oder direkt auf der App via `core_setup.register_blueprints()` (absolute Prefixes).

### Service-Dict Pattern

`init_services(config)` in `core_setup.py` initialisiert alle Backend-Services und gibt ein Dict zurueck:

```python
services = init_services(config=options)
# services["brain_graph_store"], services["event_store"], etc.
```

### init_services / register_blueprints

- `init_services(config)`: Erstellt und verdrahtet alle Service-Instanzen
- `register_blueprints(app, services)`: Registriert alle Flask Blueprints auf der App
- Beide Funktionen leben in `core_setup.py`

### Dateistruktur

```
copilot_core/
+-- Dockerfile               # Container-Build
+-- config.yaml              # HA Add-on Manifest
+-- rootfs/usr/src/app/
    +-- main.py              # Entry Point (Flask + Waitress)
    +-- copilot_core/
        +-- app.py           # Flask App Factory
        +-- core_setup.py    # init_services + register_blueprints
        +-- api/
        |   +-- v1/
        |   |   +-- blueprint.py   # Blueprint-Registry
        |   |   +-- candidates.py  # Candidates API
        |   |   +-- events.py      # Events API (wird importiert, nicht hier)
        |   |   +-- mood.py        # Mood API
        |   |   +-- graph.py       # Brain Graph API
        |   |   +-- habitus.py     # Habitus API
        |   |   +-- neurons.py     # Neurons API
        |   |   +-- search.py      # Search API
        |   |   +-- notifications.py
        |   |   +-- dashboard.py
        |   |   +-- weather.py
        |   |   +-- user_preferences.py
        |   |   +-- voice_context_bp.py
        |   |   +-- user_hints.py
        |   +-- security.py   # Token-Validierung
        |   +-- rate_limit.py  # Rate Limiting
        |   +-- performance.py # Performance Middleware
        +-- brain_graph/       # Brain Graph Store + Service
        +-- habitus_miner/     # Habitus Mining Engine
        +-- habitus/           # Habitus Service Layer
        +-- mood/              # Mood Engine + Scoring
        +-- neurons/           # 12+ Bewertungs-Neuronen
        +-- candidates/        # Candidate Store + API
        +-- ingest/            # Event Processing Pipeline
        +-- knowledge_graph/   # Knowledge Graph Store
        +-- collective_intelligence/  # Federated Learning
        +-- sharing/           # Cross-Home Sync
        +-- synapses/          # Synapse Manager
        +-- storage/           # Persistenz-Layer
        +-- tags/              # Tag Registry
        +-- system_health/     # System Health Checks
        +-- dev_surface/       # Debug/Diagnose
        +-- energy/            # Energy Neuron API
        +-- log_fixer_tx/      # Log Recovery
```

---

## Aktueller Stand

### Version v7.7.19

- **Tests:** 1962 passed, 1 skipped
- 28+ Backend-Module implementiert und registriert
- 40+ API Endpoints (30 Flask Blueprints)
- Security: Token-Validierung mit `hmac.compare_digest`
- Brain Graph mit Persistenz, Pruning, SVG-Snapshots
- Habitus Miner mit Zone Mining und Association Rules
- Mood Engine mit 3D-Scoring (Comfort/Joy/Frugality)
- Event Ingest mit Deduplication und Idempotency
- Candidate Management mit State Machine
- Knowledge Graph, Vector Store, Search
- Cross-Home Sync und Collective Intelligence
- System Health Checks (Zigbee, Z-Wave, Recorder, etc.)
- Ollama LLM Integration (Default: qwen3:0.6b, Optional: qwen3:4b)
- Dashboard Auth Bridge fuer Token-geschuetzte API
- Ollama Cloud Endpoint Hardening

---

## Hinweise fuer KI-Assistenten

- Flask-Blueprints mit relativen Prefixes werden in `api/v1/blueprint.py` registriert
- Standalone Blueprints mit `/api/v1/...` Prefix werden in `core_setup.register_blueprints()` registriert
- Neue Services muessen in `init_services()` initialisiert und im services-Dict zurueckgegeben werden
- Token-Validierung: `validate_token(request)` aus `api/security.py` verwenden
- Port ist immer 8909 (Umgebungsvariable PORT)
- Persistenz unter `/data/` (HA Add-on Mount)
- Tests mit pytest, Dateien in Repository-Root oder `/tests/`
- Dokumentation in Deutsch bevorzugt

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

### PR-Checkliste

- [ ] Changelog updated (if user-visible)
- [ ] Docs updated (if applicable)
- [ ] Privacy-first (no secrets, no personal defaults)
- [ ] Safe defaults (caps/limits; persistence off by default)
- [ ] Governance-first (no silent actions)

---

## Wichtige Dateien

| Datei | Beschreibung |
|-------|-------------|
| `copilot_core/rootfs/usr/src/app/main.py` | Entry Point |
| `copilot_core/rootfs/usr/src/app/copilot_core/app.py` | Flask App Factory |
| `copilot_core/rootfs/usr/src/app/copilot_core/core_setup.py` | Service-Initialisierung |
| `copilot_core/rootfs/usr/src/app/copilot_core/api/v1/blueprint.py` | Blueprint-Registry |
| `copilot_core/rootfs/usr/src/app/copilot_core/api/security.py` | Token-Validierung |
| `copilot_core/config.yaml` | HA Add-on Manifest |
| `docs/ARCHITECTURE.md` | Vollstaendige Architektur-Dokumentation |
| `docs/API_REFERENCE.md` | API-Endpunkte Dokumentation |