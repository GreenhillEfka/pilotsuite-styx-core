# Release v13.7.0 — Zone Dashboard v3, Smart Home Module, Musikwolke Bridge

**Datum:** 2026-03-12
**Branch:** main
**Tag:** `v13.7.0`
**HA hassfest:** compliant
**Paired Release:** Core v13.7.0 <-> HA v13.7.0

---

## Ueberblick

PilotSuite v13.7.0 ist ein Major-Feature-Release mit drei Schwerpunkten:

1. **Zone Dashboard v3** — 11 Hub-Engines integriert, voll angereichert mit Controls, Playlists, Notifications, Birthdays, Todos
2. **5 neue Smart Home Module** — Licht, Helligkeit, Heiz, Bewegung, Praesenz als eigenstaendige Hub-Module
3. **Musikwolke Bridge** — End-to-End Sonos-Integration mit Follow-Mode, Automation und 8 HA-Services

---

## Neue Features

### Zone Dashboard v3 (11 Hub-Engines)
- Zonenzentriertes Dashboard mit vollstaendiger Modulintegration
- Controls, Musik, Playlists, Notifications, Birthdays, Todos pro Zone
- Refactored fuer Effizienz und Failsafety

### 5 PilotSuite Smart Home Module
| Modul | Beschreibung |
|-------|-------------|
| `licht_module.py` | Lichtsteuerung mit Szenen und Dimming |
| `helligkeit_module.py` | Helligkeitssensor-Auswertung und Lux-Management |
| `heiz_module.py` | Heizungssteuerung mit Zieltemperatur und Zeitplaenen |
| `bewegung_module.py` | Bewegungsmelder-Aggregation und Raumaktivitaet |
| `praesenz_module.py` | Praesenz-Tracking und Aufenthaltsanalyse |

### Musikwolke Bridge + Sonos API
- `musikwolke_bridge.py`: Verbindet ZoneAutomationController mit SonosCloudClient
- Sonos jishi API Integration (Port 5005) mit REST Blueprint
- 8 neue REST-Endpoints unter `/api/v1/musikwolke/`
- Follow-Mode: Musik folgt dem Nutzer zwischen Raeumen
- Automation-Modus-System (off/learning/autonomy) pro Zone

### DynamicNeuronFactory
- Cross-module pattern-based Neuron-Erstellung
- Automatische Neuron-Generierung basierend auf Hub-Modulen

### Tag-System Erweiterung
- 13 neue Zone-Rollen-Tags (aicp.role.*)
- Bidirektionale Synchronisierung HA <-> Core
- Kanonische Tag-IDs mit Mapping

### Zone Automation
- Praesenzabhaengige Licht- und Musiksteuerung
- Entity-Management mit Auto-Rollenerkennung (11 Rollen)
- 16 API-Endpoints unter `/api/v1/zone-automation/`

---

## Bug Fixes

- **Critical:** `async init_services()` wurde ohne `await` aufgerufen
- **Critical:** Voice zone aliases Bug behoben
- **Async:** Alle deprecated asyncio event loop patterns in 11 Dateien ersetzt
- **Illumination:** Ratio lower bound Clamping verhindert negative Werte
- **Engine References:** Fehlende Engine-Referenzen und async init korrigiert
- **Musikwolke Pipeline:** Error handling, Input validation, Bridge wiring

---

## Core API-Endpunkte (HA-integriert)

| API Pfad | HA Service |
|----------|-----------|
| `POST /api/v1/musikwolke/create` | `copilot_ha.musikwolke_create` |
| `POST /api/v1/musikwolke/dissolve` | `copilot_ha.musikwolke_dissolve` |
| `POST /api/v1/musikwolke/volume/<zone_id>` | `copilot_ha.musikwolke_volume` |
| `POST /api/v1/media/zones/<id>/play` | `copilot_ha.musikwolke_play` |
| `POST /api/v1/media/zones/<id>/pause` | `copilot_ha.musikwolke_pause` |
| `POST /api/v1/media/musikwolke/start` | `copilot_ha.musikwolke_start_follow` |
| `POST /api/v1/media/musikwolke/<id>/stop` | `copilot_ha.musikwolke_stop_follow` |
| `POST /api/v1/zone-automation/zones/<id>/mode` | `copilot_ha.zone_automation_set_mode` |

---

## Dokumentation

| Dokument | Beschreibung |
|----------|-------------|
| `docs/HANDBUCH.md` | Deutsches Benutzerhandbuch |
| `docs/INSTALLATIONSANLEITUNG.md` | Installationsanleitung |

---

## Upgrade-Hinweise

- **Breaking Changes:** Keine
- **Migration:** `ha addons update pilotsuite_core`
- **Neue Dependencies:** Keine

---

## Statistiken

- **58 Dateien geaendert** (+8.016 / -1.581 Zeilen)
- **12 neue Dateien** (Module, Endpoints, Tests, Docs)
- **3720+ Tests**

---

**PilotSuite v13.7.0** — Local-first, Privacy-first, Governance-first.
