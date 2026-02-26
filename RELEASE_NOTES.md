# Release Notes - PilotSuite Core

## [10.1.2] - 2026-02-26 — PAIRED RELEASE (HA DOCS COMPLIANCE)

- Paired Release mit HA Integration `v10.1.2` (HA Manifest Best Practice: `single_config_entry`).

## [10.1.1] - 2026-02-26 — VERSION SYNC (ADD-ON VALIDATION)

- Fix: Versionsync zwischen Add-on Metadaten und Runtime wiederhergestellt.
  (`copilot_core/config.yaml`, `copilot_core/manifest.json`, `/usr/src/app/VERSION`)

## [10.1.0] - 2026-02-26 — HARDENING + EVENTBUS BRIDGES

- Stabilitaet: Logikstruktur gehaertet, Bugfixes, EventBus-Bridge-Wiring konsolidiert.

## [10.0.1] - 2026-02-26 — OVERRIDE MODES + MUSIKWOLKE PRESETS

- Neue Override Modes (temporäre manuelle Steuerung, sauberer Status/Sensor-Export).
- Musikwolke: Coordinator-Flows + Presets (z.B. Volume/Light) erweitert.

## [10.0.0] - 2026-02-26 — ZONE AUTOMATION CONTROLLER

- Zone Automation: Presence Engine + Brightness Manager + API als Basis fuer kontextbasierte Automationen.

## [9.0.0] - 2026-02-26 — ARCHITECTURE OVERHAUL + EVENTBUS + ENTITY SEARCH

### Highlights

v9.0.0 is a major architecture overhaul introducing the EventBus communication layer, bidirectional Habitus zone sync, searchable entity dropdowns, and a clean module structure.

### EventBus Architecture
- Central thread-safe pub/sub EventBus for inter-module communication.
- Topics: `zone.*`, `mood.*`, `neuron.*`, `candidate.*`, `graph.*`, `event.*`.
- Wildcard subscriptions (e.g. `zone.*`), bounded history (500 events), metrics tracking.
- REST monitoring: `/api/v1/events/bus/history`, `/api/v1/events/bus/metrics`.

### Habitus Zones API
- Bidirectional HA-Core zone synchronization.
- `POST /api/v1/habitus/zones/sync` — full/delta sync from HA integration.
- `GET/PUT/DELETE /api/v1/habitus/zones/<id>` — CRUD per zone.
- JSON file persistence at `/data/habitus_zones.json`.
- EventBus integration: publishes `zone.synced`, `zone.updated`, `zone.deleted`.

### Entity Search API
- Searchable entity dropdown data for React backend.
- `GET /api/v1/entities/search?q=&domain=&area=&limit=` — fuzzy entity search.
- `GET /api/v1/entities/domains` — domain list with counts and MDI icons.
- `GET /api/v1/entities/by-area` — entities grouped by HA area.
- Cache populated from HA event ingestion pipeline.

### Neural Pipeline Live
- 60-second periodic neuron evaluation via daemon thread.
- Publishes `neuron.evaluated` events with dominant mood + confidence.
- Mood service updates all active zones from neuron results.

### Habitus Learning Loop
- `event.ingested` triggers pattern mining when batch >= 5 events.
- New patterns published as `habitus.pattern` events.

### Brain Graph Context
- Chat conversations now include top 5 entity relationships and active nodes.
- Neuron mood summary and Habitus zone overview injected into LLM context.
- Zone changes create graph nodes; sync publishes `graph.updated`.

### Dashboard
- New EventBus tab in history panel (color-coded by topic type).
- Mood events: purple, Zone events: green, Neuron events: cyan, Candidate events: yellow.

### Cleanup
- Removed ~1700 dead blueprint entries from `core_setup.py`.
- Clean module structure with fault-isolated service init.

