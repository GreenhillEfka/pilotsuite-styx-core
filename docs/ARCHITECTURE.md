# PilotSuite Core Add-on -- Architektur

> Technisches Architekturdokument fuer das PilotSuite Core Add-on (ehemals PilotSuite Core).
> Stand: v7.7.15 (2026-02-22)
> Hinweis: Dieses Dokument beschreibt die Architekturprinzipien. Fuer den verifizierten Produktionszustand siehe `PROJECT_STATUS.md` und `docs/MODULE_INVENTORY.md`.

---

## 1. Ueberblick

Das PilotSuite Core Add-on ist das zentrale Backend der PilotSuite-Plattform. Es laeuft als **Home Assistant Add-on** in einem Docker-Container und stellt eine REST-API auf **Port 8909** bereit.

| Komponente       | Technologie                                      |
|------------------|--------------------------------------------------|
| Web-Framework    | Flask (Python 3.11+)                             |
| WSGI-Server      | Waitress (Production-ready, multi-threaded)      |
| Deployment       | Docker-Container, registriert als HA Add-on      |
| Port             | 8909                                             |
| LLM-Runtime      | Ollama (im Dockerfile gebundelt)                 |
| Standard-Modell  | `qwen3:0.6b`                                     |
| Optional-Modell  | `qwen3:4b`                                       |
| Tool-Calling     | OpenAI-kompatibel ueber `/v1/chat/completions`  |
| Persistenz       | SQLite (WAL-Modus) unter `/data/`                |

Der Container startet Ollama als Hintergrundprozess und die Flask/Waitress-Anwendung als Hauptprozess. Alle Daten werden unter `/data/` persistiert -- dem Mount-Punkt, den Home Assistant fuer Add-on-Daten bereitstellt.

---

## 2. Service-Initialisierung

Die gesamte Service-Initialisierung ist in `copilot_core/core_setup.py` zentralisiert. Zwei Hauptfunktionen steuern den Startvorgang:

### `init_services(config)`

Erstellt alle Backend-Services und gibt ein `dict` zurueck:

```python
services = init_services(config=options)
# services["brain_graph_service"]   -> BrainGraphService
# services["mood_service"]          -> MoodService
# services["event_processor"]       -> EventProcessor
# services["neuron_manager"]        -> NeuronManager
# ...
```

Jeder Service-Block ist in `try/except` gewrappt, damit ein einzelner Fehler die restlichen Services nicht am Start hindert. Die Funktion gibt ein vollstaendiges `services`-Dict zurueck, auch wenn einzelne Eintraege `None` sind.

### `register_blueprints(app, services)`

Registriert alle Flask-Blueprints auf der App-Instanz und speichert das Services-Dict unter `app.config["COPILOT_SERVICES"]`, sodass jeder Request-Handler ueber den Flask Application Context darauf zugreifen kann.

```python
app = Flask(__name__)
services = init_services(config=options)
register_blueprints(app, services)
# -> app.config["COPILOT_SERVICES"] enthaelt alle Service-Instanzen
```

---

## 3. Blueprint-Architektur

Flask-Blueprints werden auf zwei verschiedene Arten registriert. Die Unterscheidung ist wichtig, um doppelte Pfad-Prefixes (`/api/v1/api/v1/...`) zu vermeiden.

### Muster 1: Verschachtelte Blueprints (api/v1/blueprint.py)

Sub-Blueprints mit **relativen** URL-Prefixes werden auf dem `api_v1`-Blueprint registriert. Dieser traegt den Prefix `/api/v1`, und die Sub-Blueprints haengen sich darunter ein:

```python
# api/v1/blueprint.py
api_v1 = Blueprint("api_v1", __name__, url_prefix="/api/v1")

api_v1.register_blueprint(events_bp)        # -> /api/v1/events/...
api_v1.register_blueprint(candidates_bp)    # -> /api/v1/candidates/...
api_v1.register_blueprint(mood_bp)          # -> /api/v1/mood/...
api_v1.register_blueprint(graph_bp)         # -> /api/v1/graph/...
api_v1.register_blueprint(habitus_bp)       # -> /api/v1/habitus/...
api_v1.register_blueprint(neurons_bp)       # -> /api/v1/neurons/...
api_v1.register_blueprint(vector_bp)        # -> /api/v1/vector/...
api_v1.register_blueprint(weather_bp)       # -> /api/v1/weather/...
api_v1.register_blueprint(search_bp)        # -> /api/v1/search/...
api_v1.register_blueprint(dashboard_bp)     # -> /api/v1/dashboard/...
api_v1.register_blueprint(knowledge_graph_bp)
api_v1.register_blueprint(sharing_bp)
api_v1.register_blueprint(federated_bp)
# ... und weitere
```

### Muster 2: Standalone-Blueprints (core_setup.register_blueprints)

