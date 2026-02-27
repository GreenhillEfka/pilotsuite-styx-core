# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Projektueberblick

**PilotSuite Core Add-on** ist das Backend fuer die PilotSuite-Plattform. Es laeuft als Home Assistant Add-on auf Port **8909** und stellt eine Flask/Waitress REST-API bereit.

**Gegenstueck:** [pilotsuite-styx-ha](../pilotsuite-styx-ha) -- HACS Integration (Sensoren, Module, Dashboard). Endpoint-/Payload-/Auth-Aenderungen muessen integrationskompatibel bleiben. Version muss in `copilot_core/config.yaml` und `copilot_core/rootfs/usr/src/app/VERSION` uebereinstimmen.

- **Framework:** Flask (Web), Waitress (WSGI Server)
- **Sprache:** Python 3.11+
- **Deployment:** Home Assistant Add-on (Docker Container)
- **Port:** 8909
- **Version:** 10.4.0

---

## Entwicklungskommandos

```bash
# Syntax-Check (alle ~400 Python-Dateien)
python -m py_compile $(find copilot_core/rootfs/usr/src/app -name '*.py')

# Tests ausfuehren
PYTHONPATH=copilot_core/rootfs/usr/src/app python -m pytest copilot_core/rootfs/usr/src/app/tests -v --tb=short -x

# Einzelnen Test ausfuehren
PYTHONPATH=copilot_core/rootfs/usr/src/app python -m pytest copilot_core/rootfs/usr/src/app/tests/test_mood_service.py -v -x

# Tests mit Coverage
PYTHONPATH=copilot_core/rootfs/usr/src/app python -m pytest copilot_core/rootfs/usr/src/app/tests -v --tb=short --cov=copilot_core/rootfs/usr/src/app/copilot_core --cov-report=term-missing -x

# Security Scan
bandit -r copilot_core/rootfs/usr/src/app/copilot_core -ll --skip B101,B404,B603

# Smoke Test (App erstellen)
PYTHONPATH=copilot_core/rootfs/usr/src/app python -c "from copilot_core.app import create_app; app = create_app(); print('ok')"
```

---

## Architektur

### Zwei Entry Points

- **`main.py`** (Produktion): Laedt `/data/options.json`, nutzt `init_services()` + `register_blueprints()` aus `core_setup.py`. Registriert 55+ Blueprints.
- **`app.py`** (Tests): Flask App Factory mit `api_v1` aus `api/v1/blueprint.py`. Registriert nur 22 Blueprints unter `/api/v1`. **Test- und Produktionspfad divergieren bei der Blueprint-Registrierung.**

### Neural Pipeline (Normative Kette)

```
HA Events --> Event Ingest --> Brain Graph --> Habitus Miner --> Candidates
                                  |               |
                            Neurons (25+)     Patterns
                                  |               |
                          Mood Engine v3.0   Vorschlaege --> HA Repairs UI
```

1. **Event Ingest**: Empfaengt N3-Envelopes von der HACS Integration (batched, dedupliziert, idempotent)
2. **Brain Graph**: SQLite-backed Store mit WAL-Mode, exponential Decay, Pruning (max 500 Nodes, 1500 Edges)
3. **Habitus Miner**: Association Rule Mining mit Wilson-Confidence, zone-basiert
4. **Mood Engine v3.0**: 6 diskrete Zustaende (Softmax + EMA Hysterese) + 5 kontinuierliche Dimensionen
5. **Candidates**: Governed Lifecycle (pending -> offered -> accepted/dismissed)
6. **Neurons**: 25+ Neuronen in 3 Schichten (Context -> State -> Mood), 60s Evaluationsintervall

### NeuronManager Callback-Pattern

NeuronManager nutzt **Multi-Listener-Pattern** fuer `on_mood_change` und `on_suggestion`:

```python
# core_setup.py registriert mehrere Callbacks:
neuron_manager.on_mood_change(webhook_push_callback)  # Listener 1
neuron_manager.on_mood_change(eventbus_callback)       # Listener 2 (nicht ueberschrieben)
```

### Service-Dict Pattern

`core_setup.py` ist der zentrale Verdrahtungs-Hub:

```python
services = init_services(config=options)   # 24+ Services, jeder in try/except
register_blueprints(app, services)          # 55+ Blueprints auf Flask-App
```

### Blueprint-Registration (zwei Pfade)

