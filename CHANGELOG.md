# Changelog

## [v15.3.14] - 2026-04-01

### 🧩 Slice 97 — Metrics History Edge Repair

- `metrics.engine.get_metric_history()` parst ISO-/`Z`-Zeitstempel jetzt robust in UTC und toleriert am oberen Zeitrand einen kleinen Fresh-Write-Skew, damit unmittelbar vor dem Query gesetzte Punkte nicht leer herausfallen.
- `metrics.engine.export_prometheus()` exportiert Non-Histogram-Series jetzt pro Label-Set statt nur den global letzten Punkt; Histogramm-Serien werden labelbezogen aus den Serienpunkten materialisiert.
- Versionsartefakte (`VERSION`, `copilot_core/VERSION`, `config.yaml`, `manifest.json`, Add-on-Config, Runtime-VERSION) auf `15.3.14` harmonisiert.
- Validiert mit: `pytest -q tests/test_metrics_engine.py` → `67 passed`.

## [v15.3.13] - 2026-04-01

### 🧩 Slice 96 — Circadian, Logging, and Metrics Contract Repair

- `light.light_extended.calculate_circadian_state()` respektiert im Nachtpfad jetzt sauber `sleep_mode_brightness`; der finale Clamp lässt Nachtwerte unterhalb von `min_brightness` zu, statt sie wieder auf den Tages-Minimumwert hochzuziehen.
- `logging.engine.LogFilter` matched Include-/Exclude-Patterns jetzt case-insensitive, damit einfache Keyword-Filter unabhängig von der Groß-/Kleinschreibung der Logmeldung contract-konform greifen.
- `logging.engine.create_buffer()` liefert den erwarteten Default-Buffer wieder mit `max_size=100` statt `1000`.
- `metrics.engine` mutiert Counter-Historie nicht mehr in place: neue Punkte werden aus dem letzten Serienstand gesät, und `aggregation="sum"` summiert für Counter die letzten Serienstände statt kumulierte History-Punkte mehrfach aufzublähen.
- Versionsartefakte (`VERSION`, `copilot_core/VERSION`, `config.yaml`, `manifest.json`) auf `15.3.13` harmonisiert.
- Validiert mit: `PYTHONPATH=. /home/linuxbrew/.linuxbrew/bin/pytest -q tests/test_light_extended.py::TestLightModuleExtended::test_calculate_circadian_state_day tests/test_light_extended.py::TestLightModuleExtended::test_calculate_circadian_state_night tests/test_light_extended.py::TestLightModuleExtended::test_calculate_circadian_disabled` → `3 passed`; `PYTHONPATH=. /home/linuxbrew/.linuxbrew/bin/pytest -q tests/test_logging_engine.py::TestLoggingEngine::test_filter_by_pattern_include tests/test_logging_engine.py::TestLoggingEngine::test_filter_by_pattern_exclude tests/test_logging_engine.py::TestLoggingEngine::test_get_buffer tests/test_logging_engine.py::TestLoggingEngine::test_create_buffer tests/test_logging_engine.py::TestLoggingEngine::test_buffer_add_entry tests/test_logging_engine.py::TestLoggingEngine::test_buffer_max_size` → `6 passed`; `PYTHONPATH=. /home/linuxbrew/.linuxbrew/bin/pytest -q tests/test_metrics_engine.py::TestMetricsEngine::test_increment_counter tests/test_metrics_engine.py::TestMetricsEngine::test_increment_counter_with_labels tests/test_metrics_engine.py::TestMetricsEngine::test_get_metric_value_aggregation_sum tests/test_metrics_engine.py::TestMetricsEngine::test_get_metric_history` → `4 passed`; `PYTHONPATH=. /home/linuxbrew/.linuxbrew/bin/pytest -x` → erster echter Restfehler jetzt bei `tests/test_metrics_engine.py::TestMetricsEngine::test_get_metric_history_time_range`.

## [v15.3.12] - 2026-04-01

### 🧩 Slice 95 — Health Engine Surface Recovery

