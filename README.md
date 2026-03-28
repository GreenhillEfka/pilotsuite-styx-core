# PilotSuite — Styx: Core Backend

[![Release](https://img.shields.io/github/v/release/GreenhillEfka/pilotsuite-styx-core)](https://github.com/GreenhillEfka/pilotsuite-styx-core/releases)

**PilotSuite Core** — Das Gehirn + Stimme der PilotSuite-Plattform. Home Assistant Add-on mit Brain Graph, RAG Chat, Mood Engine, Zone Automation und bundled Ollama LLM. Aktuelle Core/Add-on-Release-Linie: **v15.2.7**. **Dieses Repo ist nicht die HACS-Integration.**

---

## Was ist PilotSuite Core?

PilotSuite Core ist das **Backend Add-on** für Home Assistant mit:

- **Brain Graph Engine** — Neuronales Netzwerk mit 25+ Neuronen in 3 Schichten
- **RAG Chat** — Lokaler KI-Chat mit Ollama LLM (qwen3:0.6b)
- **Mood Engine v3.0** — 6 diskrete Zustände + 5 kontinuierliche Dimensionen
- **Zone Automation** — Präsenzabhängige Licht-/Musiksteuerung
- **Privacy-first** — Alles lokal, kein Cloud-API-Call

---

## Installation

### **Option 1: Home Assistant Add-on (Empfohlen)**

1. **Repository hinzufügen**
   - Home Assistant → Einstellungen → Add-ons → Add-on Store
   - ⋮ (Menü) → Repositories → URL hinzufügen:
     ```
     https://github.com/GreenhillEfka/pilotsuite-styx-core
     ```

2. **PilotSuite Core installieren**
   - Add-on Store → Refresh
   - PilotSuite Core installieren und starten

3. **Port**
   - Core API läuft auf Port **8909**
   - Ollama LLM intern auf Port **11435**

---

## Voraussetzungen

### **HA Integration (ERFORDERLICH)**

PilotSuite Core benötigt die **PilotSuite HACS Integration** (Sinne + Hände):

- **Repository:** https://github.com/GreenhillEfka/pilotsuite-styx-ha
- Siehe [pilotsuite-styx-ha README](https://github.com/GreenhillEfka/pilotsuite-styx-ha) für Installation

### **Abhängigkeiten**

- Home Assistant >= 2024.1.0
- Docker (wird durch HA Add-on System bereitgestellt)

---

## Features

### **Intelligence Engines**

| Engine | Beschreibung |
|--------|-------------|
| **Brain Graph** | SQLite WAL, exponential Decay, max 500 Nodes / 1500 Edges |
| **Habitus Miner** | Association Rule Mining, Wilson-Confidence, zone-basiert |
| **Mood Engine v3.0** | 6 diskrete Zustände (Softmax + EMA Hysterese) + 5 Dimensionen |
| **Neurons** | 25+ Neuronen in 3 Schichten (Context → State → Mood), 60s Intervall |
| **RAG Chat** | Hybrid Search mit RRF, Ollama LLM (qwen3:0.6b) |
| **Zone Automation** | Präsenz → Licht → Musik Controller pro Zone |

### **Hub Module (10+)**

- **Presence Intelligence** — Person-Tracking, Room-Transitions, Occupancy Heatmaps
- **Light Intelligence** — Sun-Tracking, Lux-Normalisierung, Mood Scenes
- **Zone Automation** — Entity-Management mit 11 Rollen, 13 Tags
- **Energy Advisor** — Verbrauchsanalyse und Beratung
- **Sonos Client** — Audio-follows-user via jishi API
- **Scene Intelligence** — Szenen-Verwaltung mit Presets
- **Anomaly Detection** — Erkennt ungewöhnliches Verhalten
- **Predictive Maintenance** — Vorhersagende Wartung
- **Open-Meteo Weather** — Lokale Wetterdaten
- **Wecker Module** — Alarm/Wecker-Steuerung

### **v15.0.0: Autonomie-Execution + Sammelentitaeten + Zone Health**

- **AutonomyExecutor** — Mood-getriebene Auto-Execution mit Double-Safety Governance
- **MoodActionMapper** — Stimmung-zu-Aktion-Tabellen (Licht-Szenen, Musik, Wetter)
- **HABridge** — Direkte HA Service Calls aus Core
- **DeviceClassAggregator** — Geraeteklassen-basierte Entitaets-Aggregation (11 Kategorien)
- **ZoneHealthChecker** — Per-Zone Gesundheitsmonitoring (Score 0-100)
- **BehavioralLog** — RAG-indexierte Autonomie-Aktionshistorie (BM25, 30 Tage Retention)

### **Styx Dashboard SPA**

9-Tab Dashboard mit:
- Overview, Zonen, Musikwolke, Vorschläge, Automation, KI/LLM, Module, Neuronen, Chat
- Keyboard Shortcuts (1-9), Auto-Refresh (30s)
- Brain-Visualization (Canvas mit Signal-Partikeln)
- Zone-Detail-Modal (Entities, Mood-Ringe, Szenen, Medien)

---

## API Endpoints

| Endpoint | Beschreibung |
|----------|-------------|
| `/api/styx/chat` | Chat mit RAG |
| `/api/styx/health` | Health Check |
| `/api/v1/habitus/*` | Habitus Zones |
| `/api/v1/brain/*` | Brain Graph |
| `/api/v1/mood/*` | Mood Engine |
| `/api/v1/zone-automation/*` | Zone Automation (16 Endpoints) |
| `/api/v1/sonos/*` | Sonos-Steuerung (20+ Endpoints) |
| `/api/v1/neurons/*` | Neuron Manager |
| `/health` | Legacy Health (deprecated) |

Vollständige API-Dokumentation: [docs/API_REFERENCE.md](docs/API_REFERENCE.md)

---


## State of the Art (2026-03-28)

- **Aktive Line:** 15.2.x
- **Aktueller Tag:** [v15.2.2](https://github.com/GreenhillEfka/pilotsuite-styx-core/releases/tag/v15.2.2)
- **Konsolidierungsstand für das nächste Paket:**
  - PR **#157** (Zone-Sync) ist technisch prinzipiell mergebar, aber CI stoppt aktuell an `ModuleNotFoundError: prometheus_client`.
  - PR **#156** ist CONFLICTING/legacy (`release-prep/v14.7.3`), nicht für den aktuellen Head geeignet.
- Zielzustand: Kern-Release stabilisieren, danach Pair-Release mit HA auf `update.ai_home_copilot_update`-fähig setzen.

## Architecture

```
PilotSuite Core Add-on (Port 8909)
├── Flask/Waitress REST-API
│   ├── 60+ Blueprints (22 nested + 40+ standalone)
│   ├── Token-Auth (X-Auth-Token / Bearer)
│   └── Circuit Breaker (HA Supervisor + Ollama)
├── Intelligence Engines
│   ├── Brain Graph (SQLite WAL)
│   ├── Habitus Miner
│   ├── Mood Engine v3.0
│   └── Neuron Pipeline (25+ Neuronen)
├── Hub Modules (10+)
│   ├── Zone Automation, Presence, Light
│   ├── Sonos, Energy, Scenes
│   └── Anomaly, Weather, Wecker
├── Ollama LLM (Port 11435, qwen3:0.6b)
└── Styx Dashboard SPA (9 Tabs)
        ↕
Home Assistant ← PilotSuite HACS Integration (copilot_ha)
```

---

## Links

| Resource | URL |
|----------|-----|
| **GitHub (Core)** | https://github.com/GreenhillEfka/pilotsuite-styx-core |
| **GitHub (HA)** | https://github.com/GreenhillEfka/pilotsuite-styx-ha |
| **Issues** | https://github.com/GreenhillEfka/pilotsuite-styx-core/issues |
| **API Docs** | [docs/API_REFERENCE.md](docs/API_REFERENCE.md) |

---

## Changelog

Siehe [CHANGELOG.md](CHANGELOG.md) für alle Änderungen.

---

## Credits

- **Developer:** GreenhillEfka
- **License:** MIT
- **Community:** Home Assistant Forum

---

**PilotSuite Core — Brain Graph, RAG Chat, Mood Engine & Zone Automation**