### New Files
| File | Purpose |
|------|---------|
| `copilot_core/event_bus.py` | Thread-safe pub/sub EventBus |
| `api/v1/habitus_zones.py` | Habitus Zones CRUD + sync API |
| `api/v1/event_bus_api.py` | EventBus monitoring REST API |
| `api/v1/entity_search.py` | Searchable entity dropdowns |

### Version
- `copilot_core/config.yaml` → `9.0.0`
- `copilot_core/manifest.json` → `9.0.0`
- `VERSION` → `9.0.0`
- Paired with HA Integration `v9.0.0`

### Validation
```bash
cd pilotsuite-styx-core
export PYTHONPATH=$PWD/copilot_core/rootfs/usr/src/app
python3 -m pytest tests/ -v --tb=short -x
python3 -m py_compile copilot_core/rootfs/usr/src/app/copilot_core/core_setup.py
python3 -m py_compile copilot_core/rootfs/usr/src/app/copilot_core/event_bus.py
python3 -m py_compile copilot_core/rootfs/usr/src/app/copilot_core/api/v1/entity_search.py
python3 -m py_compile copilot_core/rootfs/usr/src/app/copilot_core/api/v1/habitus_zones.py
```

## [8.11.0] - 2026-02-25 — SYSTEM OVERVIEW + SENSOR/NEURON LAYER UX

### Added
- New observability endpoints:
  - `GET /api/v1/system/overview`
  - `GET /api/v1/system/sensors`
  - `GET /api/v1/system/zones/summary`
  - `POST /api/v1/system/cache/clear`
- New System page in dashboard with:
  - host resources (CPU/RAM/Disk)
  - service/module connectivity
  - neuron layer + sensor layer summary
  - habitus zone status table.
- New Habitus page card: `Habitus-Zonen Statusuebersicht`.

### Changed
- Settings now includes global health score and resource snapshot from system overview API.
- Header now exposes `UI Reload` for forced frontend refresh without add-on restart.
- System status endpoint now aggregates module dependencies and neuron hints per module.

### Fixed
- `/api/v1/system/modules` now uses registry/catalog data (no invalid `list_modules()` call).

### Validation
- `pytest -q tests/test_system_overview_api.py tests/test_dashboard_template_habitus.py` passed.
- Full regression pass: `66 passed` (dashboard/homekit/bootstrap/dev/main-waitress suites).

## [8.10.0] - 2026-02-25 — HOMEKIT SERVERS + DASHBOARD UX

### Added
- New HomeKit zone-server API with persistent config and QR endpoints.
- Automatic server generation from Habitus zones (zone name + compatible entities).
- Dedicated HomeKit section on the Habitus dashboard:
  - server status/connectivity
  - setup code + pairing QR
  - per-zone config save/enable/disable actions.
- Per-module floating config windows in dashboard:
  - open by clicking module cards
  - draggable and mouse-resizable.

### Changed
- Module config renderer now supports multi-target forms (inline + window instances).
- HomeKit QR endpoints accept query-token fallback for token-protected dashboard image loading.

### Fixed
- Habitus page keeps loading zones/dependencies/HomeKit even when no habit rules are present.

### Validation
- `pytest -q tests/test_homekit_api.py tests/test_dashboard_template_habitus.py` passed.
- `pytest -q tests/test_bootstrap_routes.py tests/test_onyx_bridge_api.py tests/test_module_and_shopping_api.py` passed.

## [8.9.1] - 2026-02-25 — VERSION & INSTALL DOC SYNC

### Changed
- Version line aligned to `8.9.1` in:
  - `copilot_core/config.yaml`
  - `copilot_core/manifest.json`
  - `copilot_core/rootfs/usr/src/app/VERSION`
- Add-on installation documentation updated to match production flow (`:8909`, paired HA/Core release line).

### Improved
- Add-on info screen now documents local + cloud model defaults consistently:
  - local: `qwen3:0.6b`
  - cloud fallback: `qwen3.5:cloud` on `https://ollama.com/v1`
- Troubleshooting notes now include explicit HA restart guidance after HACS/Add-on updates.

