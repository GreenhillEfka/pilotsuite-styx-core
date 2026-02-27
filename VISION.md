# PilotSuite Styx - Vision (2026-02-27)

This document is the **definitive vision baseline** for the dual-repo system:
- Core add-on repo: `pilotsuite-styx-core`
- HACS integration repo: `pilotsuite-styx-ha`

Version baseline:
- Core add-on: `10.4.0`
- HA integration: `10.4.0`
- Core API port: `8909`

---

## Mission

Build a **local-first AI co-pilot for Home Assistant** that learns household patterns, explains recommendations, and never bypasses user governance.

PilotSuite Styx ist kein Automatisierungs-Tool -- es ist ein intelligenter Begleiter, der das Zuhause versteht, Vorschlaege macht und dabei die Entscheidungshoheit immer beim Menschen belaesst. Jede Empfehlung ist nachvollziehbar, jede Aktion wird erst nach Freigabe ausgefuehrt.

---

## Herkunft (v0.1 → v10.4.0)

Die Entwicklung von PilotSuite Styx ist eine mehrstufige Reise von einem Prototyp zu einem produktionsreifen, KI-gestuetzten Smart-Home-System.

### Phase 1: Foundation (v0.1 – v0.8)
Grundstein des Systems mit Flask als Web-Framework, dem Brain Graph als zentralem Zustandsmodell, dem Habitus-Miner fuer Pattern-Discovery und einer Event Pipeline fuer die Kommunikation mit Home Assistant. Erste Neuronen-Prototypen fuer kontextuelle Bewertung.

### Phase 2: Stabilization (v1.0 – v2.0)
Produktionshaertung durch Circuit Breakers (HA Supervisor, Ollama), SQLite WAL-Mode fuer threadsichere Persistenz, Token-basierte Authentifizierung und strukturierte Fehlerbehandlung. Erster stabiler Dauerbetrieb im Heimnetzwerk.

### Phase 3: Feature Expansion (v3.0 – v3.9)
Massive Erweiterung auf 32+ Module. Einfuehrung des Neuronen-Systems (12+ Bewertungs-Neuronen), Mood Engine fuer multidimensionale Stimmungserkennung, Media Zones fuer Sonos/Apple TV/Smart TV, Energy Monitoring und Weather Context. Candidate-Management mit State Machine und Governance-Workflow.

### Phase 4: Bugfixes + Production Release (v3.8 – v3.9)
Intensive Stabilisierungsphase mit Fokus auf HACS-Validierung und hassfest-Kompatibilitaet. Bereinigung der manifest.json, strings.json-Normalisierung, CI/CD-Pipeline-Optimierung. Erster oeffentlicher Release ueber HACS.

### Phase 5: Cross-Home Sharing & Federated Learning (v5.0 – v7.x)
Einfuehrung von Federated Learning fuer anonymisiertes Cross-Home Pattern Sharing. Aufbau von 31+ API-Endpoints fuer den Core. RAG-Pipeline mit VectorStore und EmbeddingEngine fuer semantisches Wissensmanagement. Conversation Memory und Telegram-Bot-Integration.

### Phase 6: Conversation, RAG & System Overview (v8.x)
Styx Conversation Agent mit Brain Graph Context. RAG-Integration fuer Haushaltswissen. HomeKit Bridge, Frigate Bridge und UniFi Module fuer breitere Geraete-Abdeckung. System Overview Dashboard mit Health-Monitoring und Performance-Metriken.

### Phase 7: Architecture Overhaul (v9.0 – v9.2)
Tiefgreifende Architektur-Ueberarbeitung: Einfuehrung des EventBus-Systems, Tags v2 mit hierarchischer Struktur, 4-Tier-Modul-Architektur (Core, Context, Intelligence, Dashboard), NeuronTagResolver mit 4-Phasen Multi-Layer Pipeline. NeuronManager mit context→state→mood Pipeline.

