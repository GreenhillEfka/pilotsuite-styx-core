# PilotSuite Core — Home Assistant Integration

[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![Version](https://img.shields.io/badge/version-15.4.10-blue)](https://github.com/GreenhillEfka/pilotsuite-styx-ha/releases/tag/v15.4.10)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**AI-Powered Smart Home Automation Platform for Home Assistant**

---

## 📦 Installation

### Voraussetzung

- Home Assistant 2024.1.0 oder höher
- HACS installiert
- PilotSuite Core Add-on (läuft auf Port 8080)

### Schritt 1: HACS Custom Repository

1. Öffne **HACS** in Home Assistant
2. Klicke auf **⋮** (drei Punkte) → **Custom repositories**
3. Eintragen:
   - **Repository:** `https://github.com/GreenhillEfka/pilotsuite-styx-ha`
   - **Category:** `Integration`
4. Klicke **Hinzufügen**

### Schritt 2: Installation

1. Suche nach **"PilotSuite Core"** in HACS Integrations
2. Klicke **Download**
3. Wähle Version **15.4.10**
4. Klicke **Download**
5. **Home Assistant neustarten**

### Schritt 3: Integration konfigurieren

1. **Einstellungen** → **Geräte & Dienste**
2. **Integration hinzufügen**
3. Suche **"PilotSuite Core"**
4. Config Flow:
   - **API Endpoint:** `http://localhost:8909`
   - **Token:** (wird im Add-on generiert)
5. **Speichern**

---

## 🎯 Features

### Lovelace Cards (19)

| Card | Beschreibung |
|------|-------------|
| Brain Graph | Wissensgraph Visualisierung |
| Presence Status | Anwesenheits-Erkennung |
| Energy Dashboard | Energie-Optimierung |
| Habit Patterns | Gewohnheits-Muster |
| Suggestions | AI-Empfehlungen |
| Notifications | Benachrichtigungs-Center |
| Calendar | Kalender-Integration |
| Weather Automation | Wetter-Automatisierung |
| Analytics | Erweiterte Analysen |
| System Health | System-Überwachung |
| Scene Control | Szenen-Steuerung |
| Plugin Manager | Plugin-Verwaltung |
| Sync Status | Multi-Home Sync |
| Report Viewer | Berichte |
| Contract Status | Contract-Überwachung |
| ML Status | ML-Modell-Status |
| + 3 weitere | Siehe `lovelace/` |

### Entities

- **Sensoren:** Presence, Energy, Mood, Analytics
- **Switches:** Automation Toggles
- **Binary Sensoren:** Status Indicators
- **Notifications:** Pushover, Telegram

### API Client

- REST API Client zu Core Add-on
- WebSocket für Echtzeit-Updates
- GraphQL Support
- Rate Limiting

---

## 🔧 Configuration

### configuration.yaml (Optional)

```yaml
pilotsuite:
  api_endpoint: http://localhost:8080
  token: your-token-here
  polling_interval: 30
  debug: false
```

### Lovelace Dashboard

```yaml
type: custom:pilotsuite-brain-graph
title: Brain Graph

type: custom:pilotsuite-presence-status
title: Presence

type: custom:pilotsuite-energy-dashboard
title: Energy
```

---

## 📊 Architecture

```
┌─────────────────────────────────────┐
│   Home Assistant Integration        │
│   (This Repository)                 │
│                                     │
│   - Lovelace Cards                  │
│   - Sensors, Switches, Binary       │
│   - Config Flow                     │
│   - API Client → Core               │
└──────────────┬──────────────────────┘
               │ HTTP/REST (Port 8080)
               ▼
┌─────────────────────────────────────┐
│   Core Add-on                       │
│   (Separate Repository)             │
│                                     │
│   - REST API Server                 │
│   - ML Models                       │
│   - Database                        │
│   - Celery Workers                  │
└─────────────────────────────────────┘
```

---

## 📖 Documentation

| Doc | Link |
|-----|------|
| Installation | [INSTALL_HACS.md](docs/INSTALL_HACS.md) |
| Architecture | [ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| API Reference | [API_REFERENCE.md](docs/API_REFERENCE.md) |
| Quick Start | [QUICK_START_GUIDE.md](docs/QUICK_START_GUIDE.md) |

---

## 🐛 Troubleshooting

| Problem | Lösung |
|---------|--------|
| Integration nicht sichtbar | HA Neustart erzwingen |
| API Connection Failed | Core Add-on läuft? |
| Entities fehlen | Integration neu hinzufügen |
| Cards nicht geladen | Browser Cache leeren |

### Logs prüfen

**Einstellungen** → **System** → **Logs** → Filter: `pilotsuite`

---

## 🚀 Releases

| Version | Date | Notes |
|---------|------|-------|
| 15.4.10 | 2026-04-07 | Initial Release |

---

## 📝 License

MIT License — See [LICENSE](LICENSE)

---

## 🙏 Credits

- **Author:** @GreenhillEfka
- **Based on:** PilotSuite Styx Architecture
- **HACS:** [hacs.xyz](https://hacs.xyz)

---

**GitHub:** https://github.com/GreenhillEfka/pilotsuite-styx-ha  
**Issues:** https://github.com/GreenhillEfka/pilotsuite-styx-ha/issues