Blueprints mit **absoluten** URL-Prefixes (die bereits `/api/v1/` oder andere Top-Level-Pfade enthalten) werden direkt auf der Flask-App registriert:

```python
# core_setup.py -> register_blueprints()
app.register_blueprint(brain_graph_bp)      # /api/v1/brain-graph/...
app.register_blueprint(candidates_bp)       # /api/v1/candidates/...
app.register_blueprint(mood_bp)             # /api/v1/mood/...
app.register_blueprint(energy_bp)           # /api/v1/energy/...
app.register_blueprint(system_health_bp)    # /api/v1/system-health/...
app.register_blueprint(unifi_bp)            # /api/v1/unifi/...
app.register_blueprint(conversation_bp)     # /chat/*
app.register_blueprint(openai_compat_bp)    # /v1/*
app.register_blueprint(tags_bp)             # /api/v1/tags/...
app.register_blueprint(telegram_bp)         # /api/v1/telegram/...
app.register_blueprint(mcp_bp)             # /mcp
# ... und weitere
```

Diese Blueprints duerfen **nicht** unter `api_v1` verschachtelt werden, da sie sonst doppelte Prefixes erhalten wuerden.

---

## 4. Neural Pipeline

Die Neural Pipeline ist die zentrale Verarbeitungskette, die aus Smart-Home-Events intelligente Vorschlaege ableitet:

```
HA Events --> Event Ingest --> Brain Graph --> Habitus Miner --> Candidates
                                  |               |
                              Neurons          Patterns
                                  |               |
                              Mood Engine    Vorschlaege --> HA Repairs UI
```

### Verarbeitungsschritte

1. **Event Ingest**: Die HACS-Integration sendet Events (batched, dedupliziert) an den `/api/v1/events/ingest`-Endpoint. Ein Post-Ingest-Callback leitet die Events an den EventProcessor weiter.

2. **Brain Graph**: Der EventProcessor aktualisiert den Zustandsgraphen. Entities, Zonen und Devices werden als Nodes abgebildet; Beziehungen (in_zone, controls, affects, correlates) als Edges. Exponentielles Decay sorgt dafuer, dass veraltete Informationen an Relevanz verlieren.

3. **Habitus Miner**: Aus dem Strom verarbeiteter Events werden Verhaltensregeln (A->B-Muster) extrahiert. Support, Confidence und Lift bestimmen die Guete der entdeckten Muster.

4. **Candidates**: Erkannte Muster und Vorschlaege durchlaufen eine State Machine (pending -> offered -> accepted/dismissed). Der Governance-Workflow stellt sicher, dass kein Vorschlag ohne Nutzerzustimmung umgesetzt wird (es sei denn, beide beteiligten Module sind auf "active" gesetzt).

### Querschnittliche Systeme

- **Neurons**: 12+ Bewertungsneuronen (Presence, TimeOfDay, LightLevel, Weather, EnergyLevel, StressIndex, ComfortIndex usw.) liefern Kontextwerte fuer die Pipeline.
- **Mood Engine**: Aggregiert Neuron-Outputs zu einer multidimensionalen Stimmungsbewertung (Comfort, Joy, Frugality), die die Relevanz von Vorschlaegen beeinflusst.

---

## 5. Services (22 Kern-Services)

Alle Services werden in `init_services()` initialisiert und im `services`-Dict zurueckgegeben:

