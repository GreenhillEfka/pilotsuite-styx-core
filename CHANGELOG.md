# Changelog

Alle wesentlichen Aenderungen am PilotSuite Styx Core werden in dieser Datei dokumentiert.

## [v15.2.4] - 2026-03-28

### Added
- PR #157 übernommen: behebt verbleibende HA↔Core-Zone-Sync-Lücken im Automation-Flow (`zone_automation`) inklusive `sync-definitions` Konsistenz und robusteren Hold/State-Pfaden.
- Neue Tests für Zone-Automation-Sync und API-Handling ergänzt.

### Fixed
- Stabilere Übergabe von Presence-/Zone-Metadaten in Core-Hot-Path bei fehlenden Feldern.

### Paired
- Bereit für Paarung mit HA-Linie v15.2.4 (geplante Folgeveröffentlichung).
- Bereit für Paarung mit HA-Linie v15.2.4.


## [v15.0.18] - 2026-03-25

**PilotClaw Autonom-Entwicklung** (2026-03-24/25)

**Paired mit:** HA v15.0.17 (同期)

#### Added
- **Entity Sorter**: `copilot_core/habitus/entity_sorter.py` — HA-Entity→Habitus-Zone Matching mit Keyword-basiertem Confidence-Score (0.0–1.0). Portiert von HA v15.0.0 `habitus_entity_sorting.py`. 12 Zonen-Mappings inkl. room_mira/room_paul. Threshold 0.5 → ungeordnet.
- **Presence-Health Korrelation**: `copilot_core/zone_health/` erweitert um `PresenceHealthCorrelation`, `correlate_presence_health()` und `get_presence_health_insights()`. Leitet aus Presence+Health: occupancy_impact, absence_risk, recommended_action.
- **S2TA Quick Wins (Ops)**: `services/cron_watchdog.py`, `utils/checkpoint.py`, `utils/dms.py` — Cron-Überwachung + Resume-Checkpoint + Dead-Man-Switch Adapter für SOTA-Scout.

#### Changed
- **CHANGELOG**: Struktur angepasst für Autonomous-Release-Workflow

---

## [v15.0.17] - 2026-03-23

### HA+Core Version Sync (Post-v15.0.4 Alignment)

**Paired mit:** HA v15.0.17

#### Added
- **Zone Health Module**: `copilot_core/zone_health/` — Umgebungssensorik (Temperatur, Feuchtigkeit, CO2, Lux) mit Health-Score 0-100 und Komfort-Ranges. Portiert von HA v14.7.5 `zone_health.py`. Enthält `ZoneHealthMetrics` dataclass und `ZoneHealthStore` Singleton mit History/Trend.
- **MCP Tool `get_zone_health`**: LLM-Zugriff auf zonale Umgebungsmetriken via `/mcp` JSON-RPC Endpoint.
- **Habitat Adapter**: `copilot_core/homeassistant/habitat_adapter.py` — HA↔Core Contract Boundary. Normalisiert HA-Events (state_changed, call_service) zu Core NeuronInput und Core-Proposals zu HA-Service-Commands. Contract-Versionen: `ha.input.v1` / `ha.output.v1`. Portiert von HA v15.0.0.
- **Habitat Adapter Tests**: `tests/test_habitat_adapter.py` — 21 Test-Cases für alle Adapter-Funktionen.

#### Fixed
- **Version Alignment**: Core `VERSION`, `copilot_core/VERSION`, `copilot_core/config.yaml`, `copilot_core/rootfs/usr/src/app/addon/config.json` auf `15.0.17` synchronisiert.
- **Event Ingest Contract**: `events_ingest.py` angepasst, Payload-Validierung fuer HA→Core Sync verschärft.
- **Schema Extension**: `schemas.py` um 214 Zeilen erweitert für neue Event-Typen und Validierungsregeln.
- **Event Processor**: `event_processor.py` und `event_store.py` überarbeitet für höhere Zuverlässigkeit bei der Event-Verarbeitung.

#### Added
- **Neue Tests**: `test_event_processor.py` und `test_event_store.py` für stabilisierte Event-Verarbeitung.
- **Dokumentation**: `CORE_CONCEPT_DIRECTIVE.md`, `CORE_CONCEPT_HANDOFF.md`, `HA_CORE_INGEST_CONTRACT.md` als neue Architektur-Leitdokumente.