## [8.9.0] - 2026-02-25 — MUSIKWOLKE SONOS FLOW + REQUEST HARDENING

### Added
- New media control endpoints for zone-based UX:
  - `GET /api/v1/media/zones/<zone_id>/favorites`
  - `POST /api/v1/media/zones/<zone_id>/play-favorite`
  - `POST /api/v1/media/zones/<zone_id>/play-search`
- Musikwolke start API now accepts:
  - `mode` (`group` or `follow`)
  - `degroup_on_leave`
  - `leader_entity_id`

### Improved
- Musikwolke flow now supports leader-based group join/unjoin and tracks grouped members.
- Proactive zone-entry auto-starts Musikwolke when media is already active in the entered zone.
- Dashboard media section adds one-click controls for:
  - start/stop Musikwolke
  - Sonos favorites/sources
  - manual music search playback.
- Ollama Cloud defaults now use `qwen3.5:cloud` as the add-on default cloud model.
- Haushalt overview uses cached news/warnings fetches to reduce queue depth pressure.
- Waitress defaults updated for bursty dashboard traffic (`threads=16`).

## [8.8.0] - 2026-02-25 — REACT-FIRST HABITUS & MODEL CONTROL

### Added
- `GET /api/v1/hub/habitus/dependencies` for zone→module/neuron dependency mapping.
- `POST /api/v1/agent/models/pull` for one-click offline Ollama model download requests.
- `/api/v1/haushalt/overview` enriched with weather/news/warnings/house status payloads.

### Improved
- Habitus dashboard flow upgraded to selector UX:
  - create/edit/delete zones directly in dashboard
  - no CSV entity text input; room/entity multi-select with auto-prefill
  - dependency panel for module + neuron transparency.
- LLM model control UI:
  - cloud `:cloud` models selectable
  - offline model install status + download/select actions.

### Compatibility
- Ollama cloud model handling now treats `:cloud` IDs as cloud-native.
- Ollama-hosted cloud default model changed to `qwen3.5:cloud`.

## [8.7.1] - 2026-02-25 — STABILITY HOTFIX

### Fixed
- Startup no longer throws duplicate blueprint-name errors for System Health (`system_health`).
- Removed noisy failure path for legacy System Health registration when primary blueprint is already active.

### Improved
- Waitress server now runs with tunable, bounded production defaults to reduce queue-pressure spikes.
- Dashboard Styx auto-refresh now uses lightweight background mode and in-flight locking to prevent request pileups.

### Validation
- Syntax checks passed (`python3 -m py_compile` on changed files).
- New regression tests added for blueprint collision guard and waitress env-config bounds.

## [8.7.0] - 2026-02-25 — RAG + MODULE PRESETS + MODULE KATALOG

### Added
- Vollstaendiges RAG-API fuer Wissensbasis-Upload, Suche, Status und Loeschen (`/api/v1/rag/*`).
- Modul-Preset-API (`/api/v1/modules/presets*`) fuer schnelle Betriebsprofile.
- Modul-Katalog-API (`/api/v1/modules/catalog`) fuer dynamische UI/Backend-Konsistenz.

### Improved
- Dashboard-Settings erweitert um:
  - Modul-Preset-Anwendung per Klick
  - RAG-Status + Dokumentuebersicht
  - Dynamische Modul-Renderlogik aus Backend-Katalog
- Chatkontext nutzt jetzt sowohl semantische Conversation-Memory-Treffer als auch RAG-Dokumenttreffer.

### Fixed
- Service-Wiring in `main.py`: `COPILOT_SERVICES` wird jetzt garantiert gesetzt.
- RAG-Zaehler (`rag_documents`, `rag_chunks`) in `/chat/status` und `/chat/memory` integriert.

### Validation
- Syntax/Import-Validierung via `python3 -m py_compile` fuer alle geaenderten Core-Dateien erfolgreich.

