# Changelog

Alle wesentlichen Aenderungen am PilotSuite Styx Core werden in dieser Datei dokumentiert.

## [v13.10.0] - 2026-03-13

### Quality Release — Alle Tests gruen, Code-Bugs behoben

#### Bug Fixes
- **zone_dashboard.py**: `entity_ids`, `entities_by_role`, `scenes_data` waren undefiniert in `get_zone_detail()` (NameError zur Laufzeit)
- **core_setup.py**: `sonos_bp` Doppel-Registrierung entfernt, `sharing_bp`/`federated_bp` Dreifach-Registrierung bereinigt

#### Test Infrastructure
- **pytest-asyncio 0.25.3** installiert — ~120 async-Test-Failures behoben
- **test_sonos.py** komplett umgeschrieben (Flask Services Injection statt entfernter `init_sonos_api`)
- **Auth-Isolation**: `_AuthEnabledTestCase` Base-Class fuer Tests die Auth brauchen
- **ModuleRegistry Singleton-Leak** behoben (DB_PATH Override + conftest Reset)
- 6 weitere Test-Dateien individuell korrigiert

#### Ergebnis
- **Vorher**: 152 failed + 58 errors (210 Test-Probleme)
- **Nachher**: 0 failed, 4133 passed, 118 skipped
- HA Tests: 373 passed, 0 failed, 41 skipped

---

## [v13.9.0] - 2026-03-13

### Offizielles Release — Alle Beitraege seit v13.5.8

Dies ist das konsolidierte offizielle Release, das alle Entwicklungen seit dem letzten getaggten Release (v13.5.8) zusammenfasst.

### Neue Features

#### RAG Hybrid Search im Chat
- **Reciprocal Rank Fusion (RRF)**: BM25 + Semantic Search kombiniert fuer Chat-Antworten
- **Open-Meteo Wetter-Integration**: Echtzeit-Wetterdaten direkt im Chat abrufbar
- **Wecker-Modul**: Neues Hub-Modul fuer Alarm/Weckfunktionalitaet

#### Zone Dashboard v3 (11 Hub-Engines)
- Zonenzentriertes Dashboard mit vollstaendiger Modulintegration
- Controls, Musik, Playlists, Notifications, Birthdays, Todos pro Zone
- Refactored fuer Effizienz und Failsafety

#### 5 PilotSuite Smart Home Module
| Modul | Beschreibung |
|-------|-------------|
| `licht_module.py` | Lichtsteuerung mit Szenen und Dimming |
| `helligkeit_module.py` | Helligkeitssensor-Auswertung und Lux-Management |
| `heiz_module.py` | Heizungssteuerung mit Zieltemperatur und Zeitplaenen |
| `bewegung_module.py` | Bewegungsmelder-Aggregation und Raumaktivitaet |
| `praesenz_module.py` | Praesenz-Tracking und Aufenthaltsanalyse |

#### Musikwolke Bridge — End-to-End Sonos-Integration
- **MusikwolkeBridge**: Hub-Modul verbindet ZoneAutomationController mit SonosCloudClient und MediaFollowEngine
- **Zone-Speaker-Mapping**: Automatische und manuelle Zuordnung von Zonen zu Sonos-Raeumen
- **Follow-Mode**: Musik folgt dem Nutzer automatisch zwischen Raeumen via Sonos-Gruppierung
- **Musikwolke API**: 8 neue REST-Endpoints unter `/api/v1/musikwolke/`
- **Sonos jishi API Integration** (Port 5005) mit REST Blueprint

#### Automation-Modus-System (off/learning/autonomy)
- 3-Stufen-Modus pro Zone mit API-Endpoints
- ZoneAutomationController respektiert Modus bei Praesenz-Events

#### Tag-System — Bidirektionale Synchronisierung
- 13 neue Zone-Rollen-Tags in tags.yaml (aicp.role.*)
- Kanonische Tag-IDs mit Mapping
- HA <-> Core Sync via POST `/api/v1/tag-system/tags/sync`

#### Zone Automation Controller
- Praesenzabhaengige Licht- und Musiksteuerung mit konfigurierbaren Delays
- Entity-Management mit Auto-Rollenerkennung (11 Rollen) und Auto-Tagging (13 Tags)
- 16 API-Endpoints unter `/api/v1/zone-automation/`
- Hysterese/Daempfung gegen Flackern bei Wolkendurchzug

#### Styx Dashboard — Automation-Tab (Tab 5)
- Zone Automation Cards, Toggle Switches, Entity-Management UI
- 9 Tabs: Overview, Zonen, Musikwolke, Vorschlaege, Automation, KI/LLM, Module, Neuronen, Chat
- Keyboard Shortcuts 1-9, Auto-Refresh 30s, Tab Persistence

#### Suggestions API & Musikwolke Sonos
- Blueprint `/api/v1/suggestions` mit Accept/Reject/Snooze-Lifecycle
- Sonos-Gruppierung/-Entgruppierung Endpoints
- DynamicNeuronFactory fuer Cross-Module Neuron-Erstellung