### Phase 8: Consolidation (v10.0 – v10.4)
Konsolidierungsphase mit Zone Automation (ML-basierter Entity Classifier), Mood Engine v3.0 (6 diskrete Zustaende + 5 kontinuierliche Dimensionen + Entity Dependencies), Auto-Setup-Flow aus HA Areas, und ML Entity Classifier mit 4-Signal-Pipeline. Unified Sidebar Panel und 17 Hub Engines mit granularer Fehler-Isolation.

---

## Aktueller Stand (v10.4.0)

### Core Add-on (`pilotsuite-styx-core`)
| Metrik | Wert |
|--------|------|
| Tests | 586+ passed |
| Python-Dateien | 1100+ |
| API Endpoints | 55+ (45+ Flask Blueprints) |
| Services | 22+ via `init_services()`, alle mit Error Boundary |
| Hub Engines | 17 mit granularer Fehler-Isolation |
| Neuronen | 12+ Bewertungs-Neuronen |
| Persistenz | SQLite WAL-Mode, JSON Snapshots, VectorStore |

### HA Integration (`pilotsuite-styx-ha`)
| Metrik | Wert |
|--------|------|
| Tests | 579+ passed |
| Python-Dateien | 325+ |
| Module | 36 aktiv in 4 Tiers |
| Entities | 115+ (94+ Sensoren, 22+ Buttons/Numbers/Selects) |
| Dashboard Cards | 22+ |
| Options-Flow Steps | 29/29 mit data_description |
| Neuronen-Sensoren | 14 Kontext-Neuronen + NeuronLayerSensor |

### Beide Repos
- **Synchronisierte Versionierung:** Core und HA immer auf gleichem Major/Minor Stand
- **15-Minuten Production Guard:** Beide Repos mit `production-guard` Workflow alle 15 Minuten
- **HACS-validiert:** hassfest-kompatibel, CI/CD-abgesichert, Manifest-konform
- **Zero-Config-faehig:** Auto-Setup, Auto-Discovery, DEFAULTS_MAP + ensure_defaults()

---

## Non-negotiable principles
- **Local-first:** no cloud dependency for core operation.
- **Privacy-first:** redaction, bounded storage, explicit retention.
- **Governance-first:** recommendation before action, user remains decider.
- **Safety defaults:** fail safe under uncertainty, degraded mode over crash.
- **Explainability:** every recommendation has traceable evidence.
- **Deterministic reproducibility:** gleiche Eingaben fuehren zu gleichen Empfehlungen.
- **Graceful degradation:** jede Komponente kann unabhaengig ausfallen, ohne das Gesamtsystem zu stoppen.

---

## Zero-Config Vision

PilotSuite aims for **maximum user comfort** with zero configuration:
- Auto-discovery of Core add-on (localhost:8909)
- Auto-discovery of media entities (Sonos, Apple TV, Smart TV)
- Zone inference from entity names and HA areas
- Automatic Ollama Cloud fallback when local Ollama unavailable
- Smart weather/fallback without mandatory API keys
- Predictive maintenance with graceful degradation
- Auto-setup from HA areas on first run (zones + tags + entity roles)

### Auto-Discovery Features
| Feature | Implementation |
|---------|---------------|
| Core Endpoint | mDNS/UDP discovery + smart host candidates |
| Media Players | Sonos, Apple TV, Smart TV detection |
| Zone Inference | Entity name + HA Area parsing + ML Classifier |
| Model Fallback | Local Ollama → Ollama Cloud → graceful degradation |
| Weather | Open-Meteo (free) as default, personal-weather-station fallback |
| Entity Tagging | ML 4-Signal-Pipeline (domain, device_class, UOM, keywords) |
| Onboarding | Step-by-step notification wizard + auto-registered cards |

---

## Normative loop

`HA states -> Neuron context -> Mood/Intent weighting -> Pattern mining -> Candidate -> User decision -> Feedback`