- **Nested Blueprints** in `api/v1/blueprint.py`: relative Prefixes unter `/api/v1` (22 Blueprints)
- **Standalone Blueprints** in `core_setup.register_blueprints()`: absolute Prefixes direkt auf App (35+ via data-driven `_SIMPLE_BLUEPRINTS` Loop + 18+ individuell)
- `conversation_bp` existiert absichtlich an beiden Pfaden (`/api/v1/chat/*` + `/chat/*`) fuer Legacy-Kompatibilitaet

### Token-Validierung

Alle API-Endpoints muessen authentifiziert sein:

```python
from ..security import validate_token

@bp.route("/api/v1/my-endpoint", methods=["POST"])
def my_endpoint():
    auth_error = validate_token(request)
    if auth_error:
        return auth_error
    # ... Logik
```

---

## Aktueller Stand (v10.4.0)

- **Tests:** 586+ passed
- **Python-Dateien:** 399 (alle kompilieren sauber)
- 24+ Services via init_services(), alle mit Error Boundary
- 55+ API Endpoints, 35+ Flask Blueprints
- Unified Mood Engine v3.0: 6 diskrete + 5 kontinuierliche Dimensionen + Entity Dependencies
- NeuronManager: 25+ Neuronen in 8 Dateien (context.py, state.py, mood.py, energy.py, presence.py, camera.py, unifi.py, mupl.py)
- Brain Graph: SQLite WAL Persistenz, Decay, Pruning, vis.js-Format Export
- Habitus Miner: Zone Mining, Wilson-Confidence, zeitbasierte/kontextuelle Muster
- Auto-Setup API: 3 Endpoints (suggest-zones, auto-tag, status)
- RAG Pipeline (VectorStore + EmbeddingEngine)
- Circuit Breaker (ha_supervisor: 5/30s, ollama: 3/60s)
- Ollama LLM (Default: qwen3:0.6b) + Cloud Fallback

---

## Hinweise fuer KI-Assistenten

- Neue Services in `init_services()` initialisieren und im services-Dict zurueckgeben
- Neue Blueprints: Standalone in `register_blueprints()` registrieren (nicht in `blueprint.py` nesten, es sei denn rein unter `/api/v1`)
- `validate_token(request)` auf ALLEN neuen Endpoints verwenden
- Port ist immer 8909 (Umgebungsvariable PORT)
- Persistenz unter `/data/` (HA Add-on Mount)
- `datetime.now(timezone.utc)` statt `datetime.utcnow()` (deprecated seit Python 3.12)
- Dokumentation in Deutsch bevorzugt
- Commit-Messages: `feat:`, `fix:`, `chore:` Prefix, paired Releases mit styx-ha

### Thread-Sicherheit

- Double-Checked Locking fuer Singletons (siehe `LLMProvider`)
- `services`-Dict ist read-only nach Initialisierung
- SQLite WAL-Modus mit `busy_timeout=5000`
- `_write_lock` fuer serialisierte Schreiboperationen in Brain Graph Store

### Projektprinzipien

| Prinzip | Bedeutung |
|---------|-----------|
| **Local-first** | Alles lokal, kein Cloud-API-Call erforderlich |
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
| `copilot_core/rootfs/usr/src/app/main.py` | Produktions-Entry-Point (912 Zeilen) |
| `copilot_core/rootfs/usr/src/app/copilot_core/app.py` | Test-Entry-Point / App Factory |
| `copilot_core/rootfs/usr/src/app/copilot_core/core_setup.py` | Service-Init + Blueprint-Registration (1187 Zeilen) |
| `copilot_core/rootfs/usr/src/app/copilot_core/api/v1/blueprint.py` | Nested Blueprint-Registry |
| `copilot_core/rootfs/usr/src/app/copilot_core/api/security.py` | Token-Validierung (`validate_token`) |
| `copilot_core/rootfs/usr/src/app/copilot_core/neurons/manager.py` | NeuronManager Pipeline (33.7KB) |
| `copilot_core/rootfs/usr/src/app/copilot_core/mood/engine.py` | Unified Mood Engine v3.0 |
| `copilot_core/rootfs/usr/src/app/copilot_core/brain_graph/store.py` | Brain Graph SQLite Store |
| `copilot_core/rootfs/usr/src/app/copilot_core/api/v1/auto_setup.py` | Auto-Setup API (suggest-zones, auto-tag) |
| `copilot_core/rootfs/usr/src/app/templates/dashboard.html` | Dashboard SPA (6184 Zeilen) |
| `copilot_core/config.yaml` | HA Add-on Manifest |
| `docs/ARCHITECTURE.md` | Vollstaendige Architektur-Dokumentation |
| `docs/API_REFERENCE.md` | API-Endpunkte Dokumentation |