| Nr. | Service                  | Modulpfad                                  | Beschreibung                                                              |
|-----|--------------------------|---------------------------------------------|---------------------------------------------------------------------------|
| 1   | `brain_graph_service`    | `brain_graph/service.py`                    | Zustandsgraph mit Nodes, Edges, Decay und Pruning                         |
| 2   | `graph_renderer`         | `brain_graph/render.py`                     | DOT/SVG-Rendering des Brain Graph fuer Visualisierung                     |
| 3   | `candidate_store`        | `candidates/store.py`                       | Speicher fuer Automations-Vorschlaege mit State Machine                   |
| 4   | `habitus_service`        | `habitus/service.py`                        | Service-Layer fuer Pattern-Discovery und Verhaltensanalyse                |
| 5   | `mood_service`           | `mood/service.py`                           | 3D-Stimmungsbewertung (Comfort/Joy/Frugality) pro Zone                   |
| 6   | `event_processor`        | `ingest/event_processor.py`                 | Event-Pipeline: EventStore -> BrainGraph mit Deduplication                |
| 7   | `tag_registry`           | `tags/__init__.py`                          | Tag-System v0.2 fuer Entity-Klassifikation und -Zuordnung                |
| 8   | `webhook_pusher`         | `webhook_pusher.py`                         | Nicht-blockierender Push-Client fuer HA-Webhook-Events                    |
| 9   | `household_profile`      | `household.py`                              | Haushaltsmitglieder-Profile mit Altersgruppen und Rollen                  |
| 10  | `neuron_manager`         | `neurons/manager.py`                        | Orchestriert alle Neuronen: Kontext -> Zustand -> Mood -> Vorschlaege     |
| 11  | `conversation_memory`    | `conversation_memory.py`                    | Lifelong-Learning-Speicher fuer Chat-Interaktionen und Praeferenzen       |
| 12  | `vector_store`           | `vector_store/store.py`                     | Bag-of-Words-Embedding-Store fuer RAG-Pipeline und Aehnlichkeitssuche     |
| 13  | `embedding_engine`       | `vector_store/embeddings.py`                | Embedding-Generierung fuer Entity-, Praeferenz- und Pattern-Vektoren      |
| 14  | `module_registry`        | `module_registry.py`                        | 3-Tier-Autonomie (active/learning/off) mit SQLite-Persistenz              |
| 15  | `automation_creator`     | `automation_creator.py`                     | Erstellt HA-Automations aus akzeptierten Vorschlaegen via Supervisor API  |
| 16  | `media_zone_manager`     | `media_zone_manager.py`                     | Zone-basierte Mediaplayer-Orchestrierung ("Musikwolke"-Feature)           |
| 17  | `proactive_engine`       | `proactive_engine.py`                       | Kontextbewusste Vorschlaege bei Zonenwechsel (nicht-intrusiv)             |
| 18  | `web_search_service`     | `web_search.py`                             | Websuche (DuckDuckGo HTML), News (RSS), Warnungen (NINA/DWD)             |
| 19  | `waste_service`          | `waste_service.py`                          | Abfallkalender-Status und proaktive TTS-Erinnerungen                      |
| 20  | `birthday_service`       | `waste_service.py` (BirthdayService)        | Geburtstagsverwaltung fuer Haushaltsmitglieder                            |
| 21  | `system_health_service`  | `system_health/service.py`                  | System Health Checks (Zigbee, Z-Wave, Recorder usw.)                      |
| 22  | `telegram_bot`           | `telegram/bot.py`                           | Telegram-Bot-Integration mit Server-seitigem Tool-Calling                 |

Zusaetzlich existieren Services, die direkt in `register_blueprints()` instanziiert werden:

| Service                   | Modulpfad                                   | Beschreibung                                                        |
|---------------------------|----------------------------------------------|---------------------------------------------------------------------|
| `ExplainabilityEngine`    | `explainability.py`                          | Natuerlichsprachige Erklaerungen fuer Vorschlaege via Brain Graph   |
| `ArrivalForecaster`       | `prediction/forecaster.py`                   | Ankunftszeitprognose fuer Haushaltsmitglieder                       |
| `EnergyOptimizer`         | `prediction/energy_optimizer.py`             | Energieverbrauchs-Optimierung auf Basis von PV/Preis-Prognosen     |
| `LLMProvider`             | `llm_provider.py`                            | Ollama-first LLM-Abstraktion mit Cloud-Fallback                    |
| `CircuitBreaker`          | `circuit_breaker.py`                         | Schutzschalter fuer externe Service-Aufrufe                         |

---

## 6. Brain Graph

Der Brain Graph ist ein gerichteter, gewichteter Zustandsgraph, der das aktuelle Wissen ueber das Smart Home abbildet.

### Datenmodell

- **Nodes** (`GraphNode`): Repraesentieren Entities, Zonen, Devices, Personen oder Konzepte.
  - Typen (`NodeKind`): `entity`, `zone`, `device`, `person`, `concept`, `module`, `event`
  - Attribute: `id`, `kind`, `label`, `score`, `domain`, `tags`, `meta`, `updated_at_ms`
  - PII-Redaktion: E-Mail-Adressen, IP-Adressen, Telefonnummern und URLs werden automatisch entfernt

- **Edges** (`GraphEdge`): Repraesentieren Beziehungen zwischen Nodes.
  - Typen (`EdgeType`): `in_zone`, `controls`, `affects`, `correlates`, `triggered_by`, `observed_with`, `mentions`
  - Attribute: `id`, `from_node`, `to_node`, `edge_type`, `weight`, `evidence`, `meta`, `updated_at_ms`

### Kapazitaetsgrenzen

| Parameter       | Standard  | Bereich     |
|-----------------|-----------|-------------|
| `max_nodes`     | 500       | 100 -- 5000 |
| `max_edges`     | 1500      | 100 -- 15000|
| `node_min_score`| 0.1       | 0.0 -- 1.0  |
| `edge_min_weight`| 0.1      | 0.0 -- 1.0  |

### Exponentielles Decay

Nodes und Edges verlieren ueber die Zeit an Relevanz:

```
effective_score = score * exp(-lambda * age_hours)
lambda = ln(2) / half_life_hours
```