Rules:
- No direct state-to-action shortcut in default mode.
- High-risk classes remain manual unless explicitly elevated.
- Feedback (accept/defer/dismiss) is part of the learning loop.
- Jeder Vorschlag traegt eine Konfidenz, eine Evidenzkette und eine Risikobewertung.
- Mood-Suppression verhindert irrelevante Vorschlaege im falschen Kontext.

---

## Dual-repo contract

- `pilotsuite-styx-core`: backend runtime, event ingest, graph, mining, candidate lifecycle, LLM/memory, health APIs, hub engines, mood engine, neuron pipeline, RAG/vector store.
- `pilotsuite-styx-ha`: Home Assistant-facing runtime, entities/cards/config-flow, events forwarder, repairs/governance UX, decision sync, sidebar dashboard, module lifecycle, sensor management.

Separation is intentional for HA ecosystem compatibility and release independence.

**Synchronisierungsvertrag:**
- Beide Repos teilen die gleiche VISION.md (dieses Dokument).
- Major/Minor Versionen werden synchron released.
- API-Aenderungen im Core erfordern immer eine korrespondierende Anpassung in HA.
- Der `production-guard` Workflow prueft beide Seiten des Contracts.

---

## Communication architecture

Forward path (HA → Core):
- HA events → N3 forwarder envelope → `POST /api/v1/events` → EventProcessor → BrainGraph → Habitus.

Return path (Core → HA):
- Candidate API → HA Candidate Poller → Repairs issue/workflow → user decision → `PUT /api/v1/candidates/:id`.

Realtime path:
- Core webhook push → HA coordinator merge → entity refresh.

EventBus (internal):
- Publish/Subscribe Pattern fuer interne Kommunikation zwischen Services.
- Entkopplung von Event-Erzeugern und -Konsumenten.
- Asynchrone Verarbeitung mit garantierter Delivery innerhalb des Prozesses.

---

## Self-Heal Capabilities

PilotSuite automatically recovers from common failure scenarios:
- **Ollama unavailable**: Falls back to Ollama Cloud automatically
- **Module load failure**: Skips failed module, logs error, continues with others
- **Entity unavailable**: Uses fallback/default values
- **Network issues**: Retry with exponential backoff
- **Database corruption**: WAL checkpoint recovery, automatic rebuild
- **Circuit Breaker open**: Automatic recovery nach Cooldown (HA Supervisor: 30s, Ollama: 60s)
- **Manual trigger**: `POST /api/v1/agent/self-heal` endpoint

---

## Module intent map

Core subsystems:
- **Ingest and event store:** reliable intake with idempotency and EventBus distribution.
- **Brain graph:** decayed relationship model, graph queries, SVG snapshots, vis.js export.
- **Habitus mining:** pattern extraction with quality thresholds, association rules, zone mining.
- **Candidate store:** governed lifecycle and feedback memory with state machine.
- **Mood engine v3.0:** 6 discrete states (Softmax + EMA), 5 continuous dimensions, entity dependencies.
- **Neuron pipeline:** 12+ scoring neurons, NeuronManager, context→state→mood pipeline.
- **Vector/memory/knowledge:** semantic recall, RAG pipeline, explainability context.
- **Hub engines:** 17 domain-specific orchestration surfaces with error isolation.

HA integration runtime modules (36 active, 4 tiers) are grouped as:
- **Core plumbing:** `legacy`, `events_forwarder`, `candidate_poller`, `history_backfill`, `dev_surface`.
- **Intelligence/context:** `habitus_miner`, `brain_graph_sync`, `mood`, `mood_context`, `ml_context`, `knowledge_graph_sync`.
- **Domain context:** `energy_context`, `weather_context`, `media_zones`, `network`, `camera_context`.
- **User/governance:** `character_module`, `entity_tags`, `quick_search`, `voice_context`, `ops_runbook`.
- **Home operations:** `home_alerts`, `waste_reminder`, `birthday_reminder`, `person_tracking`, `scene_module`, `calendar_module`, `homekit_bridge`, `frigate_bridge`, `unifi_module`, `performance_scaling`.

---