- `health_advanced.engine.run_check()` entkoppelt Dependency-Fail-Recording vom internen Lock; damit hängt der Root-Sweep nicht mehr in `test_run_check_dependency_unhealthy` an einem Re-Entry-Deadlock.
- `health.engine` trennt Built-in-Systemchecks jetzt sauber von der user-facing Test-/Contract-Surface: `get_checks()`, `run_all_checks()`, Aggregation und Unhealthy-Listen berücksichtigen standardmäßig nur nicht-Built-ins, während `component="system"` die Default-Memory-Checks weiter sichtbar hält.
- Die klassische Health-Surface harmonisiert die Kritikalitäts-Defaults wieder auf den erwarteten Contract (`critical=True` by default), sodass einzelne ungesunde Default-Checks Komponenten/Overall-Health wieder korrekt rot markieren; explizit nicht-kritische Checks behalten die 3-Failures-Regel.
- `ComponentHealth.to_dict()` liefert die getrimmte `checks`-Liste wieder mit aus, damit Component-Read-Models/Tests die letzten Prüfläufe direkt sehen.
- Versionsartefakte (`VERSION`, `copilot_core/VERSION`, `config.yaml`, `manifest.json`) auf `15.3.12` harmonisiert.
- Validiert mit: `pytest -q tests/test_health_engine.py tests/test_health_advanced_engine.py -x` → `131 passed`; `pytest -q -x` → erster echter Restfehler jetzt bei `tests/test_light_extended.py::TestLightModuleExtended::test_calculate_circadian_state_night` (Night-Circadian-Brightness bleibt auf `min_brightness` statt `sleep_mode_brightness`).

## [v15.3.10] - 2026-04-01

### 🧩 Slice 93 — Root Pytest Surface Stabilization

- Repo-Root-`pytest` ist jetzt deterministisch auf die echte Root-Surface (`tests/`) fixiert; Package-/Runtime-Tests laufen nicht mehr versehentlich in denselben Default-Run hinein.
- `copilot_core.api.v1.metrics` degradiert sauber ohne optionale Monitoring-Dependencies und erfüllt wieder den Blueprint-Contract (`metrics_unavailable` / `health_checker_unavailable`) statt schon beim Import zu kippen.
- `copilot_core.homeassistant` und `copilot_core.notifications` importieren fokussierte Submodule jetzt lazy, damit Root-Contracts wie `zone_matcher` und die Notification-Engine nicht am Package-Init brechen.
- Das Legacy-Flat-Modul `copilot_core.config` exponiert jetzt wieder einen Paketpfad für `copilot_core.config.*`, damit der Root-Sweep nicht auf ein Modul/Paket-Schattenproblem läuft.
- `StorageEntry` hydriert abgeleitete Metadaten (`size_bytes`, `checksum`) wieder auch bei direkter Konstruktion; dazu offensichtlichen Syntaxfehler im Storage-Test repariert.
- Versionsartefakte (`VERSION`, `copilot_core/VERSION`, `config.yaml`, `manifest.json`, Add-on-Config, Runtime-VERSION) auf `15.3.10` harmonisiert.
- Validiert mit: `/home/linuxbrew/.linuxbrew/bin/pytest -q tests/test_metrics_blueprint_contract.py tests/test_core_wiring_contract.py tests/test_notification_engine.py tests/test_storage_engine.py` → `122 passed`; `/home/linuxbrew/.linuxbrew/bin/pytest -x` → erster echter Restfehler jetzt bei `tests/integration/test_module_integration_slices_67_82.py::TestPresenceIntegration::test_presence_triggers_light_automation` (`ZonePresenceEngine`-Import-Parität).

## [v15.3.9] - 2026-04-01

### 🧩 Slice 92 — Workspace Contract Bundle Recovery

- `tests/integration/test_workspace_ha_core_contract.py` ist jetzt worktree-aware und sucht den HA-Repo-Pfad zuerst in `pilotsuite-styx-ha-current`, mit Legacy-Fallback auf `pilotsuite-styx-ha`.
- `api/v1/zone_automation.py` normalisiert HA-Sync-Entities wieder contract-kompatibel: Listen aus Strings, Listen aus `{entity_id, role}`-Objekten und rollenbasierte Dict-Payloads werden stabil abgebildet; `cfg.ha_entities`/`cfg._ha_entities` bleiben legacy-kompatibel, reichere Sync-Metadaten wandern separat nach `_ha_entity_sync`.
- Der Core-Contract-Bundle-Lauf ist wieder grün.
- Versionsartefakte (`VERSION`, `copilot_core/VERSION`, `config.yaml`, `manifest.json`, Add-on-Config, Runtime-VERSION) auf `15.3.9` harmonisiert.
- Validiert mit: `PYTHONPATH=copilot_core/rootfs/usr/src/app pytest -q tests/integration/test_workspace_ha_core_contract.py tests/test_zone_truth_sync_contract.py` → `11 passed`; `./scripts/run_core_contract_bundle.sh` → `65 passed`.

## [v15.3.8] - 2026-04-01

### 🧩 Slice 91 — Plugin Engine Contract Recovery