- **Node Half-Life**: 24 Stunden (konfigurierbar, 0.1 -- 8760 h)
- **Edge Half-Life**: 12 Stunden (konfigurierbar, 0.1 -- 8760 h)

### Pruning

Wird periodisch ausgefuehrt und entfernt:
1. Edges mit `effective_weight < edge_min_weight`
2. Nodes mit `effective_score < node_min_score` und ohne verbundene Edges
3. Ueberzaehlige Nodes/Edges ueber den Kapazitaetsgrenzen (sortiert nach Score/Weight + Aktualitaet)

### Persistenz und Rendering

- **Speicher**: SQLite-Datenbank unter `/data/brain_graph.db` mit WAL-Modus
- **SVG-Snapshots**: Der `GraphRenderer` erstellt DOT-Graphen und rendert sie als SVG (max. 120 Nodes, 300 Edges pro Rendering)
- **Neighborhood-Queries**: Batched SQL-Queries fuer N-Hop-Nachbarschaften (vermeidet N+1-Probleme)

---

## 7. Habitus Mining

Das Habitus-Mining-System entdeckt Verhaltensregeln aus dem Smart-Home-Event-Strom mittels Association Rule Mining.

### Algorithmus

Der Mining-Algorithmus sucht nach A->B-Regeln: "Wenn Event A auftritt, folgt Event B innerhalb eines Zeitfensters."

1. **Preprocessing**: Events filtern (Domain/Entity-Inklusion/Exklusion) und deduplizieren (Cooldown pro Entity+Transition)
2. **Frequent Events**: Haeufige A- und B-Kandidaten identifizieren (`min_support_A`, `min_support_B`)
3. **Hit-Counting**: Fuer jedes (A, B, dt)-Tripel zaehlen, wie oft B innerhalb von `dt` Sekunden nach A auftritt (Binaersuche auf sortierten Zeitstempeln)
4. **Quality Metrics**: Confidence, Lift, Leverage und Conviction berechnen
5. **Filtering**: Regeln unter Mindestschwellen verwerfen

### Qualitaetsmetriken

| Metrik          | Formel                          | Bedeutung                                      |
|-----------------|----------------------------------|-------------------------------------------------|
| **Confidence**  | n(AB) / n(A)                     | Wie oft folgt B tatsaechlich auf A?             |
| **Confidence LB** | Wilson Score Lower Bound       | Konservative Schaetzung bei kleinen Stichproben |
| **Lift**        | Confidence / P(B)                | Wie stark ist die Korrelation ueber Zufall?     |
| **Leverage**    | Confidence - P(B)                | Absoluter Unterschied zur Baseline              |
| **Conviction**  | (1-P(B)) / (1-Confidence)       | Abhaengigkeitsgrad der Regel                    |

### Muster-Typen

- **Zeitbasierte Muster**: Konfigurierbare Zeitfenster (z.B. 60s, 300s, 900s)
- **Trigger-basierte Muster**: Entity A loest Entity B aus
- **Sequenzielle Muster**: A->B->C-Ketten ueber mehrere Zeitfenster
- **Kontextuelle Muster**: Stratifizierung nach Kontext-Features (Tageszeit, Zone, Wetter)

### Zone-basiertes Mining

Der Habitus Miner unterstuetzt Zone-spezifisches Mining. Events werden nach Habitus-Zonen (Wohnbereich, Schlafbereich, Kueche usw.) gruppiert, und Regeln werden pro Zone extrahiert. Das ermoeglicht raumspezifische Automatisierungen.

---

## 8. Mood Engine

Die Mood Engine berechnet eine multidimensionale Stimmungsbewertung pro Zone.

### 3D-Scoring

| Dimension      | Wertebereich | Beschreibung                                         |
|----------------|-------------|------------------------------------------------------|
| **Comfort**    | 0.0 -- 1.0  | Wie komfortabel fuehlt sich die Zone an (Temperatur, Licht, Aktivitaet) |
| **Joy**        | 0.0 -- 1.0  | Entertainment/Genuss-Level (Musik, TV, soziale Aktivitaet)             |
| **Frugality**  | 0.0 -- 1.0  | Nutzerpraeferenz fuer Ressourceneffizienz (Tageszeit, Verbrauchsmuster)|

### Zone-spezifische Snapshots

Jede Zone unterhalt einen eigenen `ZoneMoodSnapshot`, der unabhaengig aktualisiert wird:

```python
@dataclass
class ZoneMoodSnapshot:
    zone_id: str
    timestamp: float
    comfort: float       # 0--1
    frugality: float     # 0--1
    joy: float           # 0--1
    media_active: bool
    media_primary: str   # Aktueller Medientitel
    time_of_day: str     # "morning" | "afternoon" | "evening" | "night"
    occupancy_level: str # "empty" | "low" | "medium" | "high"
```

### Exponential Smoothing