## Model Strategy

Default: `qwen3:0.6b` (fast, local, privacy-first)

Available alternatives:
- `qwen3:4b` - Better reasoning, still local
- `llama3.2:3b` - Alternative reasoning model
- `ollama.com/v1` - Cloud fallback (automatic)

Strategie:
- Kleinstes Modell als Default fuer minimalen Ressourcenverbrauch.
- Automatischer Fallback bei Nichtverfuegbarkeit (lokal → Cloud → graceful degradation).
- Modellwahl ueber Options Flow konfigurierbar, ohne Neustart.
- Conversation Agent nutzt das konfigurierte Modell fuer natuerlichsprachliche Interaktion.

---

## Configurability goals
- Zero-config first run works out of the box.
- Advanced mode exposes host/port/token, zones, tags, module toggles, thresholds.
- Runtime behavior is adjustable without manual file edits.
- Operational diagnostics are available from HA UI and API endpoints.
- 29/29 Options-Flow Steps mit vollstaendiger Konfigurierbarkeit.
- DEFAULTS_MAP + ensure_defaults() fuer konsistente Konfiguration bei ZeroConfig/QuickStart.

---

## UX vision (dashboard + controls)

### Design-Prinzipien

**Progressive Disclosure:**
Einfacher Default-Zustand fuer Einsteiger, tiefgreifende Diagnostik und Konfiguration on demand. Jede UI-Ebene enthuellt nur die naechste relevante Detailstufe -- nie alles auf einmal.

**Contextual Intelligence:**
Die Oberflaeche passt sich dem aktuellen Systemzustand an. Im Normalbetrieb zeigt das Dashboard kompakte Statusanzeigen. Bei Anomalien, offenen Candidates oder Health-Problemen werden relevante Details automatisch hervorgehoben.

**Ambient Awareness:**
Mood, Neuronen-Aktivitaet und Brain-Graph-Zustand sind immer sichtbar, aber nie aufdringlich. Der Nutzer entwickelt ueber die Zeit ein intuitives Gefuehl fuer den Systemzustand, ohne aktiv Dashboards pruefen zu muessen.

### Sidebar Dashboard (Primary Interface)

Das Sidebar Panel ist die zentrale Oberflaeche -- ein iframe zum Core Ingress Dashboard:
- **System Tab:** Health, Readiness, Confidence, Module Status, Version
- **Brain Tab:** Brain Graph Visualisierung (vis.js), Node/Edge Statistiken, Decay-Anzeige
- **Mood Tab:** Aktueller Mood-Zustand, Dimensionen (Comfort, Joy, Energy, Stress, Frugality), Verlaufsdiagramm
- **Neuronen Tab:** 14 Neuronen mit Aktivitaetslevel, NeuronLayer 3-Ring-Visualisierung
- **Habitus Tab:** Erkannte Muster, Confidence Scores, Zone-basierte Patterns
- **Core Tab:** API-Status, Endpoint-Uebersicht, Circuit Breaker Status
- **Media Tab:** Media Zones, aktive Player, Szenen-Zustand

### Brain Graph + Neuronenlayer 3-Ring-Visualisierung

```
           ┌─────────────────────────────────┐
           │        OUTER RING               │
           │   Domain Neurons (Energy,       │
           │   Weather, Media, Network)      │
           │  ┌───────────────────────────┐  │
           │  │     MIDDLE RING           │  │
           │  │  Context Neurons (Mood,   │  │
           │  │  Presence, Time, Season)  │  │
           │  │  ┌─────────────────────┐  │  │
           │  │  │    INNER RING       │  │  │
           │  │  │   Brain Graph       │  │  │
           │  │  │   (Nodes + Edges)   │  │  │
           │  │  └─────────────────────┘  │  │
           │  └───────────────────────────┘  │
           └─────────────────────────────────┘
```

