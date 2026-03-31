# PilotSuite Styx Core

**Version:** 15.3.0  
**Status:** ✅ Life-Long-Learning Dachsystem

---

## 🎯 VISION

**"Ein SmartHome, das CLEVERER ist als sein Nutzer"**

PilotSuite ist ein **Life-Long-Learning Dachsystem**, das:
- **Modular** lernt (jede Komponente verbessert sich)
- **Nutzer kennt** (über ALLE Schnittstellen hinweg)
- **Habitus speichert** (gelernte Patterns zentral)
- **Proaktiv** handelt (kommt Nutzer zuvor)
- **Zugänglich** ist (Chat/API für externe Dienste)

📖 **Vollständige Vision:** [docs/VISION.md](docs/VISION.md)

---

## 🚀 WHAT'S NEW IN v15.3.0

### Life-Long-Learning System

| Feature | API | Beschreibung |
|---------|-----|--------------|
| **Habitus Storage** | `/api/v1/habitus` | Zentrales Pattern-Lernen |
| **Chat API** | `/api/v1/chat` | Externer Zugang (Telegram, WhatsApp, REST) |
| **Learning Viz** | `/api/v1/learning` | Zeigt Nutzer was System lernt |
| **Backend UI** | `/api/v1/backend` | 10-Tabs Dashboard |
| **Neurons UI** | `/api/v1/neurons` | 3-Layer Visualisierung |
| **RAG UI** | `/api/v1/rag` | Vector-Store + SearXNG + Voice |
| **Media UI** | `/api/v1/media` | Sonos + Musikwolke |
| **Zone Sync** | `/api/v1/hub/zones` | Core ↔ HA Sync |

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

### Life-Long-Learning

```
GET  /api/v1/habitus              — Overview + Stats
GET  /api/v1/habitus/patterns     — Gelernte Patterns
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
GET  /api/v1/learning/overview    — Lern-Übersicht
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
```

---

## 🏗️ ARCHITEKTUR

```
┌─────────────────────────────────────────────────────────────┐
│                    PILOTSUITE CORE                           │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Habitus    │  │   Neurons    │  │    Chat      │      │
│  │   Storage    │  │   Manager    │  │   Handler    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│         ↓                   ↓                   ↓           │
│  ┌────────────────────────────────────────────────────┐    │
│  │              API Gateway (Flask)                    │    │
│  └────────────────────────────────────────────────────┘    │
│         ↓                   ↓                   ↓           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Zones      │  │   Modules    │  │     RAG      │      │
│  │   Engine     │  │   Registry   │  │   + SearXNG  │      │
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
| **Code Lines** | ~190.000 |
| **API Endpoints** | 50+ |
| **Modules** | 25+ |
| **Zone Types** | 10 |
| **Neuron Layers** | 3 (CONTEXT, STATE, MOOD) |
| **Mood Dimensions** | 5 |
| **Patterns** | Unbegrenzt (SQLite) |

---

## 🔗 LINKS

| Resource | URL |
|----------|-----|
| **GitHub** | https://github.com/GreenhillEfka/pilotsuite-styx-core |
| **Releases** | https://github.com/GreenhillEfka/pilotsuite-styx-core/releases |
| **HA Integration** | https://github.com/GreenhillEfka/pilotsuite-styx-ha |
| **Vision** | [docs/VISION.md](docs/VISION.md) |
| **Changelog** | [CHANGELOG.md](CHANGELOG.md) |

---

## 🎉 RELEASE v15.3.0

**Datum:** 2026-04-01  
**Tag:** v15.3.0  
**Status:** ✅ READY FOR PRODUCTION

**Key Features:**
- ✅ Life-Long-Learning System (Habitus Storage)
- ✅ Chat API (Telegram, WhatsApp, REST)
- ✅ Learning Visualization (für Nutzer-Vertrauen)
- ✅ Zone Sync (Core ↔ HA)
- ✅ Backend UI (10 Tabs)
- ✅ ~190.000 Zeilen Code bewahrt

---

**🚀 PILOTSUITE — DAS DACHSYSTEM.**
