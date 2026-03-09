# PilotSuite - Smart Home Intelligence

[![GitHub Release](https://img.shields.io/github/v/release/GreenhillEfka/pilotsuite-styx-core)](https://github.com/GreenhillEfka/pilotsuite-styx-core/releases)
[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

## 🚀 Features

- **ML-basierte Vorhersagen** - Predictive Automation für dein Smart Home
- **Anomaly Detection** - Erkennt ungewöhnliches Verhalten automatisch
- **Smart Scheduling** - Optimiert Geräteeinsatz (Waschmaschine, Wallbox, etc.)
- **Echtzeit-Dashboard** - 10 Habituszonen mit Live-Daten
- **WebSocket Support** - Sofortige Updates ohne Polling
- **Styx Dashboard SPA** - 9-Tab Dashboard mit Zonen, Musikwolke, Vorschläge, Automation, KI/LLM, Module, Neuronen, Chat
- **Musikwolke (Sonos)** - Audio-follows-user mit Group/Ungroup, Volume-Slider, Play/Pause
- **Vorschlagssystem** - Muster-basierte Automationsvorschläge mit Konfidenz-Score und Accept/Reject/Snooze
- **Szenen-Management** - 8 Presets + benutzerdefinierte Szenen pro Zone mit Save/Apply
- **Sonos Favorites** - Source-Auswahl pro Zone, Musikwolke-Integration
- **Brain Visualization** - 3-Layer Neural-Viz mit Signal-Partikeln und Firing-Animationen
- **HomeKit QR-Codes** - Automatische HomeKit-Bridge pro Habituszone mit QR-Code-Pairing
- **Keyboard Shortcuts** - 1-9 für Tabs, Escape für Modal, r für Refresh
- **Zero-Config Example** - Vollständige Beispielkonfiguration für alle 10 Zonen mit echten HA-Entitäten

## 📦 Installation

### Über HACS (Empfohlen):

1. HACS öffnen
2. Rechts oben auf "⋮" → "Custom repositories"
3. Repository: `https://github.com/GreenhillEfka/pilotsuite-styx-core`
4. Category: `Integration`
5. Auf "Add" klicken
6. PilotSuite in HACS finden und installieren
7. Home Assistant neu starten
8. Integration einrichten: Einstellungen → Geräte & Dienste → PilotSuite

### Manuell:

1. Repository klonen:
   ```bash
   git clone https://github.com/GreenhillEfka/pilotsuite-styx-core.git
   cd pilotsuite-styx-core
   ```

2. Das Core Add-on gemäß Repo-/Release-Dokumentation bauen bzw. in Home Assistant als Add-on-Repository einbinden.

3. Home Assistant neu starten

4. PilotSuite Core starten und Health auf `http://localhost:8909/health` prüfen

## ⚙️ Konfiguration

### YAML (optional):

```yaml
pilotsuite:
  core_url: http://localhost:8909
  enable_ml: true
  enable_anomaly_detection: true
```

### UI:

1. Einstellungen → Geräte & Dienste → PilotSuite → Konfigurieren
2. Core Backend URL eingeben (Standard: `http://localhost:8909`)
3. ML-Features aktivieren/deaktivieren
4. Speichern

## 🔗 Links

- [GitHub Repository](https://github.com/GreenhillEfka/pilotsuite-styx-core)
- [HA Integration](https://github.com/GreenhillEfka/pilotsuite-styx-ha)
- [Dokumentation](https://github.com/GreenhillEfka/pilotsuite-styx-core)
- [Issues melden](https://github.com/GreenhillEfka/pilotsuite-styx-core/issues)

## 📝 Changelog

Siehe [Releases](https://github.com/GreenhillEfka/pilotsuite-styx-core/releases) für alle Änderungen.

---

**Aktuelle Version:** v13.5.7
**Letztes Update:** 2026-03-09
**Home Assistant:** 2024.1.0+