## [8.6.0] - 2026-02-25 — HABITUS MANAGEMENT + NEURON BRAIN

### Added
- Habitus management/bootstrap APIs:
  - `/api/v1/hub/habitus/management/recommendations`
  - `/api/v1/hub/habitus/management/bootstrap_zones`
- Habitus automation APIs:
  - `/api/v1/hub/habitus/automation/suggestions`
  - `/api/v1/hub/habitus/automation/apply`
- New `HabitusAutomationAdvisor` to convert A→B rules into neuron-tagged automation payloads.

### Improved
- Dashboard (`/`) now includes:
  - Neuron Brain mode with module-color encoding
  - Synapse visualization from automations + brain synapses
  - Pulsing activity for modules impacted by active zones
  - Tabbed history views for Live, Events, Logs, and Chat.
- Habitus recommendations and assignment heuristics now include camera entities.

### Stability
- Habitus zone persistence now degrades safely when storage path is not writable (no test pollution, explicit fallback only).

### Testing
- 52 targeted tests passed for habitus management helpers, zone engine, route wiring, and dashboard template regressions.

## [8.5.0] - 2026-02-25 — MODULE CONFIG + ADAPTIVE AUTOMATION

### Added
- Hub config APIs for core runtime policies:
  - `/api/v1/hub/media/config`
  - `/api/v1/hub/light/config`
  - `/api/v1/hub/scenes/config`
- New adaptive endpoints:
  - `/api/v1/hub/light/context`
  - `/api/v1/hub/light/recommendations`
  - `/api/v1/hub/scenes/auto`

### Improved
- Musikwolke: cooldown + max-hop guard + presence-driven follow policy.
- Lichtmodul: kombinierte Zeit/Praesenz-Steuerung mit Innen/Aussen-Helligkeitsverhaeltnis.
- Szenenmodul: konfigurierbare Auto-Aktivierung mit Quiet-Hours und Presence-Guard.
- Dashboard:
  - direkte Modulkonfiguration fuer Media/Light/Scenes
  - dropdown-basierte Media-Zuordnung statt manueller CSV-Workflows
  - no-cache response headers + sichtbarer Dashboard-Build

### Persistence
- Hub policy settings are stored via ModuleRegistry and restored on API access after restart.

### Testing
- 130 targeted tests passed across engine behavior, route wiring, and dashboard template checks.

## [8.4.3] - 2026-02-25 — HABITUS + HINTS COMPATIBILITY ROUND

### Added
- `/api/v1/habitus/status`
- `/api/v1/habitus/rules`
- `/api/v1/habitus/rules/summary`
- `/api/v1/habitus/dashboard_cards/rules`
- `/api/v1/chat/status` alias
- `/api/v1/hints/*` registration

### Fixed
- Suggestion inbox in dashboard no longer receives 404 for rules/hints compatibility paths.
- HA Habitus Miner entity expectations (`status`, `rules/summary`) now align with Core responses.

### Testing
- 43 targeted tests passed (bootstrap, dashboard, module/shopping, core endpoints, tags, MCP)

## [8.4.2] - 2026-02-25 — STARTUP ROUTE RECOVERY

### Changed
- Registered Hub API blueprint (`/api/v1/hub/*`) in main startup flow.
- Added compatibility endpoints in main app:
  - `GET /api/v1/status`
  - `GET /api/v1/capabilities`

### Fixed
- `register_blueprints()` could abort with `UnboundLocalError` due local import shadowing of `system_health_bp` / `energy_bp`.
- Restored downstream routes that were missing because startup registration stopped early:
  - `/api/v1/modules/*`
  - `/api/v1/agent/*`
  - `/chat/status`, `/v1/models`, `/v1/chat/completions`
  - `/api/v1/hub/zones` and related Hub endpoints

### Testing
- `pytest -q tests/test_bootstrap_routes.py` → 2 passed
- `pytest -q tests/test_onyx_bridge_api.py tests/test_module_and_shopping_api.py tests/test_dashboard_template_habitus.py tests/test_core_endpoints.py tests/test_tag_api.py tests/test_mcp_server.py` → 40 passed