Jeder Ring visualisiert eine Abstraktionsebene: der innere Ring zeigt den rohen Brain Graph, der mittlere Ring die kontextuellen Neuronen, der aeussere Ring die Domain-spezifischen Neuronen. Aktivitaet wird durch Farb-Intensitaet und Pulsieren dargestellt.

### Mobile-First Responsive Design
- Touch-optimierte Steuerungselemente fuer Candidate Accept/Defer/Dismiss
- Responsive Layouts: 1-Spalten-Layout auf Mobilgeraeten, Multi-Spalten auf Desktop
- Swipe-Gesten fuer Tab-Navigation im Sidebar Dashboard
- Kompakte Sensor-Karten mit expandierbaren Details
- Offline-faehige Lovelace Cards mit lokalem State-Cache

### Real-time WebSocket Updates
- Webhook Push vom Core → Coordinator → Entity Refresh in Echtzeit
- Kein Warten auf das naechste Polling-Intervall fuer kritische Updates
- Mood-Aenderungen, neue Candidates und Health-Events werden sofort reflektiert
- Visuelle Uebergangsanimationen bei Statuswechseln

### Zero-Config Onboarding Wizard
- Schritt 1: Core Add-on automatisch erkennen (mDNS/UDP/localhost)
- Schritt 2: HA Areas scannen → Zonen vorschlagen
- Schritt 3: Entities automatisch taggen (ML 4-Signal-Pipeline)
- Schritt 4: Dashboard-Karten automatisch registrieren
- Schritt 5: Erste Empfehlungen nach wenigen Stunden Lernphase
- Fortschrittsanzeige als Persistent Notification mit Deep Links

### Weitere UX-Elemente
- Lovelace card resources for mood/neurons/habitus surfaces.
- Repairs-based governance workflow for controlled application of candidates.
- Unified module-to-core communication path (active failover endpoint + consistent auth headers).
- Explainable recommendations: Evidenz und Risikostufe sichtbar vor jeder Aktion.
- Fast feedback loop: Nutzer-Entscheidungen werden sofort im UI-State reflektiert.

---

## Production readiness definition

A release is production-ready only if all are true:
- Critical path tests pass (forward path + return path + auth + status).
- Runtime fallback behavior works outside ideal HA container paths.
- CI fails on real regressions (no masked failures).
- Versioning/changelogs/docs are synchronized across both repos.
- HACS-Validierung und hassfest-Kompatibilitaet sind sichergestellt.
- Zero-Config-Pfad funktioniert ohne manuelle Eingriffe.

---

## Continuous hardening loop

Both repos run a scheduled `production-guard` workflow every 15 minutes to validate critical paths continuously.

Purpose:
- detect regressions early,
- keep dual-repo contract healthy,
- provide a stable base for iterative feature work,
- sicherstellen, dass Auto-Discovery und Self-Heal im Dauerbetrieb funktionieren.

---

## v10.4.0 — Consolidation & Auto-Setup

### Phase 1: Setup Flow
- Auto-setup from HA areas: zones + tags created automatically on first run
- Enhanced onboarding notification with step-by-step guide
- Normalized UI strings (English, domain-specific tags remain German)

### Phase 2: Dashboard Consolidation
- Unified sidebar panel (iframe to Core ingress)
- Auto-registered Lovelace card resources
- Legacy YAML dashboard generation (optional, disabled by default)

### Phase 3: Zones & Auto-Tagging
- ML-style entity classifier with 4-signal pipeline (domain, device_class, UOM, keywords)
- Bilingual keyword matching (DE + EN)
- Auto-suggest zones from HA areas with entity role assignment
- Bulk auto-tag by domain/device_class (14 tag categories)
- Manual override in options flow

### Phase 4: Core Backend
- New `/api/v1/auto-setup/suggest-zones` endpoint
- New `/api/v1/auto-setup/auto-tag` endpoint
- New `/api/v1/auto-setup/status` endpoint

---

## Projekt-Roadmap

### Phase A: v10.4.x Stabilisierung
**Ziel:** Produktionshaertung der v10.4.0-Features.

