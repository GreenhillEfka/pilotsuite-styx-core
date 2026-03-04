# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Projektueberblick

**PilotSuite Core Add-on** ist das Gehirn + Stimme der PilotSuite-Plattform. Es laeuft als Home Assistant Add-on (Docker Container) mit Flask/Waitress REST-API auf Port **8909** und bundled Ollama LLM auf Port **11435** (intern).

**Gegenstueck:** [pilotsuite-styx-ha](../pilotsuite-styx-ha) -- HACS Integration (Sensoren, Module, Dashboard)

- **Framework:** Flask 3.0.2 (Web) + Waitress 3.0.0 (WSGI)
- **Sprache:** Python 3.11+
- **Lizenz:** Privat, alle Rechte vorbehalten
- **Version:** Muss in `copilot_core/config.yaml`, `copilot_core/manifest.json` und `copilot_core/VERSION` uebereinstimmen
- **Releases:** Immer paired mit pilotsuite-styx-ha (gleiche Versionsnummer)

---

## Entwicklungskommandos

```bash
# Tests ausfuehren (alle, von repo root)
cd copilot_core/rootfs/usr/src/app && python -m pytest tests/ -v --tb=short -x

# Einzelnen Test ausfuehren
cd copilot_core/rootfs/usr/src/app && python -m pytest tests/test_zone_automation.py -v -x

# Einzelne Testklasse/-methode
cd copilot_core/rootfs/usr/src/app && python -m pytest tests/test_zone_automation.py::TestPresenceLight::test_presence_triggers_light_on_after_delay -v

# Tests mit Coverage
cd copilot_core/rootfs/usr/src/app && python -m pytest tests/ -v --tb=short --cov=copilot_core --cov-report=term-missing -x

# Alternativ von repo root mit PYTHONPATH
PYTHONPATH=copilot_core/rootfs/usr/src/app python -m pytest copilot_core/rootfs/usr/src/app/tests -v --tb=short -x

# Syntax-Check (alle Python-Dateien)
python -m py_compile $(find copilot_core/rootfs/usr/src/app -name '*.py')

# Security Scan
bandit -r copilot_core/rootfs/usr/src/app/copilot_core -ll --skip B101,B404,B603

# Smoke Test (Flask App erstellen)
PYTHONPATH=copilot_core/rootfs/usr/src/app python -c "from copilot_core.app import create_app; app = create_app(); print('ok')"
```

**Hinweis:** pytest.ini liegt in `copilot_core/rootfs/usr/src/app/pytest.ini`. Am einfachsten `cd` dorthin oder PYTHONPATH setzen. `asyncio_mode = auto` ist aktiviert. Das Plugin `pytest-randomly` ist deaktiviert (`-p no:randomly`).

---

## Architektur

### Zwei Entry Points (kritisches Design-Detail)

- **`main.py`** (Produktion): Laedt `/data/options.json`, nutzt `init_services()` + `register_blueprints()` aus `core_setup.py`. Registriert **60+ Blueprints** (22 nested + 40+ standalone).
- **`app.py`** (Tests): Flask App Factory mit `api_v1` Blueprint aus `api/v1/blueprint.py`. Registriert nur die **22 nested Blueprints** unter `/api/v1`.
- **Konsequenz:** Tests ueber `app.py` sehen nur Endpoints unter `/api/v1`, nicht die Standalone-Blueprints aus `core_setup.py`. Standalone-Endpoints muessen separat getestet werden (eigener Flask-App mit Blueprint-Registration).

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

### Hub Intelligence Engines (hub/)

Eigenstaendige Intelligence-Module mit eigenen Datenmodellen:

| Modul | Beschreibung |
|-------|-------------|
| `presence_intelligence.py` | Person-Tracking, Room-Transitions, Occupancy Heatmaps |
| `light_intelligence.py` | Sun-Tracking, Lux-Normalisierung, Cloud-Hysterese, Mood Scenes |
| `zone_automation.py` | **Praesenzabhaengige Licht-/Musiksteuerung**, Entity-Management, Tags |
| `energy_advisor.py` | Energieberatung und Verbrauchsanalyse |
| `media_follow.py` | Musikwolke Follow-Logik |
| `scene_intelligence.py` | Szenen-Verwaltung |
| `anomaly_detection.py` | Anomalieerkennung |
| `predictive_maintenance.py` | Vorhersagende Wartung |
| `habitus_zones.py` | Habituszonen-Verwaltung |

### Zone Automation Controller (hub/zone_automation.py)

Vereint Praesenz → Licht → Musik in einem Controller pro Zone:

- **ZoneLightConfig**: presence_delay_s, absence_delay_s, brightness_target_pct, dampening_band_pct, lux_outdoor_compensation, override enabled/disabled
- **ZoneMusicConfig**: presence_auto_play, follow_mode, presence_delay_s, absence_pause_s, default_volume_pct
- **Entity Management**: add_entity/remove_entity mit Auto-Rollenerkennung (11 Rollen) und Auto-Tagging (13 Tags)
- **Hysterese/Daempfung**: Dead-Band verhindert Flackern bei kurzen Helligkeitsschwankungen (Wolkendurchzug)
- API: 16 Endpoints unter `/api/v1/zone-automation/`