---

## [v15.0.4] - 2026-03-22

### Runtime Version Truth Repair

**Paired mit:** HA v15.0.4

#### Fixed
- **Packaged Runtime Version**: `copilot_core/rootfs/usr/src/app/VERSION` von veraltetem `14.7.3` auf `15.0.4` gehoben, sodass `/version` und `/health` nicht mehr auf den alten Fallback zurueckfallen.
- **Release-Metadata Sync**: `VERSION`, `copilot_core/VERSION`, `copilot_core/config.yaml`, `copilot_core/manifest.json` und die verpackte Runtime-Version wieder auf einen Stand harmonisiert.
- **Regression Guard**: Test ergaenzt, der `rootfs/usr/src/app/VERSION` gegen `manifest.json` prueft, damit dieser Drift nicht erneut released wird.

---

## [v15.0.3] - 2026-03-21

### Release Metadata + Zone Sync Cleanup

**Paired mit:** HA v15.0.1

#### Fixed
- **Release-Wahrheit harmonisiert:** `VERSION`, `copilot_core/VERSION`, `copilot_core/config.yaml`, `copilot_core/manifest.json`, README und Release-Dokumentation auf `15.0.3` zusammengezogen.
- **Zone-Definition-Sync sauber releast:** der bereits auf `main` vorhandene `/api/v1/zone-automation/sync-definitions` Contract wird jetzt nicht mehr von veralteten Release-Metadaten verdeckt.
- **Paired Reporting Cleanup:** Core-Release wieder klar von HA/HACS `v15.0.1` und Live-Stand getrennt dokumentiert.

---

## [v15.0.0] - 2026-03-21

### Phase 7 Production Readiness Foundation

**Paired mit:** HA v15.0.0

#### Paired HA→Core Features

- **Zone-Presence Hold API**: `POST /api/v1/presence/zone/presence/<zone_id>/hold` — auto/force_on/force_off persistence
- **Zone-Presence State API**: `POST /api/v1/presence/zone/presence/<zone_id>/state` — aggregate presence to Core Neurons
- **Legacy Path Aliases**: `/api/v1/zone/presence/<zone_id>/hold` maintained for backwards compatibility
- **Paired Release Gate**: VERSION + CHANGELOG harmonisiert

#### Architecture

- **Module Lazy-Loading** (HA-side): Tiered loading — EAGER (3), DEFERRED (4), ON_DEMAND (26) modules
- **Schema TTL Cache** (HA-side): 1h refresh instead of single-fetch

#### Metadata

- **Core Add-on Sichtbarkeit**: `copilot_core/config.yaml` und `copilot_core/manifest.json` auf `15.0.0` harmonisiert

---

## [v14.9.0] - 2026-03-21

### Phase 7 — Production Foundation

#### Added
- **Zone-Presence Hold API**: `POST /api/v1/presence/zone/presence/<zone_id>/hold` mit auto/force_on/force_off states
- **Zone-Presence State API**: `POST /api/v1/presence/zone/presence/<zone_id>/state` fuer persistente Presence-Signale
- **Legacy Path Aliases**: `/api/v1/zone/presence/<zone_id>/hold` bleibt funktional (Rueckwaertskompatibilitaet)

#### Changed
- **Presence v3.4**: Multi-Source Aggregation mit any-on Regel, hold/override, source-tracking
- **Zone-Based Miner**: Semantic bucketing, confidence/lift scoring fuer automatische Zone-Proposals
- **Zone-Proposals API**: `GET/POST /zone-proposals` + `POST /zone-proposals/accept` mit Modul-Policy
- **Module-Overrides**: ZoneType-basierte Overrides (light/motion/music/volume/tv/climate/camera)

#### Fixed
- **Dashboard ZONE_CONFIG**: German Slugs (`wohnbereich`, `schlafzimmer`, `kueche`, `badezimmer`, `kinderzimmer`, `buero`, `aussenbereich`) harmonisiert
- **Outdoor Aliases**: Terrasse/Balkon/Loggia kanonisch → OUTSIDE

---

