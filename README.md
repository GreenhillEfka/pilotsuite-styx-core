# PilotSuite Styx Core

**Version:** 1.0.0-rc2  
**Status:** ✅ Life-Long-Learning Dachsystem — End-to-End Verkabelt

---

## 🎯 VISION

**"Ein SmartHome, das CLEVERER ist als sein Nutzer"**

PilotSuite ist ein **Life-Long-Learning Dachsystem**, das:
- **Modular** lernt (jede Komponente verbessert sich)
- **Nutzer kennt** (über ALLE Schnittstellen hinweg)
- **Habitus speichert** (gelernte Patterns zentral — Unified Store)
- **Proaktiv** handelt (kommt Nutzer zuvor)
- **Zugänglich** ist (Chat/API für externe Dienste)
- **End-to-End** verkabelt ist (maximale Synergien)

📖 **Vollständige Vision:** [docs/VISION.md](docs/VISION.md)

---

## 🚀 WHAT'S NEW IN v15.3.0

### Unified Habitus Store

**Kombiniert RAG + Habitus + Anomaly in EINEM Store:**
- Patterns (A→B Regeln)
- Preferences (Nutzer-Vorlieben)
- Routines (wiederkehrende Aktivitäten)
- Events (HA state_changed)
- RAG-Docs (Dokumente, Wissen)
- AnomalyBaselines (Normalzustände)
- ZoneConfigs (pro Zone)
- ModuleDependencies (übergreifend)

### End-to-End Wiring

**Verkabelt ALLE Komponenten:**
- AutoDiscovery → UnifiedHabitusStore
- UnifiedHabitusStore → Neurons
- Neurons → Anomaly Detection
- Anomaly Detection → Chat API
- Chat API → User Feedback
- User Feedback → UnifiedHabitusStore
- Module Dependencies → Cross-Module Effects

### Zone-Scoped Data

**Saubere Trennung + Queries:**
- Alle Daten mit zone_id taggbar
- Zone-spezifische Konfiguration
- Zone-scoped Search
- Cross-Zone Contamination verhindert

### Module Dependencies

**Übergreifende Abhängigkeiten:**
- requires (Light benötigt Motion)
- enhances (Music verbessert Climate)
- conflicts (Camera konflikts mit Privacy)

---

## 📦 INSTALLATION

### Als Home Assistant Add-on

```yaml
# HA Add-on Repository hinzufügen
https://github.com/GreenhillEfka/pilotsuite-styx-core

# Installieren
Add-on: PilotSuite Core
Version: 15.3.0
Start: ✅
```

### Config

```yaml
ollama_url: http://127.0.0.1:11434
ha_url: http://homeassistant.local:8123
ha_token: YOUR_LONG_LIVED_ACCESS_TOKEN
searxng_url: http://localhost:8080  # Optional
```

---

## 🔗 API-ENDPOINTS

### Life-Long-Learning (Unified Store)

```
GET  /api/v1/habitus              — Overview + Stats
GET  /api/v1/habitus/patterns     — Patterns (filterbar)
POST /api/v1/habitus/feedback     — Feedback geben
GET  /api/v1/habitus/preferences  — Nutzer-Präferenzen
GET  /api/v1/habitus/routines     — Nutzer-Routinen
```

### Chat (Externer Zugang)

```
POST /api/v1/chat/sessions                 — Session erstellen
POST /api/v1/chat/sessions/<id>/messages   — Nachricht senden
POST /api/v1/chat/webhooks/telegram        — Telegram Webhook
POST /api/v1/chat/webhooks/rest            — REST Webhook
```

### Learning Visualization

```
GET  /api/v1/learning/overview    — Intelligence Score
GET  /api/v1/learning/patterns    — Patterns (visualisiert)
GET  /api/v1/learning/progress    — Fortschritt pro Zone/Modul
POST /api/v1/learning/correct     — Manuelle Korrektur
```

### Backend UI (10 Tabs)