### Service-Dict Pattern (`core_setup.py`)

Zentraler Verdrahtungs-Hub — alle Services werden in einem Dict gesammelt und an Blueprints uebergeben:

```python
services = init_services(config=options)   # 24+ Services, jeder in try/except
register_blueprints(app, services)          # Blueprints auf Flask-App
```

**Error Boundary:** Jeder Service ist in try/except gewrappt. Fehlgeschlagene Services werden `None` gesetzt — Blueprint-Code muss damit umgehen.

### Blueprint-Registration

- **Nested** (`api/v1/blueprint.py`): Relative Prefixes unter `/api/v1` (22 Blueprints)
- **Standalone** (`core_setup.register_blueprints()`): Absolute Prefixes direkt auf App (40+ via data-driven `_SIMPLE_BLUEPRINTS` Loop + individuell)
- `conversation_bp` existiert an `/api/v1/chat/*` UND `/chat/*` (Legacy-Kompatibilitaet)
- **Neue Blueprints:** Standalone in `register_blueprints()` registrieren, es sei denn rein unter `/api/v1`

### Token-Validierung (`api/security.py`)

```python
from copilot_core.api.security import require_token

@bp.route("/api/v1/my-endpoint", methods=["POST"])
@require_token
def my_endpoint():
    ...
```

Alternativen: `@optional_token` (setzt `flask.g.token_valid`), `validate_token(request)` (manuell).

Token-Quellen (Prioritaet): `X-Auth-Token` Header > `Authorization: Bearer` > `COPILOT_AUTH_TOKEN` Env > `/data/options.json: auth_token`

### Styx Dashboard (templates/styx_dashboard.html)

Single-Page-App mit 9 Tabs: Overview, Zonen, Musikwolke, Vorschlaege, **Automation**, KI/LLM, Module, Neuronen, Chat. Keyboard Shortcuts 1-9. Auto-Refresh alle 30s. API calls via `fetchJSON()` / `postJSON()`.

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

152+ Testdateien in `copilot_core/rootfs/usr/src/app/tests/` mit 3720+ Tests. `conftest.py` stellt autouse-Fixtures bereit:

- **`reset_auth_token_cache`**: Setzt `_token_cache` in `security.py` vor/nach jedem Test zurueck (60s TTL wuerde sonst State-Leaking verursachen)
- **`reset_circuit_breakers`**: Setzt `ha_supervisor_breaker`, `ollama_breaker`, `cloud_api_breaker` zurueck (offene Breaker wuerden Folgetests beeinflussen)

**Standalone-Blueprint-Tests**: Erstellen eigene Flask-App + Blueprint-Registration statt `app.py`, z.B.:
```python
app = Flask(__name__)
app.register_blueprint(zone_automation_bp)
with app.test_client() as c:
    resp = c.get("/api/v1/zone-automation/dashboard")
```

---

## Hinweise fuer KI-Assistenten

- Neue Services: In `init_services()` initialisieren, in try/except wrappen, im services-Dict zurueckgeben
- Neue Hub-Module: In `hub/` anlegen, Blueprint in `api/v1/` anlegen, in `register_blueprints()` registrieren
- Port ist immer 8909 (`PORT` Env-Variable); Ollama intern 11435
- Persistenz: `/data/` (HA Add-on Mount), Ollama Models unter `/share/`
- `datetime.now(timezone.utc)` statt `datetime.utcnow()` (deprecated seit Python 3.12)
- Dokumentation in Deutsch bevorzugt
- Commit-Messages: `feat:`, `fix:`, `chore:`, `release:` Prefix

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
| `copilot_core/rootfs/usr/src/app/copilot_core/hub/zone_automation.py` | Zone Automation Controller (Licht/Musik/Entities) |
| `copilot_core/rootfs/usr/src/app/copilot_core/hub/light_intelligence.py` | Light Intelligence (Lux, Sun, Scenes) |
| `copilot_core/rootfs/usr/src/app/copilot_core/hub/presence_intelligence.py` | Presence Intelligence (Person-Tracking) |
| `copilot_core/rootfs/usr/src/app/copilot_core/neurons/manager.py` | NeuronManager Pipeline |
| `copilot_core/rootfs/usr/src/app/copilot_core/mood/engine.py` | Unified Mood Engine v3.0 |
| `copilot_core/rootfs/usr/src/app/copilot_core/brain_graph/store.py` | Brain Graph SQLite Store |
| `copilot_core/rootfs/usr/src/app/copilot_core/example_config.py` | Beispielkonfiguration (10 Zonen, ~80 Entities) |
| `copilot_core/rootfs/usr/src/app/copilot_core/templates/styx_dashboard.html` | Styx Dashboard SPA (9 Tabs) |
| `copilot_core/config.yaml` | HA Add-on Manifest (Optionen + Schema) |
| `copilot_core/Dockerfile` | Container-Build (Dependencies, Ollama) |
| `copilot_core/rootfs/usr/src/app/start_dual.sh` | Startup: Ollama + Flask |
| `docs/ARCHITECTURE_DUAL_REPO.md` | Dual-Repo Gesamtkonzept |
| `docs/API_REFERENCE.md` | API-Endpunkte Dokumentation |
