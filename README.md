# PilotSuite Core

Home Assistant Copilot mit RAG, Chat, und Zone Management.

## Installation

- **ML-basierte Vorhersagen** - Predictive Automation für dein Smart Home
- **Anomaly Detection** - Erkennt ungewöhnliches Verhalten automatisch
- **Smart Scheduling** - Optimiert Geräteeinsatz (Waschmaschine, Wallbox, etc.)
- **Echtzeit-Dashboard** - 10 Habituszonen mit Live-Daten
- **WebSocket Support** - Sofortige Updates ohne Polling
- **Styx Dashboard SPA** - 9-Tab Dashboard mit Zonen, Musikwolke, Vorschläge, Automation, KI/LLM, Module, Neuronen, Chat
- **Musikwolke (Sonos)** - Audio-follows-user mit Group/Ungroup, Volume-Slider, Play/Pause
- **Vorschlagssystem** - Muster-basierte Automationsvorschläge mit Konfidenz-Score und Accept/Reject/Snooze
- **Keyboard Shortcuts** - 1-8 für Tabs, Escape für Modal, r für Refresh
- **Zero-Config Example** - Vollständige Beispielkonfiguration für alle 10 Zonen mit echten HA-Entitäten

1. Repository hinzufügen: `https://github.com/GreenhillEfka/pilotsuite-styx-core`
2. Add-on Store → Refresh
3. PilotSuite Core installieren
4. Starten

### Ports
- 8909: Core API

## Endpoints

- `/api/styx/chat` - Chat mit RAG
- `/api/styx/health` - Health Check
- `/api/v1/habitus/*` - Habitus Zones
- `/api/v1/legacy/health` - Legacy (deprecated)

1. Repository klonen:
   ```bash
   git clone https://github.com/GreenhillEfka/pilotsuite-styx-ha.git
   cd pilotsuite-styx-ha
   ```

2. Nach `custom_components/pilotsuite/` kopieren:
   ```bash
   cp -r custom_components/pilotsuite /config/custom_components/
   ```

3. Home Assistant neu starten

4. Integration einrichten: Einstellungen → Geräte & Dienste → "+" → PilotSuite

## ⚙️ Konfiguration

### YAML (optional):

```yaml
pilotsuite:
  core_url: http://localhost:8000
  enable_ml: true
  enable_anomaly_detection: true
```

### UI:

1. Einstellungen → Geräte & Dienste → PilotSuite → Konfigurieren
2. Core Backend URL eingeben (Standard: `http://localhost:8000`)
3. ML-Features aktivieren/deaktivieren
4. Speichern

## 🔗 Links

- [GitHub Repository](https://github.com/GreenhillEfka/pilotsuite-styx-ha)
- [Core Backend](https://github.com/GreenhillEfka/pilotsuite-styx-core)
- [Dokumentation](https://github.com/GreenhillEfka/pilotsuite-styx-ha/wiki)
- [Issues melden](https://github.com/GreenhillEfka/pilotsuite-styx-ha/issues)

## 📝 Changelog

Siehe [Releases](https://github.com/GreenhillEfka/pilotsuite-styx-ha/releases) für alle Änderungen.

---

**Aktuelle Version:** v13.3.0
**Letztes Update:** 2026-03-04
**Home Assistant:** 2024.1.0+