## [v14.8.1] - 2026-03-21

### Release Candidate fuer Live-HA-Test

#### Added
- **Zone-Presence API**: `POST /api/v1/presence/zone/presence/<zone_id>/hold` und `POST /api/v1/presence/zone/presence/<zone_id>/state` fuer persistente HA-Area-Presence-Signale.
- **Zone-Summary Alignment**: Dashboard-Zonen auf HA-Habitus-Slugs (`wohnbereich`, `schlafzimmer`, `kueche`, `badezimmer`, `kinderzimmer`, `buero`, `aussenbereich`) harmonisiert, inkl. `presence`, `media_playing`, `lights_on`, `presence_hold`.

#### Fixed
- **Paired Release Gate**: Versionsdateien (`VERSION`, `copilot_core/VERSION`, `manifest.json`) auf `14.8.1` harmonisiert fuer den gemeinsamen Test-Release mit HA.

## [v14.7.5] - 2026-03-20

### Zone-Proposals & Configuration

#### Added
- **ErrorResponse Library**: `ErrorResponse` + `error_response_payload()` als neue Shared Library
- **Zone-Proposals API**: `GET/POST /zone-proposals` + `POST /zone-proposals/accept` mit Modul-Policy
- **ZoneResponse Erweiterung**: `/zones/assign` mit ErrorResponse-Examples (400/404)
- **module_overrides**: ZoneType-basierte Module-Overrides (`light/motion/music/volume/tv/climate/camera`)
- **Outdoor Aliases**: Terrasse/Balkon/Loggia kanonisch → OUTSIDE

### Presence v3.4

#### Added
- **Multi-Source Aggregation**: `any-on`-Regel mit hold/override und sources-Tracking
- **Numeric Bucketing**: Lux→dark/bright, Temp→cold/warm
- **ZoneBasedMiner**: Semantic bucketing, confidence/lift scoring

### Zone-Editor & API

#### Added
- **zone_editor.ts**: API v1 mit `domain` optional, `rooms[]`, `entity_count`

#### Changed
- **OpenAPI Sync**: `/zones/assign` Pilot, Version → 14.7.3

## [v14.7.3] - 2026-03-17

### Module-per-Zone Architektur + Neues Styx Dashboard

#### Added
- **Zone Modules Package** (`hub/zone_modules/`): Selbstbeschreibende Module mit ZoneModuleConfig ABC, ZoneModuleFieldSpec und Decorator-basierter Registry
- **7 Zone-Module**: Light, Music (migriert), Climate, Cover, Energy, Scene, Security (neu)
- **Module-Schemas API**: `GET /api/v1/zone-automation/module-schemas` — Schema-Endpoint fuer dynamische UI-Generierung
- **Module-Config API**: `GET/POST /zones/<zone_id>/modules/<module_id>` — Per-Zone Modul-Konfiguration
- **Module-Entities API**: `GET /zones/<zone_id>/modules/<module_id>/entities` — Entity-Matching via Domain/Role/Tag
- **Neues 7-Tab Styx Dashboard**: Brain+Chat, Module, Stimmung, Habitus, Habituszonen, Status, Einstellungen
- **Dashboard UX**: localStorage Tab-Persistenz, Auto-Refresh Countdown, Zone-Detail-Modal, Escape/R-Key Shortcuts
- **24 neue Tests**: test_zone_modules.py (Registry, Configs, API-Endpoints, Round-Trip Serialisierung)

#### Changed
- **ZoneAutomationConfig**: Refactored mit `modules: dict[str, ZoneModuleConfig]` + rueckwaertskompatible Legacy-Keys
- **to_dict/from_dict**: Gibt sowohl `light`/`music` Top-Level als auch `modules` Dict zurueck

#### Fixed
- **CandidateStore** Type-Hint Crash auf Python 3.12+ (`from __future__ import annotations`)
- **user_hints Blueprint**: Doppelte Registration aus `_EXTRA_BLUEPRINTS` entfernt
- **Dashboard UX Tests**: Angepasst an neues 7-Tab Layout

### Compatibility
- Core v14.7.3 <-> HA v14.7.3 (Paired Release)
- Tests: 4430 passed, 118 skipped

---

## [v14.6.1] - 2026-03-16

