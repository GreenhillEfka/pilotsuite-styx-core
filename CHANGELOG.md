# Changelog

## [v15.3.1] - 2026-04-01

### 🛠 Runtime Wiring Repair

- `copilot_core/rootfs/usr/src/app/copilot_core/core_setup.py` repariert: optionale UI-Blueprints werden jetzt sauber und fehlertolerant geladen statt den Startup durch einen Syntax-/Import-Fehler zu brechen.
- Neue Contract-Absicherung für fehlende optionale UI-Module: Core-Startup bleibt stabil, auch wenn Backend-/Viz-Blueprints in einem Runtime-Paket nicht vorhanden sind.
- Versionsartefakte (`VERSION`, `copilot_core/VERSION`, `config.yaml`, `manifest.json`, Add-on-Config, Runtime-VERSION) auf `15.3.1` harmonisiert.

## [v15.3.0] - 2026-04-01

### 🎯 Life-Long-Learning System

**NEU: Zentrales Habitus-Storage**
- `copilot_core/habitus/habitus_storage.py` (832 Zeilen)
- Patterns (A→B Regeln mit Confidence)
- User Preferences (Nutzer-Vorlieben)
- User Routines (wiederkehrende Aktivitäten)
- User Feedback (Akzeptanzen, Ablehnungen)
- Context History (für Mining, rolling window 10000)

**NEU: HabitusService (High-Level API)**
- `copilot_core/habitus/habitus_service.py` (568 Zeilen)
- `service.observe()` — Auto Pattern Creation
- `service.get_proposals()` — Smart Vorschläge
- `service.process_feedback()` — Intelligent Feedback
- `service.learn_preference()` — Präferenzen lernen
- Wilson Score Confidence (robust bei wenig Daten)
- Fuzzy Pattern-Matching (80% Ähnlichkeit)

**NEU: AutoDiscovery (Automatisches Lernen)**
- `copilot_core/habitus/auto_discovery.py` (398 Zeilen)
- Background-Mining (alle 60s)
- Zeit-basierte Patterns ("Immer um 19:30")
- Kontext-basierte Patterns ("Wenn Präsenz + Abend")
- Sequenz-basierte Patterns ("Licht an → Musik an")
- Event-Buffer (max 1000 Events)

### 📡 APIs

**NEU: Habitus API**
- `GET /api/v1/habitus` — Overview + Stats
- `GET /api/v1/habitus/patterns` — Patterns (filterbar)
- `POST /api/v1/habitus/feedback` — Feedback geben
- `GET /api/v1/habitus/preferences` — Nutzer-Präferenzen
- `GET /api/v1/habitus/routines` — Nutzer-Routinen
- `GET /api/v1/habitus/context` — Context-History

**NEU: Chat API (Externer Zugang)**
- `POST /api/v1/chat/sessions` — Session erstellen
- `POST /api/v1/chat/sessions/<id>/messages` — Nachricht senden
- `POST /api/v1/chat/webhooks/telegram` — Telegram Webhook
- `POST /api/v1/chat/webhooks/rest` — REST Webhook
- Chat mit Habitus-Kontext (Preferences, Mood, Zones)

**NEU: Learning Visualization API**
- `GET /api/v1/learning/overview` — Lern-Übersicht + Intelligence Score
- `GET /api/v1/learning/patterns` — Patterns (visualisiert)
- `GET /api/v1/learning/progress` — Fortschritt pro Zone/Modul
- `POST /api/v1/learning/correct` — Manuelle Korrektur

### 📊 Backend UI

**10 Tabs mit echten Engines:**
- Dashboard — System-Status, Health, Quick Actions
- Zones — Habituszonen, Entity-Mapping, Module pro Zone
- Modules — Alle Module, Konfiguration, active/learning/off
- Brain — Neuronen (3 Layers), Graph, Pipeline
- Mood — 6 States, 5 Dimensions, History
- Automation — Vorschläge, Regeln, Accept/Reject
- RAG — Vector-Store, Embeddings, SearXNG, Voice
- Media — Sonos, Musikwolke, Favorites, Cameras
- Hardware — Zigbee, Z-Wave, UniFi
- System — Health, Config, Logs, Models, Docs

### 🔗 Zone Sync

**Core ↔ HA Bidirektional:**
- `copilot_core/hub/zone_sync.py` (401 Zeilen)
- `load_from_ha()` — HA → Core Sync
- `save_to_ha()` — Core → HA Sync
- `sync_module_state()` — Module State Sync
- `sync_entity_tags()` — Tag-basierte Entity-Zuordnung

### 🏷️ Tag System

**Automatische Entity→Zone Zuordnung:**
- 9 Domain-Kategorien (light, climate, motion, media, energy, humidity, camera, cover, lock)
- 10 Zone-Tags (zone_living, zone_bath, zone_kitchen, etc.)
- 3 Status-Tags (auto_assign, needs_review, manual_override)

### 📈 Intelligence Score

**Lern-Fortschritt messbar (0-100):**
- Pattern Score (Max 40)
- Active Automations Score (Max 30)
- User Acceptance Score (Max 30)
- Level: Novice → Beginner → Intermediate → Advanced → Expert

### 📖 Dokumentation

**NEU:**
- `docs/VISION.md` — Die Dachsystem-Vision (228 Zeilen)
- `README.md` — Neue README (150 Zeilen)

### 📊 Code-Statistik

| Metrik | Wert |
|--------|------|
| **Neuer Code** | ~3.214 Zeilen |
| **Bewahrter Code** | ~190.000 Zeilen |
| **API Endpoints** | 50+ |
| **Blueprints** | 10+ |
| **Dokumentation** | ~1.000 Zeilen |

### 🎯 Vision-Status

| Vision-Element | Status |
|----------------|--------|
| **Modular** | ✅ Jede Komponente lernt |
| **Nutzer-Kenntnis** | ✅ Preferences, Routines, Feedback |
| **Habitus (zentral)** | ✅ HabitusStorage (SQLite) |
| **Proaktiv** | ✅ Patterns → Proposals → Auto |
| **Zugänglich** | ✅ Chat API (Telegram, WhatsApp, REST) |
| **Ende-zu-Ende** | ✅ Neurons ↔ Habitus ↔ Chat ↔ Externe |
| **Learning-Viz** | ✅ /api/v1/learning für Nutzer |

---

## [v15.2.93] - 2026-03-31

### Added
- **Slice 67-73:** Zone-Aware Pipeline (Base)
- **Slice 75-79:** Module Extensions
- **Slice 80:** Climate/HVAC Module
- **Slice 81:** Humidity Module
- **Slice 82:** Energy Module
- **Slice 83:** Integration Tests

### Changed
- Alle Module folgen einheitlichem Contract
- Module Registry entdeckt und verwaltet alle Fachmodule zentral

### Fixed
- Module duplikate bereinigt
- Event Propagation zwischen Modulen konsolidiert

---

**🚀 v15.3.0 — DAS LEBENDIGE, LERNENDE DACHSYSTEM.**