#### Automation Repair & Suggestions
- Automation Repair Endpoint
- Suggestions API Repairs Endpoint
- Alle Platzhalter-Endpoints durch funktionalen Code ersetzt

#### Cross-Module Wiring
- 14 zuvor nicht registrierte API Blueprints verdrahtet
- Aggregierte Endpoints `/api/v1/modules/dashboard` und `/zones/<zone_id>`
- Vollstaendige RAG Chat Pipeline mit Modul-Anreicherung

### Code-Qualitaet & Hardening

- **Thread-Safety**: Double-Checked Locking, Service Registry Improvements
- **Resource Leaks**: Alle offenen Handles geschlossen
- **Silent Error Swallowing**: `except: pass` Bloecke durch Debug-Logging ersetzt
- **App Factory**: Shared Brightness Filter, API Contract Verbesserungen
- **Automation Hardening**: From-State Guards und TTS Delay

### Bug Fixes

- **Critical**: `async init_services()` wurde ohne `await` aufgerufen
- **Critical**: Voice zone aliases Bug behoben
- **Async**: Alle deprecated asyncio event loop patterns in 11 Dateien ersetzt
- **Illumination**: Ratio lower bound Clamping verhindert negative Werte
- **Engine References**: Fehlende Engine-Referenzen und async init korrigiert
- **Musikwolke Pipeline**: Error handling, Input validation, Bridge wiring
- **Performance Module**: Fehlende `dashboard/api/v1/performance.py` erstellt

### Versions-Synchronisierung
- Einheitliche Version 13.9.0 in allen Artefakten
- Paired Release: Core v13.9.0 <-> HA v13.9.0

### Test Coverage
- **3720+ Tests** passed, 0 failed
- 38+ neue Tests fuer Zone Automation Controller + API
- 51+ neue Tests fuer Dashboard Iterationen

---

## [v13.7.0] - 2026-03-11

### Musikwolke HA-Integration & Dokumentation
- **HA-Services**: 8 neue Services steuern alle Musikwolke-Endpunkte aus HA Automations
- **Dokumentation**: Handbuch, Installationsanleitung
- **Versions-Synchronisierung**: Alle Artefakte auf 13.7.0

## [v13.6.0] - 2026-03-11

### Musikwolke Bridge — End-to-End Sonos-Integration
- **MusikwolkeBridge**: Neues Hub-Modul verbindet ZoneAutomationController mit SonosCloudClient und MediaFollowEngine
- **Zone-Speaker-Mapping**: Automatische und manuelle Zuordnung von Zonen zu Sonos-Raeumen
- **Follow-Mode**: Musik folgt dem Nutzer automatisch zwischen Raeumen via Sonos-Gruppierung
- **Musikwolke API**: 8 neue REST-Endpoints unter `/api/v1/musikwolke/` (status, zone-map, play, pause, volume, create, dissolve, auto-discover)

### Automation-Modus-System (off/learning/autonomy)
- **3-Stufen-Modus** pro Zone: `off` (nur Zustand), `learning` (Zustand + Muster lernen), `autonomy` (volle Automatisierung)
- **Modus-Integration**: ZoneAutomationController respektiert Modus bei Praesenz-Events
- **API-Endpoints**: GET/POST `/api/v1/zone-automation/zones/{zone_id}/mode`
- **Dashboard-Integration**: Modus wird in Zone-State und Dashboard angezeigt

### Tag-System — Bidirektionale Synchronisierung
- **13 neue Zone-Rollen-Tags** in tags.yaml: aicp.role.licht bis aicp.role.styx
- **Kanonische Tag-IDs**: Mapping zwischen Kurznamen und aicp.role.* IDs
- **HA → Core Sync**: POST `/api/v1/tag-system/tags/sync` fuer bidirektionalen Tag-Austausch
- **TagZoneIntegration**: Auto-Erstellung von HabitusZones aus aicp.place.* Tags

### Zone Dashboard — Echtdaten statt Mockups
- **MoodService-Integration**: Echte Mood-Abfragen statt Mock-Daten
- **ZoneAutomationController-Abfragen**: Live Entity-Counts, Occupancy, Brightness
- **HabitusZones-Metriken**: Echte Daten aus ZoneAutomationController

### Versions-Synchronisierung
- **Einheitliche Version 13.6.0**: Alle VERSION-Dateien, config.yaml und manifest.json synchronisiert
- **Paired Release**: Core + HA identische Versionsnummer

### TagRegistry — Erweiterte Methoden
- `remove_from_zone`, `get_zone_members`, `get_zones`, `get_subject_tag_ids`, `get_context_for_llm`, `auto_tag_styx`

### Added
- Chat Blueprint (`/api/styx/chat`, `/api/styx/health`)
- Home Assistant Add-on Support
- requirements.txt für Dependencies

### Fixed
- Core Services Init (brain_graph, conversation_memory, vector_store)
- Ollama API 400 Error (glm-5 → qwen3.5:397b-cloud)

### Changed
- Legacy Endpoint deprecated (`/api/v1/legacy/health`)
- OpenAPI synced (551/551 aligned)

### Closed
- Drift-A: 5 zone/mood paths

## v13.5.7 (2026-03-09)

### Added
- Initial release