Mood-Werte werden mit exponentiellem Smoothing (alpha = 0.3) aktualisiert, um abrupte Spruenge zu vermeiden:

```
neuer_wert = alter_wert * (1 - 0.3) + signal * 0.3
```

### Eingabequellen

- **MediaContext**: Musik-/TV-Aktivitaet beeinflusst Joy (Musik: +0.7, TV: +0.3)
- **Habitus-Kontext**: Tageszeit beeinflusst Comfort (Abend: 0.8, Nacht: 0.2); Frugality-Score wird direkt uebernommen

### Suggestion Suppression

Die Mood Engine beeinflusst die Relevanz von Vorschlaegen:
- `should_suppress_energy_saving(zone_id)`: Unterdrueckt Energiespar-Vorschlaege, wenn Joy > 0.6 oder Comfort > 0.7 bei Frugality < 0.5
- `get_suggestion_relevance_multiplier(zone_id, type)`: Liefert einen Multiplikator (0--1) basierend auf der aktuellen Stimmung

### SQLite-Persistenz

- Datenbank: `/data/mood_history.db` (WAL-Modus, busy_timeout=5000)
- Throttling: Maximal ein Schreibvorgang pro Zone pro 60 Sekunden
- Retention: 30 Tage Rolling History, max. 50.000 Eintraege
- Startup-Restore: Letzte bekannte Mood pro Zone wird aus der DB geladen

---

## 9. Persistenz

Alle persistenten Daten liegen unter `/data/` -- dem Mount-Punkt, den Home Assistant fuer Add-on-Daten bereitstellt.

### SQLite-Konfiguration

Alle SQLite-Datenbanken verwenden einheitliche Einstellungen:

```sql
PRAGMA journal_mode=WAL;      -- Write-Ahead Logging fuer bessere Concurrency
PRAGMA busy_timeout=5000;      -- 5 Sekunden Wartezeit bei gesperrter Datenbank
PRAGMA synchronous=NORMAL;     -- Kompromiss zwischen Performance und Sicherheit
```

### Datenbank-Dateien

| Datei                        | Service                 | Inhalt                                         |
|------------------------------|-------------------------|-------------------------------------------------|
| `/data/brain_graph.db`       | BrainGraphStore         | Nodes, Edges, Indizes fuer den Zustandsgraphen  |
| `/data/mood_history.db`      | MoodService             | Zone-Mood-Snapshots (30-Tage-Historie)           |
| `/data/conversation_memory.db` | ConversationMemory    | Chat-Verlauf und extrahierte Praeferenzen        |
| `/data/module_states.db`     | ModuleRegistry          | Modul-Zustaende (active/learning/off)            |
| `/data/media_zones.db`       | MediaZoneManager        | Mediaplayer-zu-Zone-Zuordnungen                  |
| `/data/predictions.db`       | ArrivalForecaster       | Ankunftsprognosen und historische Muster          |

---

## 10. Thread Safety

Flask/Waitress bedient Requests in mehreren Threads gleichzeitig. Die folgenden Muster stellen Thread-Sicherheit sicher:

### Double-Checked Locking fuer Singletons

```python
_instance = None
_lock = threading.Lock()

def get_instance():
    global _instance
    if _instance is not None:        # Schneller Pfad (kein Lock)
        return _instance
    with _lock:                       # Langsamer Pfad (mit Lock)
        if _instance is not None:     # Erneute Pruefung
            return _instance
        _instance = MyService()
        return _instance
```

Dieses Muster wird verwendet von: `LLMProvider`, `ModuleRegistry`, `NeuronManager`, `VectorStore`, `EmbeddingEngine`.

### Service-Dict im Flask Application Context

Das `services`-Dict wird einmalig beim Startup erstellt und danach nur gelesen. Es wird unter `app.config["COPILOT_SERVICES"]` gespeichert und ist fuer alle Request-Handler zugreifbar, ohne zusaetzliche Synchronisation (read-only nach Initialisierung).

### SQLite-Concurrency

SQLite im WAL-Modus erlaubt gleichzeitige Leser bei einem einzelnen Schreiber. `busy_timeout=5000` verhindert sofortige Fehler bei kurzzeitigen Sperren. Jeder Service oeffnet seine eigene Connection pro Operation (kein Connection-Pooling auf SQLite-Ebene).

---

## 11. Circuit Breaker

Der Circuit Breaker schuetzt vor kaskadierenden Fehlern, wenn externe Services nicht erreichbar sind.

### Zustandsmaschine

```
CLOSED (normal) --> OPEN (fehlerhaft) --> HALF_OPEN (testet Recovery)
       ^                                         |
       +---- Erfolg in HALF_OPEN ----------------+
```

### Konfigurierte Instanzen