## [8.4.1] - 2026-02-25 — STABILITY RECOVERY FOR v8.4 LINE

### Changed
- Restored full `conversation.py` implementation and re-enabled dashboard/chat runtime routes.
- Added app-level registration for OpenAI-compatible `/v1/*` endpoints.
- Added `/ready` endpoint and extended `/version` payload with `name: Styx`.
- Registered tags API blueprint during app startup (`/api/v1/tags`, `/api/v1/assignments`).
- Normalized API prefixes for newly added modules to avoid double-prefix routing.
- Version sync to `8.4.1` in `config.yaml`, runtime `VERSION`, and `manifest.json`.

### Fixed
- Import crash in API blueprint (`weather.bp` missing).
- Multiple dashboard/backend chat regressions from minimal conversation stub.
- Graph snapshot/state endpoints now degrade gracefully on unavailable DB files.
- Legacy compatibility symbols restored in error modules:
  - `ErrorBoundary`, `register_error_handler`
  - `ErrorStatus`, `get_global_status`

### Testing
- Core app test suite: `2025 passed, 1 skipped, 22 subtests passed`
- HA integration suite: `561 passed, 5 skipped`

## [8.1.1] - 2026-02-25 — VERSION SYNC

### Added
- None

### Changed
- Version sync: `config.yaml` and `VERSION` file aligned to `8.1.1`
- Minor version bump to reflect runtime/file consistency

### Fixed
- `config.yaml` version drift (was 7.40.0, now 8.1.1)

### Testing
- Version resolution validated
- Runtime version returns `8.1.1` consistently

## [8.1.0] - 2026-02-25 — MCP PHASE 2: WEB SEARCH + TEST SUITE

### Added
- **MCP Phase 2: Web Search via SearXNG**
  - New MCP tool: `pilotsuite.search_web`
  - Supports query, language, categories, time_range, safesearch, max_results
  - Integration with local SearXNG instance (http://192.168.30.18:4041)
- **Enhanced MCP Test Suite**
  - `test_mcp_web_search_tool_exists` – verifies search_web tool registration
  - `test_mcp_web_search_tool_schema` – validates input schema

### Changed
- MCP_TOOLS extended with web search capability
- VERSION bumped to 8.1.0
- All MCP tools now return structured JSON results

### Fixed
- None

### Testing
- pytest passed: MCP server contract tests
- SearXNG endpoint reachable
- Web search tool schema validated

---

## [7.26.0] - 2026-02-25 — INPUT NUMBER + ZONES + PATTERN APIs

### Added
- `input_number` API: `/api/v1/input_number` GET/POST
- `zones` API: `/api/v1/zones` GET
- `scene_patterns` API: `/api/v1/scenes/patterns` (record, suggest, summary, clear)
- `routine_patterns` API: `/api/v1/routines` (record, predict, typical, summary, clear)
- `push_notifications` API: `/api/v1/notifications` (send, channels, test)

### Changed
- Manifest v7.26.0
- All new APIs registered in blueprint.py

### Fixed
- Push notifications: fixed syntax error in validation

### Testing
- All API files syntax OK (py_compile)
- Blueprint registration validated

---

## [7.8.9] - 2026-02-23 — ERROR ISOLATION + CONNECTION POOLING

### Added
- Module-Crash-Isolation über `ModuleErrorBoundary`
- Connection Pooling für HA-ClientSessions
- Error Dashboard Widget zur Visualisierung

### Changed
- Error handling in `__init__.py` überarbeitet
- Session-Management in `api/__init__.py`

### Fixed
- Haushalts-Error-Kaskaden verhindert
- Resource-Leaks bei HA-Updates

### Testing
- pytest passed: 520 tests
- hassfest: ✅ OK
- local Ollama: ✅ OK