### Backend-Dashboard Modul-Config-Overhaul

#### Changed
- **Modul-Config**: Expandierbare per-Modul Config-Panels ersetzen zentralisiertes Dropdown
- **16 MODULE_CONFIG_SPECS**: Typisierte Konfigurationsfelder (toggle, range, number, select) pro Modul
- **Neue Kategorie "Styx Gehirn"**: Character, Attribution, User Hints, Konflikte, ML Pipeline im Modul-Tab
- **Live-Daten**: Jedes Modul zeigt Echtzeit-Stats und hat eigene Action-Buttons

### Compatibility
- Core v14.6.1 <-> HA v14.6.1 (Paired Release)

---

## [v14.6.0] - 2026-03-16

### Backend Dashboard Komplett-Ueberarbeitung + Modul-Migration HA→Core

#### Added
- **Backend Dashboard**: Komplett neues 7-Tab-Dashboard (Styx, Module, Stimmung, Habitus, Habituszonen, Status, Einstellungen)
- **Brain Canvas**: 3-Layer Neuron-Visualisierung (Context/State/Mood) mit Pulsier-Animation
- **4 neue Netzwerk-Module**: ZWave, Zigbee, Thread, HomeAssistant (hub/ + api/v1/ Blueprints)
- **Modul-Migration von HA**: ML Pipeline, CharacterService, ActionAttribution, UserHints, PII-Service in Core verschoben
- **Conflict Resolution API**: `/api/v1/conflicts/state`, `/evaluate`, `/strategy`

#### Changed
- **Dashboard Design**: Glassmorphism Cards, Sidebar-Navigation, Keyboard Shortcuts (1-7)
- **Styx Tab**: Brain Graph + Chat + Neuronen zusammengefuehrt als Startseite

#### Fixed
- 4 vorbestehende Test-Failures (user_id optional + mood schema migration)

### Compatibility
- Core v14.6.0 <-> HA v14.6.0 (Paired Release)
- Tests: 1826 passed, 112 skipped

---

## [v14.5.0] - 2026-03-16

### Backend Dashboard + Netzwerk-Module

#### Added
- Backend Dashboard initial redesign (7 Tabs)
- ZWave, Zigbee, Thread Module (Supervisor API)

---

## [v14.4.7] - 2026-03-15

### Styx Chat Auth + Mood Fix

#### Fixed
- styx-chat auth Token-Handling
- mood Supervisor API Fix
- user_id optional in verschiedenen Endpoints

---

## [v14.4.4] - 2026-03-15

### Mood History DB Fix + Backend Dashboard Mining Controls

#### Fixed
- **MoodHistoryStore Table Conflict**: Tabelle umbenannt von `mood_snapshots` zu `neuron_mood_history` — verhindert Schema-Kollision mit MoodService (mood/service.py) die dasselbe DB-File nutzt
- **Mood History/Trend API**: `GET /api/v1/neurons/mood/history` und `/trend` gaben zuvor `"no such column: ts"` zurueck

#### Added
- **Backend Dashboard: Mining Controls**: Mining-Status (Regeln, Events, Letztes Mining), manueller Mining-Trigger-Button, Config-Anzeige auf der Habitus-Seite
- **Backend Dashboard: Mood History**: Neuron Mood History Tabelle mit Zeitraum-Auswahl (1h/6h/24h/7d), Trend-Statistiken, Dominant-Mood-Anzeige

### Compatibility
- Erfordert keine Aenderungen an pilotsuite-styx-ha
- Bestehende mood_snapshots Daten (MoodService) bleiben erhalten
- Neue neuron_mood_history Tabelle wird automatisch erstellt

## [v14.4.2] - 2026-03-15

### Auto-Mining, Mood History, Feedback Loop

#### Added
- **Auto-Mining**: EventProcessor triggert automatisch Habitus-Mining (1000 Events / 3600s Intervall)
- **MoodHistoryStore**: SQLite Time-Series fuer Mood-Evaluationen mit Rate Limiting und Cleanup
- **Mood API**: `GET /api/v1/neurons/mood/history` + `GET /api/v1/neurons/mood/trend`
- **Habitus Config**: `POST /api/v1/habitus/config` fuer Mining-Konfiguration von HA
- **Feedback Store**: Gewichtungsmultiplikatoren (accepted=1.5x, rejected=0.1x, snoozed=0.5x)