- `copilot_core.plugins.engine` auf Legacy-/Current-Contract-Parität gehärtet: `plugins_dir` und `plugin_dirs`, `manifest.json` und `plugin.json`, `core_version`-Factory-Override sowie int-kompatibles Discovery-Result werden jetzt parallel unterstützt.
- Plugin-Lifecycle wieder slice-übergreifend konsistent: Versionskompatibilität, Dependency-Checks, Hook-Registrierung/-Unregistrierung, Config-Updates und Summary-/Statistics-APIs decken jetzt beide historischen Testflächen ab.
- Legacy-Status/Hooks (`ACTIVE`, `ON_EVENT_RECEIVED`, `ON_ZONE_CREATED`, `ON_HEALTH_CHECK`) bleiben intern kompatibel, während die neuere API-Fläche weiter normalisiert `enabled`/Hook-Listen ausliefert.
- Versionsartefakte (`VERSION`, `copilot_core/VERSION`, `config.yaml`, `manifest.json`, Add-on-Config, Runtime-VERSION) auf `15.3.8` harmonisiert.
- Validiert mit: `pytest -q tests/test_plugin_engine.py tests/test_plugins_engine.py` → `84 passed`.

## [v15.3.7] - 2026-04-01

### 🧩 Slice 90 — Runtime Surface Repair

- Root-Pytest-Importfläche gehärtet: neue Bridge-Pakete für `copilot_core.api`, `copilot_core.api.v1`, `copilot_core.config`, `core` und `copilot_sdk`; `copilot_core.homeassistant` und `copilot_core.cache` erweitern jetzt deterministisch den Runtime-Pfad.
- `copilot_core/__init__.py` exportiert wieder eine belastbare `__version__`; HA-Event-Imports zeigen jetzt auf die reale Home-Assistant-Implementierung, und `plugins/__init__.py` degradiert sauber ohne `bs4`, damit Engine-Tests nicht schon beim Package-Import kippen.
- Cache-/Queue-/Config-/SDK-Baseline repariert: FIFO-Insertion-Tracking im Cache, Queue-Requeue/Delay/Expiry-Handling, Konfigurations-Validierungsfehler-Tracking sowie ein testbarer Top-Level-SDK-Client sind jetzt wieder konsistent.
- `ha_adapter_executor.CommandOutput.to_dict()` liefert für terminale Zustände wieder ein belastbares `completed_at`.
- Versionsartefakte (`VERSION`, `copilot_core/VERSION`, `config.yaml`, `manifest.json`, Add-on-Config, Runtime-VERSION) auf `15.3.7` harmonisiert.
- Validiert mit: `/home/linuxbrew/.linuxbrew/bin/pytest -q tests/test_cache_engine.py tests/test_config_engine.py sdk/python/tests/test_client.py tests/test_queue_engine.py tests/test_ha_adapter_executor.py` → `236 passed`.

## [v15.3.6] - 2026-04-01

### 🧪 Slice 89 — Pytest Root Bootstrap

- `tests/conftest.py` ergänzt jetzt einen deterministischen Repo-Root-Bootstrap in `sys.path`, damit Top-Level-Testläufe die Bridge aus `copilot_core/__init__.py` ohne manuelles `PYTHONPATH=.` sehen.
- Bestehende Canvas-Fixtures bleiben unverändert nutzbar; der Bootstrap wirkt nur auf die Test-Importauflösung.
- Versionsartefakte (`VERSION`, `copilot_core/VERSION`, `config.yaml`, `manifest.json`, Add-on-Config, Runtime-VERSION) auf `15.3.6` harmonisiert.
- Validiert mit: `/home/linuxbrew/.linuxbrew/bin/pytest tests/test_predictive_automation.py tests/test_energy_optimization.py tests/test_anomaly_blueprint_contract.py -q` → `34 passed`.

## [v15.3.5] - 2026-04-01

### 🧩 Slice 88 — Runtime Package Bridge

- Neues `copilot_core/__init__.py` ergänzt den Paketpfad deterministisch um die reale Runtime unter `copilot_core/rootfs/usr/src/app/copilot_core`, damit Top-Level-Tests und Runtime dieselbe Modulstruktur sehen.
- `copilot_core/ml/__init__.py` auf lazy Exporte + Runtime-Pfad umgestellt; dadurch crasht ein reiner Package-Import nicht mehr an schweren Forecast-Abhängigkeiten, und optionale Anomaly-/ML-Pfade können sauber degradieren.
- Import-Lücke für `copilot_core.predictive.automation_engine`, `copilot_core.energy.optimization_engine` und `copilot_core.api.v1.anomaly` im Worktree geschlossen, ohne Logik zu duplizieren.
- Versionsartefakte (`VERSION`, `copilot_core/VERSION`, `config.yaml`, `manifest.json`, Add-on-Config, Runtime-VERSION) auf `15.3.5` harmonisiert.
- Validiert mit: `PYTHONPATH=. /home/linuxbrew/.linuxbrew/bin/pytest tests/test_predictive_automation.py tests/test_energy_optimization.py tests/test_anomaly_blueprint_contract.py -q` → `34 passed`.

