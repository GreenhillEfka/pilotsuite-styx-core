# PilotSuite - Smart Home Intelligence

[![GitHub Release](https://img.shields.io/github/release/GreenhillEfka/pilotsuite-styx-ha.svg)](https://github.com/GreenhillEfka/pilotsuite-styx-ha/releases)
[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

## 🚀 Features

- **ML-basierte Vorhersagen** - Predictive Automation für dein Smart Home
- **Anomaly Detection** - Erkennt ungewöhnliches Verhalten automatisch
- **Smart Scheduling** - Optimiert Geräteeinsatz (Waschmaschine, Wallbox, etc.)
- **Echtzeit-Dashboard** - 10 Habituszonen mit Live-Daten
- **WebSocket Support** - Sofortige Updates ohne Polling
- **Styx Dashboard SPA** - 8-Tab Dashboard mit Zonen, Musikwolke, Vorschläge, KI/LLM, Module, Neuronen, Chat
- **Musikwolke (Sonos)** - Audio-follows-user mit Group/Ungroup, Volume-Slider, Play/Pause
- **Vorschlagssystem** - Muster-basierte Automationsvorschläge mit Konfidenz-Score und Accept/Reject/Snooze
- **Keyboard Shortcuts** - 1-8 für Tabs, Escape für Modal, r für Refresh
- **Zero-Config Example** - Vollständige Beispielkonfiguration für alle 10 Zonen mit echten HA-Entitäten

## 📦 Installation

### Über HACS (Empfohlen):

1. HACS öffnen
2. Rechts oben auf "⋮" → "Custom repositories"
3. Repository: `https://github.com/GreenhillEfka/pilotsuite-styx-ha`
4. Category: `Integration`
5. Auf "Add" klicken
6. PilotSuite in HACS finden und installieren
7. Home Assistant neu starten
8. Integration einrichten: Einstellungen → Geräte & Dienste → PilotSuite

### Manuell:

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

**Aktuelle Version:** v13.2.0
**Letztes Update:** 2026-03-04
**Home Assistant:** 2024.1.0+