- **Auto-Setup E2E:** Kompletter Durchlauf von Area-Scan bis Entity-Tagging ohne manuelle Eingriffe validieren und haerten
- **Sidebar UX:** Dashboard-Tabs optimieren, Ladezeiten verbessern, Error States fuer offline-Core abfangen
- **Classifier Tuning:** ML Entity Classifier Precision/Recall verbessern, Edge Cases bei ungewoehnlichen Entity-Namen behandeln
- **HASSFest Fix:** Alle verbleibenden hassfest-Warnungen beheben, Manifest-Kompatibilitaet sicherstellen
- **Test-Coverage:** Luecken in Integration-Tests schliessen, insbesondere Auto-Setup und Options-Flow Pfade
- **Dokumentation:** HANDBOOK.md und API_REFERENCE.md auf v10.4.0-Stand bringen

### Phase B: v10.5.0 Enhanced Conversation & Voice
**Ziel:** PilotSuite wird zum natuerlichsprachlichen Smart-Home-Begleiter.

- **Multi-Turn Conversations:** Persistenter Konversationskontext ueber mehrere Nachrichten, Bezugnahme auf fruehere Empfehlungen und Entscheidungen
- **Voice-First Interaction:** Optimierung fuer Sprachassistenten (Home Assistant Voice, Assist Pipeline), kurze und praezise Antworten, Bestaetigung durch Sprache
- **Proactive Suggestions:** Kontextabhaengige, unaufgeforderte Hinweise basierend auf Mood, Tageszeit und erkannten Mustern -- immer als sanfte Benachrichtigung, nie als Unterbrechung
- **Brain Graph Context in Conversation:** Der Conversation Agent nutzt den vollstaendigen Brain Graph, Mood-Zustand und Habitus-Patterns fuer informierte Antworten
- **Conversation Memory:** Langzeit-Erinnerung an Nutzerpraeferenzen und vergangene Interaktionen ueber die RAG-Pipeline

### Phase C: v11.0.0 Advanced ML
**Ziel:** Intelligentere lokale KI-Modelle fuer praezisere Empfehlungen.

- **On-Device Inference:** Optimierte lokale Modelle fuer Pattern Recognition, Entity Classification und Anomaly Detection ohne Cloud-Abhaengigkeit
- **Time Series Forecasting:** Vorhersage von Energieverbrauch, Raumtemperatur und Anwesenheit basierend auf historischen Mustern und Wetterdaten
- **Energy Load Shifting:** Intelligente Empfehlungen zur Verlagerung von Energieverbrauch in guenstige Zeitfenster (PV-Ertrag, Niedrigtarif, Grid-Load)
- **Personalized Timing:** Lernen individueller Routinen und optimale Zeitpunkte fuer Vorschlaege (wann ist der Nutzer empfaenglich, wann nicht)
- **Anomaly Detection:** Automatische Erkennung ungewoehnlicher Muster (Energiespitzen, Sicherheitsrelevantes, Geraeteausfaelle) mit erklaerbaren Alerts

### Phase D: v11.x Skalierung
**Ziel:** PilotSuite fuer grosse Installationen und Mehrbenutzer-Haushalte.

- **Large-Home Support:** Optimierung fuer 500+ Entities, 20+ Zonen, schnellere Graph-Operationen und effizienteres Mining
- **Multi-User:** Individuelle Praeferenz-Profile pro Haushaltsmitglied, personalisierte Empfehlungen basierend auf Anwesenheit und gelernten Vorlieben
- **Policy Controls:** Feingranulare Governance-Regeln pro Risikoklasse, Raum, Tageszeit und Benutzer -- von "immer automatisch" bis "immer manuell"
- **Deeper RAG:** Erweiterte Wissensbasis mit Geraete-Dokumentation, Hersteller-Empfehlungen und Community-Patterns fuer kontextreichere Antworten
- **Performance Scaling:** Horizontale Skalierung der Hub Engines, Lazy Loading fuer selten genutzte Module, Memory-Footprint-Optimierung