#### Changed
- Event Envelope unterstuetzt `neuron_tags` fuer Layer-Klassifikation
- NeuronManager verarbeitet neuron_tags aus HA-Events

### Compatibility
- Core v14.4.2 <-> HA v14.4.2 (Paired Release)
- Tests: 1793+ passed, 29 neue Mood-History-Tests

---

## [v14.4.0] - 2026-03-15

### Version Sync mit HA v14.4.0
- Zone Automation Controller Erweiterungen

---

## [v14.3.18] - 2026-03-15

### Dashboard Auth Fix
- X-Auth-Token fuer Ingress-Kompatibilitaet

---

## [v14.3.17] - 2026-03-15

### Paired Release mit HA v14.3.17

#### Fixed (v14.3.0-v14.3.16)
- **Ingress Dashboard**: `detectIngressBasePath()` erkennt HA-Ingress-Pfade korrekt — API-Calls gehen an Core statt an HA
- **Auth Header**: `X-Auth-Token` statt `Authorization: Bearer` (HA Ingress Proxy strippt Authorization)
- **System Health**: CPU%, RAM, Disk, Uptime, Service-Verfuegbarkeit im Dashboard
- **Cloud API**: URL + Key im Dashboard konfigurierbar
- **Blueprint-Registrierung**: automations_bp (5 Endpoints) + onboarding_bp (5 Endpoints) verdrahtet
- **Null-Safety**: postJSON(), fetchJSON() Aufrufer abgesichert

#### Version Bump
- Reine Versions-Synchronisierung mit HA v14.3.17

---

## [v14.2.0] - 2026-03-14

### Autonomie-Execution + Sammelentitaeten + Zone Health

#### Neue Module
- **AutonomyExecutor**: Mood-getriebene Auto-Execution — Bus-Event → Governance-Check → HA-Service-Call → RAG-Log
- **MoodActionMapper**: Stimmung-zu-Aktion-Tabellen (Licht-Szenen, Musik-Favoriten, Wetter-Overlay)
- **HABridge**: Direkte HA Service Calls aus Core (light.turn_on, scene.turn_on etc.)
- **BehavioralLog**: RAG-indexierte Autonomie-Aktionshistorie (BM25, 30 Tage Retention)
- **DeviceClassAggregator**: Geraeteklassen-basierte Entitaets-Aggregation (11 Kategorien)
- **ZoneHealthChecker**: Per-Zone Gesundheitsmonitoring (Score 0-100, Entity-Verfuegbarkeit, Staleness)

#### Neue APIs
- `POST /api/v1/autonomy/zones/<zone_id>/module` — Per-Zone Modul-State setzen
- `GET /api/v1/autonomy/dashboard` — Autonomie-Dashboard (Stats, Zone-Modi)
- `GET /api/v1/autonomy/mood-actions` — Mood-Action-Mapping-Tabelle
- `GET /api/v1/zone/aggregates/<zone_id>` — Sammelentitaeten per Zone
- `POST /api/v1/zone/aggregates/<zone_id>/scene/capture` — Zone-Szene erfassen
- `POST /api/v1/zone/aggregates/<zone_id>/scene/apply` — Zone-Szene anwenden
- `GET /api/v1/zone/health` — Zonen-Gesundheitsuebersicht
- `GET /api/v1/zone/health/<zone_id>` — Detaillierte Zone-Gesundheit

#### Erweiterungen
- **ModuleRegistry**: Per-Zone Modul-States (zone_module_states SQLite-Tabelle, Fallback auf globalen State)
- **IntegrationBus**: 18 Event-Typen (neu: state.changed, device.metric, anomaly.detected)
- **Double-Safety Governance**: Zone automation_mode + Source/Target Modul-State + Rate-Limiting (30s)
- **Zone Scene Persistence**: SQLite-basiert mit WAL-Modus (statt In-Memory Cache)
- **10 Zone-Presets**: Morgen, Tag, Abend, Nacht, Film, Party, Konzentration, Abwesend, Romantisch, Gaeste
- **NeuronManager**: get_last_result() fuer Weather-Context Integration