```
GET  /api/v1/backend/dashboard    — System-Status
GET  /api/v1/backend/zones        — Habituszonen + Module
GET  /api/v1/backend/brain         — Neuronen + Graph
GET  /api/v1/backend/mood          — Mood + Dimensions
GET  /api/v1/backend/automation    — Vorschläge + Regeln
GET  /api/v1/backend/rag           — Vector-Store + SearXNG
GET  /api/v1/backend/media         — Sonos + Musikwolke
GET  /api/v1/backend/hardware      — Zigbee/Z-Wave/UniFi
GET  /api/v1/backend/system        — Health + Config + Models
```

---

## 🏗️ ARCHITEKTUR

```
┌─────────────────────────────────────────────────────────────┐
│                    PILOTSUITE CORE                           │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         UNIFIED HABITUS STORE                         │  │
│  │  (Patterns + Preferences + RAG + Anomaly + Zones)    │  │
│  └──────────────────────────────────────────────────────┘  │
│         ↓                   ↓                   ↓           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Habitus    │  │   Neurons    │  │    Chat      │      │
│  │   Service    │  │   Manager    │  │   Handler    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│         ↓                   ↓                   ↓           │
│  ┌────────────────────────────────────────────────────┐    │
│  │          END-TO-END WIRING                          │    │
│  │  (AutoDiscovery → Store → Neurons → Anomaly →     │    │
│  │   Chat → Feedback → Confidence → Dependencies)     │    │
│  └────────────────────────────────────────────────────┘    │
│         ↓                   ↓                   ↓           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Zones      │  │   Modules    │  │   Anomaly    │      │
│  │   Engine     │  │   Registry   │  │   Detector   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                            ↓
            ┌───────────────┴───────────────┐
            ↓                               ↓
    ┌──────────────┐              ┌──────────────┐
    │   HA Store   │              │   External   │
    │     V2       │              │   Services   │
    └──────────────┘              └──────────────┘
```

---

## 📊 STATISTICS (v15.3.0)

| Metric | Value |
|--------|-------|
| **Code Lines (neu)** | ~4.289 |
| **Code Lines (bewahrt)** | ~190.000 |
| **API Endpoints** | 50+ |
| **Modules** | 25+ |
| **Zone Types** | 10 |
| **Neuron Layers** | 3 (CONTEXT, STATE, MOOD) |
| **Mood Dimensions** | 5 |
| **Patterns** | Unbegrenzt (Unified Store) |
| **Module Dependencies** | Unbegrenzt |

---

## 🎯 INTELLIGENCE SCORE

```python
score = pattern_score + active_score + acceptance_score

pattern_score = min(total_patterns * 2, 40)     # Max 40
active_score = min(active_patterns * 5, 30)     # Max 30
acceptance_score = min(acceptance_rate * 30, 30) # Max 30

Level:
- 80-100: Expert
- 60-79:  Advanced
- 40-59:  Intermediate
- 20-39:  Beginner
- 0-19:   Novice
```

---

## 🔗 LINKS

| Resource | URL |
|----------|-----|
| **GitHub** | https://github.com/GreenhillEfka/pilotsuite-styx-core |
| **Releases** | https://github.com/GreenhillEfka/pilotsuite-styx-core/releases |
| **HA Integration** | https://github.com/GreenhillEfka/pilotsuite-styx-ha |
| **Vision** | [docs/VISION.md](docs/VISION.md) |
| **Changelog** | [CHANGELOG.md](CHANGELOG.md) |
| **Architektur** | [/config/clawd/ARCHITECTUR_REVISION.md](/config/clawd/ARCHITECTUR_REVISION.md) |

---

## 🎉 RELEASE v15.3.0

**Datum:** 2026-04-01  
**Tag:** v15.3.0  
**Status:** ✅ READY FOR PRODUCTION

**Key Features:**
- ✅ UnifiedHabitusStore (RAG + Habitus + Anomaly)
- ✅ EndToEndWiring (alle Komponenten verkabelt)
- ✅ Zone-Scoped Data (saubere Trennung)
- ✅ Module Dependencies (übergreifend)
- ✅ Cross-Type Search (BM25 über ALLES)
- ✅ HabitusService (High-Level API)
- ✅ AutoDiscovery (automatische Pattern-Erkennung)
- ✅ Chat API (Telegram, WhatsApp, REST)
- ✅ Learning Visualization (Intelligence Score)

---

**🚀 PILOTSUITE — DAS LEBENDIGE, LERNENDE, VERKABELTE DACHSYSTEM.**