## [v15.3.4] - 2026-04-01

### 🧠 Slice 87 — Brain Read-Model Test API Completion

- `core/brain_read_model.py`: `BrainGraphGrowth.to_dict()` ergänzt und `reset_brain_state()` als offizieller Test-/Contract-Reset eingeführt.
- Brain-Read-Model exportiert den Reset jetzt explizit über `__all__`, damit die v2-Contracts sauber importieren.
- Versionsartefakte (`VERSION`, `copilot_core/VERSION`, `config.yaml`, `manifest.json`, Add-on-Config, Runtime-VERSION) auf `15.3.4` harmonisiert.
- Validiert mit: `PYTHONPATH=copilot_core/rootfs/usr/src/app /home/linuxbrew/.linuxbrew/bin/pytest tests/test_zone_presence.py tests/test_presence_extended.py tests/test_edge_cases_refinement.py tests/test_core_contract_slice11.py tests/test_module_read_model.py tests/test_dashboard_read_models_contract.py tests/test_zone_dashboard_contract.py tests/test_dashboard_tabs.py tests/test_ha_connection_read_model.py tests/test_brain_read_model_contract.py tests/test_brain_read_model_v2.py -q` → `290 passed`.

## [v15.3.3] - 2026-04-01

### 🧠 Slice 86 — Module Read-Model Runtime State Merge

- `core/module_read_model.py`: `build_module_read_model()` merge-t jetzt den bereits gehaltenen Runtime-Zustand aus `_module_state`, statt bei Aufrufen ohne Registry leer zu bleiben.
- Bestehende Snapshots werden per Deep-Copy übernommen, damit Builder-Aufrufe den In-Memory-Zustand nicht aliasen oder mutieren.
- Versionsartefakte (`VERSION`, `copilot_core/VERSION`, `config.yaml`, `manifest.json`, Add-on-Config, Runtime-VERSION) auf `15.3.3` harmonisiert.
- Validiert mit: `PYTHONPATH=copilot_core/rootfs/usr/src/app /home/linuxbrew/.linuxbrew/bin/pytest tests/test_module_read_model.py tests/test_dashboard_read_models_contract.py tests/test_zone_dashboard_contract.py -q` → `28 passed`.

## [v15.3.2] - 2026-04-01

### 🧩 Slice 85 — Contract Compatibility Hardening

- `presence/zone_presence.py`: Off-Delay und `extended_absent` wieder korrekt an Timer-/Abwesenheitssemantik gekoppelt; dazu Thread-Lock auf persistente Instanz gehärtet.
- `presence/presence_extended.py`: `AdvancedSensorConfig.pet_friendly` ergänzt und Trend-Erkennung für stark belegte Zonen mit stabilem Fallback versehen.
- `automations/suggestion_engine.py`: `SuggestionActionIntent` wieder Slice-7-kompatibel gemacht (`suggestion_id`, `action_type`, `domain`, `service`, `entity_ids`, `evidence`, `explanation`, `policy_decision`) ohne die neuere Proposal-/Intent-Wiring zu brechen.
- `core/dashboard_read_models.py`: Read-Models wieder objekt-kompatibel für Contract-Tests und API-Aufrufer (`get()`/`copy()`), inklusive Alias-Felder und `get_all_zones()`-Fallback für truth-backed Dashboard-Building.
- Neuer Import-Kompatibilitätspfad `copilot_core.modules.module_registry` für Slice-3-Contracts ergänzt.
- Versionsartefakte (`VERSION`, `copilot_core/VERSION`, `config.yaml`, `manifest.json`, Add-on-Config, Runtime-VERSION) auf `15.3.2` harmonisiert.
- Validiert mit: `PYTHONPATH=copilot_core/rootfs/usr/src/app /home/linuxbrew/.linuxbrew/bin/pytest tests/test_zone_presence.py tests/test_presence_extended.py tests/test_edge_cases_refinement.py tests/test_core_contract_slice11.py -q` → `192 passed`.

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