#### Bugfixes
- AutonomyExecutor Bus-Wiring: Executor wurde nach Bus-Subscription erstellt → Dead Wiring
- AggregateEntity.attributes nie befuellt → Summarize-Funktionen bekamen leere Dicts
- zone_health zone_id_norm war No-Op → Zone-IDs nicht normalisiert
- SQLite Connections ohne try/finally → Resource-Leaks bei Fehlern
- BehavioralLog _time_of_day nutzte UTC statt Europe/Berlin
- Health-Score Double-Deduction fuer fehlende Rollen
- @require_token fehlte auf Autonomie-API-Endpoints

#### Tests
- 4293 Tests bestanden, 0 fehlgeschlagen, 118 uebersprungen
- 67 neue Tests (9 neue Testdateien)

---

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
- OpenAPI synced (572/572 aligned)

### Closed
- Drift-A: 5 zone/mood paths

## v13.5.7 (2026-03-09)

### Docs
- Webhook contract mirrored in OpenAPI
- Version files normalized for aligned dual-repo release

---

## [v13.0.0 - v13.5.8] - 2026-03-02 bis 2026-03-10

### Phase 13 — Webhook-Haertung, OpenAPI-Konsolidierung, Add-on-Konformitaet

- **Webhook Delivery Pipeline**: DeliveryQueue, WebhookPusher mit Retry-Klassifizierung, Backoff, Backpressure, Payload-Guards, SSRF-Destination-Policy
- **Webhook Security**: Signing Headers (Replay-Schutz), Key-Rotation (Primary/Secondary), per-Destination Rate-Limits
- **OpenAPI Reconciliation**: 130 Hub-Pfade abgeglichen, Allowlist-Diff CI-Workflow, 21 Stub-Endpoints (501)
- **Auth-Migration**: `X-Auth-Token` als bevorzugter Header (`X-API-Key` deprecated)
- **RAG Search API**: BM25 + Semantic Search, TTL-Cache, Rate-Limiting, Namespace-Validierung
- **Module Registry API**: `/api/v1/modules` REST-Endpoints, `/api/styx/health/backend`
- **Chat Blueprint**: `/api/styx/chat` registriert, Core Services Init repariert
- **HA Add-on**: config.yaml/manifest.json konform, Zone/Mood-Pfade abgesichert

---

## [v12.0.0 - v12.21.0] - 2026-03-01 bis 2026-03-02

### Phase 12 — RAG Conversation, Connection Pooling, Security Hardening

- **RAG Conversation** (v12.1.0): Hybrid Search mit SearXNG-Integration, Neuron Visualization API + WebSocket
- **Connection Pooling** (v12.13.0): 28.5x schnellere API-Responses, Hybrid Cache (Redis + LRU), Query Optimizer
- **Security Hardening**: WebSocket Auth, Neuron State Override Protection, Zone-ID Sanitization, Rate-Limiting, Admin Token Enforcement
- **Dashboard**: 3D Vision (Three.js), Energy Forecast, Swagger UI, Prometheus Monitoring, Voice Integration
- **ML Pipeline**: LSTM/Transformer-Modelle, Anomaly Detection API, Predictive Automation
- **HA Auto-Discovery** (v12.8.0): Habitus Dashboard, Zone Matching, Task Queue System
- **Codequalitaet**: 2201 Tests, 8 kritische Bugs behoben, 815 tote API-Stubs entfernt

---

## [v11.1.0 - v11.9.0] - 2026-02-27 bis 2026-03-01

### Phase 11 — Dual-Repo Architektur, RAG Hybrid Search, Phase 5/6 APIs

- **Dual-Repo Architektur** (v11.1.0): System Message Merge, MUPL Feedback-Loop, HA-Core Sync-Protokoll
- **RAG Hybrid Search** (v11.5.0+): BM25 + Semantic mit RRF Fusion, SearXNG-Integration
- **Phase 5 APIs** (v11.3.0): Sharing, Notifications, Collective Intelligence — Integration Tests komplett
- **HA Notify Adapter**: Push-Notifications aus Core an HA
- **Zone-Editor v1** (v11.7.0): UX Dashboard Foundation, Frontend Zone-Dashboard
- **Neural Confidence Hardening** (v11.2.0): Docs Freshness Gate, Context-ID SHA256 Hashing
- **Type Hints**: Phase 6 Type Hints fuer Notifications, Sharing, CI APIs komplett