| Name             | Failure Threshold | Recovery Timeout | Schuetzt                         |
|------------------|-------------------|------------------|----------------------------------|
| `ha_supervisor`  | 5 Fehler          | 30 Sekunden      | HA Supervisor REST API Aufrufe   |
| `ollama`         | 3 Fehler          | 60 Sekunden      | Ollama LLM API Aufrufe           |

### Verhalten

- **CLOSED**: Alle Aufrufe werden normal durchgeleitet. Bei Fehler wird der Zaehler inkrementiert.
- **OPEN**: Alle Aufrufe werden sofort mit `CircuitOpenError` abgelehnt (Fail Fast). Nach Ablauf des Recovery Timeout wechselt der Zustand zu HALF_OPEN.
- **HALF_OPEN**: Ein einzelner Testaufruf wird durchgelassen. Bei Erfolg -> CLOSED; bei Fehler -> zurueck zu OPEN.

---

## 12. LLM-Integration

### Ollama im Dockerfile

Ollama wird direkt im Docker-Container gebundelt und beim Container-Start als Hintergrundprozess gestartet. Standard ist `qwen3:0.6b`; fuer mehr Qualitaet auf staerkerer Hardware kann `qwen3:4b` verwendet werden.

### LLM Provider Chain

Der `LLMProvider` implementiert eine Fallback-Kette:

1. **Ollama (lokal, Standard)**: Privacy-first, laeuft auf `http://localhost:11434`
2. **Cloud API (Fallback)**: OpenClaw, OpenAI oder ein beliebiger OpenAI-kompatibler Endpoint

Konfiguration ueber die Add-on-Optionen (`conversation`-Sektion):
- `prefer_local: true` versucht zuerst Ollama, faellt bei Fehler auf Cloud zurueck
- `cloud_api_url`, `cloud_api_key`, `cloud_model` konfigurieren den Cloud-Fallback

### Zwei Conversation-Blueprints

| Blueprint          | Prefix    | Zweck                                                  |
|--------------------|-----------|--------------------------------------------------------|
| `conversation_bp`  | `/chat/*` | Legacy-API fuer den integrierten Chat                  |
| `openai_compat_bp` | `/v1/*`   | OpenAI-kompatible API (`/v1/chat/completions`, `/v1/models`) |

Die `/v1/*`-API ist kompatibel mit:
- Extended OpenAI Conversation (jekalmin/extended_openai_conversation)
- OpenAI Python SDK (`AsyncOpenAI`)
- Jeder OpenAI-kompatible Client (inkl. OpenClaw)

**Base URL fuer HA-Integration**: `http://<addon-host>:8909/v1`

### Tool-Calling

- **Client-seitiges Tool-Calling (`/v1/`)**: Der Client (z.B. Extended OpenAI Conversation) erhaelt Tool-Definitionen und fuehrt die Tool-Calls selbst aus. Das Add-on leitet Nachrichten und Tool-Responses durch.
- **Server-seitiges Tool-Calling (Telegram)**: Der Telegram-Bot fuehrt eine Server-seitige Tool-Execution-Loop aus. Die Funktion `process_with_tool_execution` ruft das LLM auf, fuehrt Tool-Calls (9 Tools: Licht, Klima, Szenen, Entitaeten usw.) via Supervisor API aus, und iteriert bis zur finalen Antwort.

### MCP-Server

Zusaetzlich stellt das Add-on einen MCP-Server (Model Context Protocol) unter `/mcp` bereit. Externe KI-Clients (OpenClaw, Claude Desktop) koennen darueberauf Brain Graph, Habitus, Mood, Neurons und Conversation Memory zugreifen.

---

## 13. Verzeichnisstruktur

```
addons/copilot_core/
+-- Dockerfile                          # Container-Build mit Ollama
+-- config.yaml                         # HA Add-on Manifest
+-- rootfs/usr/src/app/
    +-- main.py                         # Entry Point (Flask + Waitress)
    +-- copilot_core/
        +-- __init__.py
        +-- app.py                      # Flask App Factory
        +-- core_setup.py              # init_services() + register_blueprints()
        +-- circuit_breaker.py         # Circuit Breaker (CLOSED/OPEN/HALF_OPEN)
        +-- llm_provider.py            # Ollama + Cloud LLM Fallback-Kette
        +-- conversation_memory.py     # Lifelong Learning Store (SQLite)
        +-- explainability.py          # Natuerlichsprachige Erklaerungen
        +-- household.py               # Haushaltsmitglieder + Altersgruppen
        +-- media_zone_manager.py      # Zone-basierte Mediaplayer-Steuerung
        +-- module_registry.py         # 3-Tier-Autonomie (active/learning/off)
        +-- automation_creator.py      # Vorschlaege -> HA Automations
        +-- proactive_engine.py        # Kontextbewusste Vorschlaege
        +-- web_search.py             # DuckDuckGo + RSS + NINA/DWD
        +-- waste_service.py           # Abfallkalender + Geburtstage
        +-- webhook_pusher.py          # Nicht-blockierender Webhook-Push
        +-- performance.py             # Caching, GZIP, Connection Pooling
        +-- mcp_server.py             # MCP Server (JSON-RPC 2.0)
        +-- mcp_tools.py              # MCP Tool-Definitionen
        +-- user_profiles.py           # Benutzerpraeferenzen
        +-- ab_testing.py             # A/B-Testing-Framework
        |
        +-- api/
        |   +-- security.py            # Token-Validierung (Bearer Auth)
        |   +-- rate_limit.py          # Rate Limiting
        |   +-- performance.py         # Performance Middleware
        |   +-- validation.py          # Request-Validierung
        |   +-- v1/
        |       +-- blueprint.py       # Blueprint-Registry (verschachtelt)
        |       +-- conversation.py    # /chat/* + /v1/* (OpenAI-kompatibel)
        |       +-- events_ingest.py   # Event-Ingestion Endpoint
        |       +-- candidates.py      # Candidates API
        |       +-- mood.py            # Mood API
        |       +-- graph.py           # Brain Graph API
        |       +-- graph_ops.py       # Graph-Operationen
        |       +-- habitus.py         # Habitus API
        |       +-- neurons.py         # Neurons API
        |       +-- search.py          # Suche API
        |       +-- weather.py         # Wetter API
        |       +-- dashboard.py       # Dashboard API
        |       +-- vector.py          # Vector Store API
        |       +-- presence.py        # Praesenz-Tracking API
        |       +-- scenes.py          # Szenen-Verwaltung API
        |       +-- homekit.py         # HomeKit Bridge API
        |       +-- calendar.py        # Kalender API
        |       +-- shopping.py        # Einkaufsliste + Erinnerungen API
        |       +-- media_zones.py     # Mediazonen API
        |       +-- reminders.py       # Abfall + Geburtstage API
        |       +-- haushalt.py        # Haushalt-Dashboard API
        |       +-- entity_assignment.py # Entity-Zuordnung API
        |       +-- explain.py         # Explainability API
        |       +-- automation_api.py  # Automation-Erstellung API
        |       +-- module_control.py  # Modul-Steuerung API
        |       +-- user_preferences.py # Nutzerpraeferenzen API
        |       +-- voice_context_bp.py # Sprachkontext API
        |       +-- notifications.py   # Benachrichtigungen API
        |       +-- user_hints.py      # Nutzertipps API
        |       +-- swagger_ui.py      # Swagger UI
        |       +-- log_fixer_tx.py    # Log Recovery API
        |       +-- tag_system.py      # Tag System API
        |       +-- schemas.py         # API-Schemata
        |
        +-- brain_graph/               # Brain Graph Subsystem
        |   +-- model.py               # GraphNode, GraphEdge Datenmodelle
        |   +-- store.py               # SQLite-basierter Graph Store
        |   +-- service.py             # High-Level Graph-Operationen
        |   +-- render.py              # DOT/SVG Rendering
        |   +-- api.py                 # Blueprint fuer Graph-Endpoints
        |   +-- feeding.py             # Graph-Feeding aus Events
        |   +-- bridge.py              # Bruecke zu anderen Subsystemen
        |   +-- provider.py            # Graph-Datenbereitstellung
        |
        +-- habitus_miner/             # Habitus Mining Engine
        |   +-- model.py               # NormEvent, Rule, MiningConfig
        |   +-- mining.py              # A->B Rule Mining Algorithmus
        |   +-- zone_mining.py         # Zone-basiertes Mining
        |   +-- store.py               # Regel-Persistenz
        |   +-- service.py             # Mining Service Layer
        |
        +-- habitus/                   # Habitus Service Layer
        |   +-- service.py             # HabitusService (BrainGraph + Candidates)
        |   +-- api.py                 # Habitus API Blueprint
        |   +-- miner.py               # Mining-Orchestrierung
        |
        +-- mood/                      # Mood Engine
        |   +-- service.py             # MoodService (3D-Scoring, SQLite)
        |   +-- engine.py              # Mood-Berechnungslogik
        |   +-- scoring.py             # Scoring-Funktionen
        |   +-- actions.py             # Stimmungsbasierte Aktionen
        |   +-- orchestrator.py        # Mood-Orchestrierung
        |   +-- api.py                 # Mood API Blueprint
        |
        +-- neurons/                   # Neuronales Bewertungssystem
        |   +-- base.py                # BaseNeuron, NeuronConfig, NeuronState
        |   +-- manager.py             # NeuronManager (Pipeline-Orchestrierung)
        |   +-- context.py             # Kontext-Neuronen (Presence, Time, Light, Weather)
        |   +-- state.py               # Zustands-Neuronen (Energy, Stress, Comfort, ...)
        |   +-- mood.py                # Mood-Neuronen (Relax, Focus, Sleep, Alert, ...)
        |   +-- energy.py              # Energie-Neuronen (PV, Kosten, Grid)
        |   +-- unifi.py               # UniFi-Netzwerk-Neuron
        |   +-- presence.py            # Erweiterte Praesenz-Logik
        |   +-- weather.py             # Wetter-Neuron
        |   +-- camera.py              # Kamera-Neuron
        |
        +-- candidates/                # Candidate Management
        |   +-- store.py               # CandidateStore (State Machine)
        |   +-- api.py                 # Candidates API Blueprint
        |
        +-- ingest/                    # Event Ingestion Pipeline
        |   +-- event_processor.py     # EventStore -> BrainGraph Verarbeitung
        |   +-- event_store.py         # Event-Speicher
        |
        +-- knowledge_graph/           # Knowledge Graph
        |   +-- builder.py             # Graph-Aufbau
        |   +-- models.py              # Datenmodelle
        |   +-- api.py                 # API Blueprint
        |   +-- pattern_importer.py    # Pattern-Import
        |
        +-- vector_store/              # RAG Pipeline
        |   +-- embeddings.py          # Bag-of-Words Embedding Engine
        |   +-- store.py               # VectorStore (Aehnlichkeitssuche)
        |
        +-- collective_intelligence/   # Federated Learning (Phase 5)
        |   +-- federated_learner.py   # Foederiertes Lernen
        |   +-- knowledge_transfer.py  # Wissenstransfer
        |   +-- model_aggregator.py    # Modell-Aggregation
        |   +-- privacy_preserver.py   # Datenschutz-Praesrvierung
        |   +-- api.py                 # API Blueprint
        |   +-- service.py             # Service Layer
        |
        +-- sharing/                   # Cross-Home Sync
        |   +-- api.py                 # Sharing API Blueprint
        |
        +-- prediction/               # Vorhersagen
        |   +-- forecaster.py          # Ankunftsprognosen
        |   +-- energy_optimizer.py    # Energieoptimierung
        |   +-- api.py                 # Prediction API Blueprint
        |
        +-- system_health/            # System Health
        |   +-- service.py             # SystemHealthService
        |   +-- api.py                 # System Health API Blueprint
        |
        +-- telegram/                 # Telegram Integration
        |   +-- bot.py                 # TelegramBot (Polling + Tool-Loop)
        |   +-- api.py                 # Telegram API Blueprint
        |
        +-- unifi/                    # UniFi Netzwerk-Integration
        |   +-- service.py             # UniFiService
        |   +-- api.py                 # UniFi API Blueprint
        |
        +-- energy/                   # Energie-Integration
        |   +-- service.py             # EnergyService
        |   +-- api.py                 # Energy API Blueprint
        |
        +-- tags/                     # Tag System v0.2
        |   +-- __init__.py            # TagRegistry, create_tag_service
        |   +-- api.py                 # Tags API Blueprint
        |
        +-- tagging/                  # Entity-Tagging (Legacy)
        |   +-- registry.py            # Tag-Registry
        |   +-- assignments.py         # Tag-Zuordnungen
        |   +-- models.py              # Datenmodelle
        |   +-- zone_integration.py    # Zone-Integration
        |
        +-- dev_surface/              # Debug/Diagnose
        |   +-- service.py             # DevSurface Service
        |   +-- api.py                 # Debug API Blueprint
        |   +-- models.py              # Datenmodelle
        |
        +-- storage/                  # Persistenz-Layer
        |   +-- candidates.py          # Candidate-Persistenz
        |   +-- events.py              # Event-Persistenz
        |   +-- user_preferences.py    # Nutzerpraeferenzen-Persistenz
        |
        +-- synapses/                 # Synapse Manager
        |   +-- manager.py             # SynapseManager
        |   +-- models.py              # Datenmodelle
        |
        +-- log_fixer_tx/            # Transaktionslog + Recovery
            +-- transaction_log.py     # Transaktionslog
            +-- operations.py          # Log-Operationen
            +-- recovery.py            # Recovery-Logik
```

---

## Anhang: Konfigurationsparameter

Alle numerischen Konfigurationsparameter werden mit `_safe_int()` / `_safe_float()` validiert. Diese Hilfsfunktionen erzwingen Minimum- und Maximum-Grenzen und fallen bei ungueltigen Werten auf sichere Defaults zurueck:

```python
def _safe_int(value, default: int, minimum: int = 1, maximum: int = 100000) -> int:
    try:
        return max(minimum, min(maximum, int(value)))
    except (TypeError, ValueError):
        return default
```

Dies verhindert, dass ungueltige Add-on-Optionen (z.B. `max_nodes=0` oder `max_nodes=-1`) das System in einen inkonsistenten Zustand bringen.