---

## [v10.0.0 - v10.4.2] - 2026-02-26 bis 2026-02-27

### Phase 10 — Override Modes, Mood Engine v3.0, Strukturbereinigung

- **Override Modes** (v10.0.0): Musikwolke Coordinator Handoff, Volume-Presets, Light-Presets
- **Mood Engine v3.0** (v10.2.0): Unified Mood Engine — Models, Engine, Service, API; defensive Input-Validierung
- **Habitus Miner Trends** (v10.1.x): Climate-aware Zone Automation, Shopping, Network, Calendar/Weather Dashboard
- **Security Hardening** (v10.3.0): Data-driven Blueprint-Registration (37 try/except Bloecke durch Loop ersetzt)
- **Strukturbereinigung**: 815 tote API-Stubs entfernt, FastAPI v2 Modul geloescht
- **EventBus Bridges**: Logik-Struktur gehaertet, Auto-Setup API Endpoints

---

## [v9.0.0 - v9.3.0] - 2026-02-26

### Phase 9 — Entity Search v2, HA Bridge, Dashboard Restrukturierung

- **HA Bridge**: HA-Daten aus Add-on heraus via REST + WebSocket entdecken
- **Entity Search v2** (v9.1.0): Device Cache, Manufacturer Filter, Labels, Bulk Import, Zone Suggestions, Role Inference
- **Dashboard Restrukturierung**: Tier-separierte Module, Overview Health Panel, Chat Tab
- **Neuronenlayer 3-Ring Visualization**: Tagged-not-in-Zone Panel
- **Config Services**: Endpoint-Fix, Dashboard Model Download + Manual Entry

---

## [v8.0.0 - v8.12.1] - 2026-02-24 bis 2026-02-26

### Phase 8 — Scene/Routine Extractors, Habitus Management, Self-Repair

- **Scene + Routine Pattern Extractors** (v8.0.0): Dashboard API, MCP Phase 2 Core Tools
- **Brain Graph + Habitus Sensors** (v8.2.0): Core API Integration, Dashboard Improvements
- **RAG Document Pipeline** (v8.7.0): Module Control erweitert, Knowledge Graph Guard
- **Habitus Automation Management** (v8.6.0): Neuron-Brain Dashboard, react-first Habitus Flow
- **HomeKit Zone Servers** (v8.10.0): QR Endpoints, Dashboard Controls
- **System Observability Dashboard**: Zone Summaries, System Health Registration gehaertet
- **Self-Repair API** (v8.11.0): Guarded Self-Repair, Workspace Clone + Branch Prep Flow
- **Musikwolke**: Cloud Model Defaults, Media Flow gehaertet

---

## [v7.0.0 - v7.125.0] - 2026-02-21 bis 2026-02-25

### Phase 7 — Brain Architecture, Presence Intelligence, MCP API-Expansion

- **Brain Architecture** (v7.4.0): Hirnregionen, Neuronen, Synapsen — Pulse, Sleep, Chat History
- **Presence Intelligence** (v7.1.0): Anwesenheits-Intelligence, Notification Intelligence (v7.2.0)
- **System Integration Hub** (v7.3.0): Cross-Engine Orchestration
- **Production-Ready** (v7.6.0): Full Engine Wiring, Granular Fault Isolation, Docker Build Fix (Alpine 3.21)
- **LLM Hardening** (v7.7.x): Ollama Readiness, Cloud Fallback, Self-Heal, Model Alias, interner Port 11435
- **MCP API Expansion** (v7.14.0-v7.125.0): Entity Management, Service Calls, Sensors, Lights, Climate, Switches, Media Players, Scenes, History, Weather, Scripts, Alerts, Webhooks, RBAC
- **Notification APIs** (v7.10.0-v7.13.0): Templates, Scheduling, Type Hints, Phase 5/6 Tests (142+ Tests gruen)
- **CI/CD**: HACS/HassFest Validation, Production Guard Workflow
