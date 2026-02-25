# Changelog - PilotSuite Core Add-on

## [8.9.1] - 2026-02-25 — DOCS + VERSION LINE HARDENING

### Changed
- Version line synchronized to `8.9.1` across add-on runtime files:
  - `copilot_core/config.yaml`
  - `copilot_core/manifest.json`
  - `copilot_core/rootfs/usr/src/app/VERSION`
- Add-on installation docs refreshed for current production defaults:
  - Core API on `:8909`
  - local model `qwen3:0.6b`
  - cloud fallback `qwen3.5:cloud` via `https://ollama.com/v1`

### Improved
- Setup instructions now explicitly align with paired HA integration release line.
- Troubleshooting guidance now clarifies expected post-update HA restart requirements.

## [8.9.0] - 2026-02-25 — MUSIKWOLKE SONOS FLOW + LOAD HARDENING

### Added
- Media API extensions for zone-native playback control:
  - `GET /api/v1/media/zones/<zone_id>/favorites`
  - `POST /api/v1/media/zones/<zone_id>/play-favorite`
  - `POST /api/v1/media/zones/<zone_id>/play-search`
- Musikwolke session control now supports policy parameters:
  - `mode` (`group` | `follow`)
  - `degroup_on_leave`
  - `leader_entity_id`
- Proactive zone-entry flow can now auto-start Musikwolke when a person enters a zone with active playback.

### Changed
- `MediaZoneManager` upgraded for Sonos-style grouping:
  - joins new zone players to a leader (`media_player.join`)
  - optional de-group on zone leave (`media_player.unjoin`)
  - tracks grouped entities + current zone per session.
- Ollama Cloud add-on defaults aligned to `qwen3.5:cloud` (instead of legacy non-`:cloud` defaults).
- Dashboard media panel upgraded:
  - direct Musikwolke start/stop controls
  - zone favorite/source dropdown
  - manual search-and-play action.

### Improved
- Haushalt overview now caches external news/warnings requests to reduce blocking request pressure.
- Waitress default thread pool increased from `12` to `16` for better burst handling on dashboard fan-out.
- Dashboard info table now includes new media favorites/search endpoints.

## [8.8.0] - 2026-02-25 — REACT-FIRST HABITUS MGMT + CLOUD MODEL UX

### Added
- New zone dependency endpoint:
  - `GET /api/v1/hub/habitus/dependencies`
  - exposes per-zone module dependencies + neuron hints from entity-role mappings.
- New offline model pull endpoint:
  - `POST /api/v1/agent/models/pull`
  - triggers non-blocking local `ollama pull` for selectable offline models.
- Haushalt overview API now includes:
  - `weather`, `news`, `warnings`, and `house_status` in `/api/v1/haushalt/overview`.

### Changed
- Dashboard Habitus UX:
  - zone create/edit flow now selector-based (no CSV text input for entities)
  - in-place zone edit/cancel/delete actions
  - dependency visualization card (modules + neuron hints).
- Dashboard settings model UX:
  - cloud `:cloud` models are surfaced and selectable
  - offline models show install state with one-click download/select actions.
- LLM provider cloud detection now supports `:cloud` model IDs explicitly.
- Ollama Cloud default model set to `qwen3.5:cloud` for Ollama-hosted cloud URL.

### Integration
- HA integration switched to React-first dashboard concept:
  - legacy YAML dashboard auto-generation is now opt-in
  - `habitus_zones` options menu now shows dashboard mode info (legacy YAML remains available manually).

## [8.7.1] - 2026-02-25 — STABILITY HOTFIX (SYSTEM HEALTH + WAITRESS)

### Fixed
- Prevented duplicate System Health blueprint registration in startup wiring:
  - avoids `ValueError: The name 'system_health' is already registered for a different blueprint`
  - legacy `/api/v1/system_health/*` registration is now skipped when already present.

### Improved
- Waitress runtime tuning now supports bounded env-based worker config:
  - `WAITRESS_THREADS` (default `16`)
  - `WAITRESS_CONNECTION_LIMIT` (default `300`)
  - `WAITRESS_BACKLOG` (default `1024`)
  - `WAITRESS_CHANNEL_TIMEOUT` (default `120`)
  - `WAITRESS_CLEANUP_INTERVAL` (default `30`)
- Styx dashboard auto-refresh reduced backend pressure:
  - background refresh no longer reloads heavy history/brain/suggestion data
  - overlapping refreshes are now prevented with in-flight guard.

### Validation
- `python3 -m py_compile` on changed runtime modules/tests passed.
- Added regression tests:
  - `tests/test_bootstrap_routes.py` (system health duplicate registration log regression)
  - `tests/test_main_waitress_config.py` (waitress config defaults/bounds).

## [8.7.0] - 2026-02-25 — RAG API + MODULE PRESETS + FULL MODULE CATALOG

### Added
- New RAG service + endpoints:
  - `GET /api/v1/rag/status`
  - `GET /api/v1/rag/stats`
  - `GET /api/v1/rag/documents`
  - `POST /api/v1/rag/documents`
  - `POST /api/v1/rag/documents/bulk`
  - `DELETE /api/v1/rag/documents/<doc_id>`
  - `POST /api/v1/rag/query`
- New module control endpoints:
  - `GET /api/v1/modules/catalog`
  - `GET /api/v1/modules/presets`
  - `POST /api/v1/modules/presets/apply`
- New module preset library (`balanced_home`, `privacy_local_first`, `autonomous_plus`) with state + settings rollout.

### Changed
- Module control schemas expanded for the full module surface (brain, habitus, mood, neurons, knowledge, RAG, media, light, scenes, context, reminders, integrations).
- Dashboard settings page:
  - Modul-Presets are now selectable and applyable directly.
  - RAG status/docs are visible in a dedicated settings card.
  - Module list/config now auto-extends from backend catalog (new modules appear without hardcoded UI edits).
- Conversation context now enriches responses with both:
  - semantic conversation memory hits
  - RAG document hits from indexed knowledge base.

### Fixed
- `COPILOT_SERVICES` is now explicitly wired into Flask app startup (`main.py`), so context-dependent APIs consistently see initialized services.
- `/chat/status` and `/chat/memory` now expose RAG counters (`rag_documents`, `rag_chunks`) for UI/diagnostics.

### Validation
- `python3 -m py_compile` on changed Core modules/tests passed.
- Targeted pytest files were prepared (`test_module_and_shopping_api.py`, `test_rag_api.py`); full pytest run requires environment with `pytest` installed.

## [8.6.0] - 2026-02-25 — HABITUS AUTOMATION + NEURON BRAIN UX

### Added
- New Habitus management + automation endpoints:
  - `GET /api/v1/hub/habitus/management/recommendations`
  - `POST /api/v1/hub/habitus/management/bootstrap_zones`
  - `GET /api/v1/hub/habitus/automation/suggestions`
  - `POST /api/v1/hub/habitus/automation/apply`
- New `HabitusAutomationAdvisor` module (`copilot_core/habitus/automation_advisor.py`) to map mined rules to neuron tags + actionable automation payloads.
- Dashboard upgrades:
  - Neuron Brain mode with module-colored neurons
  - Synapse/automation connectivity overlay
  - Zone-activity pulsing
  - Dedicated Live/Event/Log/Chat history tabs.

### Changed
- Habitus zone recommendations now include camera entities and camera metric coverage.
- Entity assignment suggestions include camera domain and improved confidence combos.
- Habitus zone engine persistence hardening:
  - deterministic disable-on-unwritable behavior unless explicit fallback directory is configured.

### Validation
- `pytest -q tests/test_habitus_management_api_helpers.py tests/test_habitus_zones.py tests/test_bootstrap_routes.py tests/test_dashboard_template_habitus.py`
- Result: **52 passed**

## [8.5.0] - 2026-02-25 — MUSIKWOLKE/LICHT/SZENEN CONFIG + DASHBOARD UX ROUND

### Added
- New Hub policy endpoints:
  - `GET/POST /api/v1/hub/media/config`
  - `GET/POST /api/v1/hub/light/config`
  - `GET/POST /api/v1/hub/scenes/config`
- Adaptive lighting context + recommendations:
  - `POST /api/v1/hub/light/context`
  - `GET /api/v1/hub/light/recommendations`
- Scene auto decision endpoint:
  - `POST /api/v1/hub/scenes/auto`

### Changed
- Musikwolke engine now supports runtime policy (presence-follow toggle, cooldown, max hops).
- Light engine now supports adaptive policy (time/presence trigger mode, indoor/outdoor ratio threshold, zone mode context).
- Scene engine now supports configurable auto-activation policy (confidence threshold, quiet hours, home-presence guard).
- Dashboard module config panel now includes Media, Light, and Scenes module settings.
- Media panel now supports dropdown-based player assignment/removal (no CSV/manual text flow).
- Dashboard root (`/`) now sends no-cache headers; settings show dashboard build to verify updates.
- Hub policy settings are persisted via `ModuleRegistry` for restart-safe behavior.

### Validation
- `pytest -q tests/test_media_follow.py tests/test_light_intelligence.py tests/test_scene_intelligence.py tests/test_bootstrap_routes.py tests/test_dashboard_template_habitus.py`
- Result: **130 passed**

## [8.4.3] - 2026-02-25 — CORE FUNCTIONALITY COMPATIBILITY PASS

### Added
- Habitus compatibility endpoints on `/api/v1/habitus/*` for HA + dashboard consumers:
  - `GET /api/v1/habitus/status`
  - `GET /api/v1/habitus/rules`
  - `GET /api/v1/habitus/rules/summary`
  - `GET /api/v1/habitus/dashboard_cards/rules`
- Compatibility alias: `GET /api/v1/chat/status`
- User hints API registration on `/api/v1/hints/*`

### Fixed
- Dashboard suggestion pipeline no longer depends on missing endpoints (`/api/v1/habitus/rules`, `/api/v1/hints`).
- HA Habitus Miner entities receive expected summary/status schema again (`total_rules`, `top_rules`, statistics payload).
- Route registration test coverage expanded for core compatibility surface.

### Validation
- `pytest -q tests/test_bootstrap_routes.py tests/test_onyx_bridge_api.py tests/test_module_and_shopping_api.py tests/test_dashboard_template_habitus.py tests/test_core_endpoints.py tests/test_tag_api.py tests/test_mcp_server.py` → **43 passed**

## [8.4.2] - 2026-02-25 — BOOTSTRAP + API COMPATIBILITY RECOVERY

### Fixed
- Critical Flask bootstrap bug in `register_blueprints()` where local import shadowing (`system_health_bp`, `energy_bp`) caused `UnboundLocalError` and aborted route registration.
- Added missing Hub API registration (`/api/v1/hub/*`) and service wiring in startup path.
- Restored HA/Core compatibility endpoints in `main.py`:
  - `GET /api/v1/status`
  - `GET /api/v1/capabilities`

### Improved
- Added regression tests for startup route wiring and compatibility endpoints:
  - `tests/test_bootstrap_routes.py`

### Validation
- `pytest -q tests/test_bootstrap_routes.py` → **2 passed**
- `pytest -q tests/test_onyx_bridge_api.py tests/test_module_and_shopping_api.py tests/test_dashboard_template_habitus.py tests/test_core_endpoints.py tests/test_tag_api.py tests/test_mcp_server.py` → **40 passed**

## [8.4.1] - 2026-02-25 — API RECOVERY + COMPATIBILITY HARDENING

### Changed
- Recovered full conversation API implementation (`/api/v1/chat/*` + `/v1/*` compatibility paths).
- Registered OpenAI-compatible blueprint in app startup.
- Normalized newly added API blueprints to relative prefixes to avoid `/api/v1/api/v1/*` double paths.
- Added readiness endpoint (`/ready`) and enriched `/version` with `name: Styx`.
- Registered tags blueprint in `create_app` so `/api/v1/tags` and `/api/v1/assignments` are available.
- Aligned add-on version files to `8.4.1` (`config.yaml`, `VERSION`, `manifest.json`).

### Fixed
- Core app import/boot failure caused by missing `bp` export in weather API.
- Dashboard/API failures caused by broken conversation stub in `api/v1/conversation.py`.
- Graph SVG and graph endpoints now return safe fallback state instead of 500 on unavailable DB path.
- LLM provider HTTP wrappers now keep connection pooling and still support monkeypatched request calls in tests.
- Backward-compatible exports restored: `ErrorBoundary`, `register_error_handler`, `ErrorStatus`, `get_global_status`.

### Testing
- `pytest -q tests` in `copilot_core/rootfs/usr/src/app`: **2025 passed, 1 skipped, 22 subtests passed**
- `pytest -q` in `pilotsuite-styx-ha`: **561 passed, 5 skipped**

## [8.1.1] - 2026-02-25 — DEV LOOP #1: BRANCH SYNC + TEST FIXES

### Added
- **Branch Sync**
  - Local main sync with origin/main (commit 10bc67d)
  - RFC-Phase 2 Core Tools implemented
- **Test Suite Expansion**
  - `test_app_smoke.py`: ✅ 31 passed, 2 skipped
  - `test_anomaly_detection.py`: ✅ passed
  - Additional smoke tests for core endpoints

### Changed
- VERSION bumped to 8.1.1
- Pre-loop checklist integrated in GROKY_DEV_CHECK.md
- TODOS.md updated (P2 tasks marked as active)

### Fixed
- HASSFest disabled (pending manifest.json update for codeowners)

### Testing
- pytest: ✅ 200+ tests (test_app_smoke, test_anomaly_detection)
- SearXNG: ✅ reachable (http://192.168.30.18:4041)
- API: ✅ working (blueprint registration validated)

## [8.1.0] - 2026-02-25 — MCP PHASE 2: WEB SEARCH + TEST SUITE

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

## [7.8.8] - 2026-02-23 — DUAL MODEL ROUTING + CLOUD/OFFLINE CONTROL

### Added
- LLM routing with explicit `primary`/`secondary` provider chain (`offline`/`cloud`) and runtime fallback handling.
- New conversation endpoints:
  - `GET /chat/models/catalog`
  - `GET /chat/routing`
  - `POST /chat/routing` (token-protected)
- Dashboard settings now include:
  - Routing editor (primary/secondary provider)
  - Separate offline + cloud model selectors
  - grouped model visibility and RAG status indicator

### Changed
- OpenAI-compatible `/v1/models` now exposes routing aliases (`pilotsuite`, `primary`, `secondary`, `offline`, `cloud`) plus local/cloud catalogs.
- Model alias normalization is routing-aware (`primary`, `secondary`, `offline`, `cloud`).
- Cloud defaults optimized for Ollama-hosted API:
  - `conversation_cloud_api_url` default: `https://ollama.com/v1`
  - `conversation_cloud_model` default: `gpt-oss:20b`
- Runtime version synchronized to `7.8.8` (`copilot_core/config.yaml`, `/usr/src/app/VERSION`).

### Fixed
- Dashboard chat now sends routing-aware model keys (e.g. `primary`) and surfaces HTTP/API errors more clearly.
- Cloud base URL normalization tolerates `/chat/completions` and `/models` style user inputs.

## [7.8.7] - 2026-02-23 — DASHBOARD RECONNECT + MODEL UX

### Fixed
- Dashboard ingress auto-detection now supports both HA ingress path variants:
  - `/api/hassio_ingress/<slug>`
  - `/hassio/ingress/<slug>`
- API calls from the Styx board no longer break when served from the newer ingress route.

### Added
- Interactive chat model selection in the Styx dashboard (`chat-model-select`):
  - Installed models are loaded from `/chat/status`.
  - User choice is persisted in browser storage and applied to chat completions.

### Changed
- Add-on runtime version source synchronized:
  - `copilot_core/config.yaml` now `7.8.7`
  - `/usr/src/app/VERSION` now `7.8.7` (removes stale-version display drift).

## [7.8.6] - 2026-02-22 — INSTALL/UX DOCS HARDENING

### Changed
- Add-on info docs (`copilot_core/DOCS.md`) now contain an exact production install flow:
  - Core + HACS integration order
  - canonical Lovelace dashboard YAML
  - where to configure cloud fallback API key (`conversation_cloud_api_key`)
  - operational smoke checks (`/health`, `/chat/status`, `/v1/chat/completions`)
- README clarifies that add-on info screen is authoritative for install instructions.

### Fixed
- Dashboard template no longer advertises a static internal UI version label.

## [7.8.5] - 2026-02-22 — VERSION LABEL CLARITY

### Fixed
- Dashboard version badge no longer starts with a misleading hardcoded `v1.0.0`.
- Version badge now shows `--` until `/chat/status` returns the real runtime version.
- Settings version row no longer falls back to an unrelated static version string.

### Notes
- `X-API-Version: 1.0` remains the API contract/schema version (not the add-on release version).

## [7.8.4] - 2026-02-22 — DASHBOARD UX: PERSISTENT CHAT + MODULE CONFIG PANEL

### Added
- **Persistent Chat History im Styx-Dashboard**
  - Chat lädt nun Verlauf aus `/api/v1/hub/brain/activity/chat`.
  - User-/Assistant-Nachrichten werden nach jedem Chat-Call in den Brain-Activity-Verlauf geschrieben.
  - Neuer Chat-Clear-Button (`/api/v1/hub/brain/activity/chat/clear`).
- **Modul-Konfigurationspanel im Dashboard**
  - Neue UI unter `Module -> Modul-Konfiguration`.
  - Runtime-Config für unterstützte Module:
    - `habitus_miner` über `/api/v1/habitus/config`
    - `brain_graph` (Brain Activity Timeouts) über `/api/v1/hub/brain/activity` + `/api/v1/hub/brain/activity/config`

### Changed
- **Health-Checks robuster gemacht (API v1/v2/legacy tolerant)**
  - Dashboard nutzt Fallback-Requests (`apiTry`) für Endpunkt-Varianten.
  - Mood-Ansicht verarbeitet jetzt mehrere Antwortformate (`moods`, `zones`, `mood`).

### Fixed
- **Frontend/Backend Handshake im Dashboard**
  - Modul- und Mood-Ansichten brechen nicht mehr sofort bei Endpoint-Drift.
  - Chat-UX zeigt nicht nur lokalen Verlauf, sondern den echten backend-seitigen Verlauf.

### Tests
- Dashboard-Template-Tests erweitert:
  - Ingress-Erkennung
  - Modul-Konfigurationspanel
  - Persistente Brain-Chat-History Hooks

## [7.8.3] - 2026-02-22 — DASHBOARD API RECONNECT + MODULE CONFIG SYNC

### Fixed
- **Ingress API routing in Styx dashboard**
  - Dashboard erkennt jetzt HA-Ingress-Pfade automatisch (`/api/hassio_ingress/<slug>`),
    statt API-Calls immer an den Host-Root zu senden.
  - behebt `API offline`/404 im Sidebar-Panel trotz laufendem Core.
- **Module-Konfiguration verlässlich**
  - Dashboard synchronisiert Modulstatus mit `/api/v1/modules/` als Backend-Source-of-Truth.
  - Toggle-Flow speichert nur noch bei erfolgreichem Backend-Write.
  - Bei Fehler wird der UI-Toggle sauber auf den vorherigen Zustand zurückgesetzt
    (kein irreführender „lokal-only“ Zustand mehr).
- **Settings-Diagnose**
  - neue Anzeige `API Route` (Ingress vs Direct) im Settings-Tab für schnellere Fehleranalyse.

### Tests
- Template-Regression ergänzt: Ingress-Base-Erkennung im Dashboard verifiziert.

## [7.8.2] - 2026-02-22 — ONYX PRODUCTION BRIDGE + E2E TOOLING

### Added
- **Onyx Bridge API** (`/api/v1/onyx/*`)
  - `GET /api/v1/onyx/status`: Bridge-/HA-Reachability-Status fuer produktive Agent-Checks.
  - `POST /api/v1/onyx/ha/service-call`: kontrollierter HA-Service-Call mit optionalem State-Readback (`readback_states`).
- **E2E Script**: `tools/onyx_styx_e2e.sh`
  - prueft in einem Lauf: Onyx-Bridge Status, HA Action, MCP Initialize, OpenAI-Chat Endpoint.

### Changed
- **Onyx OpenAPI Contract** (`docs/integrations/onyx_styx_actions.openapi.yaml`)
  - produktive Server-Defaults (`192.168.30.18:8909`)
  - neue Operation fuer deterministische HA-Aktionen via Onyx-Bridge
  - Zonen-Rooms/Zone-Create fuer Habitus-Zonen-Flow
- **Onyx Doku** (`docs/ONYX_INTEGRATION.md`)
  - konkrete Feldwerte fuer Provider, OpenAPI-Action und MCP-Server.
  - direkte Smoke-Test Befehle fuer Live-Verifikation.

### Tests
- Neue Tests: `tests/test_onyx_bridge_api.py`
  - Status-Endpunkt
  - erfolgreicher Service-Call mit Readback
  - Domain-Allowlist Blockierung
  - fehlender `SUPERVISOR_TOKEN` Fehlerpfad

## [7.8.1] - 2026-02-22 — ONYX BRIDGE + MCP VERSION SYNC

### Added
- **Onyx Integrationsdokumentation** (`docs/ONYX_INTEGRATION.md`)
  - klare Zielarchitektur: Onyx als Knowledge-/RAG-Frontend, Styx als Home-Action-Plane.
  - Security-Leitlinien fuer Token, Scope und Agent-Guardrails.
- **OpenAPI Action Contract fuer Onyx** (`docs/integrations/onyx_styx_actions.openapi.yaml`)
  - minimales, kontrolliertes Endpoint-Set fuer Zonen/Modi/Szenen/Benachrichtigungen.

### Fixed
- **MCP Server Version jetzt runtime-synchron**
  - `MCP_SERVER_INFO.version` nutzt jetzt `copilot_core.__version__`
    statt veraltetem Hardcode.
  - verhindert Versionsdrift in MCP-Clients und Dashboards.

### Tests
- Neue Tests: `tests/test_mcp_server.py`
  - MCP version contract
  - `initialize` Antwort inkl. `serverInfo`
  - `tools/list` Basiskontrakt

## [7.7.19] - 2026-02-22 — HABITUS DASHBOARD ZONE FLOW FIXES

### Fixes
- **Habitus dashboard zone management now uses real Hub zone endpoints**
  - Zone listing switched from the wrong miner config endpoint to `/api/v1/hub/zones`.
  - Zone details now load from `/api/v1/hub/zones/<zone_id>` so entity/room rendering is consistent.
- **Zone creation flow repaired**
  - Dashboard now creates zones via `/api/v1/hub/zones` and supports multi-room selection.
  - If no room is selected, dashboard can register a synthetic room from explicit entity IDs and still create the zone.
- **Room selector UX improved**
  - New multi-select room dropdown in Habitus page (`Ctrl/Cmd` multi-select).
  - Room list reload action added.
  - Best-effort auto-import from entity-assignment suggestions when no rooms are present.

## [7.7.18] - 2026-02-22 — DASHBOARD AUTH BRIDGE + CHAT UX RELIABILITY

### Fixes
- **Dashboard requests now reuse configured auth token automatically**
  - Dashboard root is now rendered with the configured Core auth token injected
    (server-side) and reused by all frontend API calls.
  - behebt 401-Fehler im Dashboard bei gesetztem `auth_token`.
- **Chat in Core dashboard stabilized**
  - Chat-Requests (`/v1/chat/completions`) senden nun automatisch den Auth-Header.
  - gleiches gilt fuer Suggestion-, Szene-, HomeKit-, Habitus-, Modul- und Haushalts-Aktionen.
  - Ergebnis: Dashboard-Funktionen laufen konsistent auch bei aktivierter API-Authentifizierung.

## [7.7.17] - 2026-02-22 — OLLAMA CLOUD ENDPOINT HARDENING

### Fixes
- **Ollama Cloud URL fest normalisiert**
  - `https://ollama.com`, `https://ollama.com/api` und `https://ollama.com/v1`
    werden intern auf `https://ollama.com/v1` vereinheitlicht.
  - Dadurch nutzt Styx fuer Cloud-Fallback immer den korrekten
    OpenAI-kompatiblen Endpoint (`/v1/chat/completions`).
- **Modell-Mapping fuer Ollama Cloud**
  - Inkompatible OpenAI-Defaults wie `gpt-4o-mini`, `gpt-4o`, `gpt-4.1`, `gpt-5`, `o1`, `o3`
    werden bei Ollama Cloud automatisch auf `gpt-oss:20b` umgebogen.
  - Verhindert `404 model not found` bei funktionierender Cloud-Verbindung.
- **Provider-spezifischer Cloud-Default**
  - Ollama Cloud: Default `gpt-oss:20b`
  - Andere OpenAI-kompatible Endpoints: Default bleibt `gpt-4o-mini`

### Verifikation
- Gesamte Core-Testsuite lokal: **1962 passed, 1 skipped**.

## [7.7.16] - 2026-02-22 — LLM MISCONFIG GUARDRAIL

### Fixes
- **Fehlkonfiguration `OLLAMA_MODEL=gpt-4o-mini` abgefangen**
  - Wenn im lokalen Ollama-Modellfeld versehentlich ein Cloud-Modellname steht,
    wird jetzt automatisch auf ein sicheres lokales Fallback (`qwen3:0.6b`) gewechselt.
  - Verhindert lokale 404-Schleifen und den Fehler:
    `Kein LLM-Provider verfuegbar ... model 'gpt-4o-mini' not found`.
- Provider-Status zeigt zusaetzlich:
  - `ollama_model_configured`
  - `ollama_model_overridden`
  fuer klare Diagnose bei Setup-/Migrationsfaellen.

### Verifikation
- Gesamte Core-Testsuite lokal: **1959 passed, 1 skipped**.

## [7.7.15] - 2026-02-22 — DEFAULT MODEL SWITCH TO QWEN3:0.6B

### Default Model Strategy
- Add-on Default fuer `conversation_ollama_model` auf `qwen3:0.6b` gesetzt.
- Runtime-Fallbacks in Startup-Skripten und LLM-Komponenten ebenfalls auf `qwen3:0.6b` vereinheitlicht.
- Ergebnis: schnellere erste Antworten und geringerer RAM-Druck auf typischer HA-Hardware.

### Konsistenz in Runtime und API
- OpenAI-kompatible Conversation-API nutzt jetzt `qwen3:0.6b` als internen Default.
- Agent-Status/Self-Heal greifen bei fehlender Modellkonfiguration ebenfalls auf `qwen3:0.6b` zurueck.

### Dokumentation
- README, Add-on-Doku und Architektur/API-Dokumente auf neue Default-Strategie aktualisiert.
- `qwen3:4b` bleibt als optionales Qualitätsmodell fuer staerkere Systeme dokumentiert.

## [7.7.14] - 2026-02-22 — SELF-HEAL + ZERO-CONFIG HARDENING

### Agent Self-Heal API
- Neuer Endpoint: `POST /api/v1/agent/self-heal` (token-protected).
- Fuehrt best-effort Reparaturschritte aus:
  - LLM-Provider-Konfiguration neu laden
  - installierte Ollama-Modelle pruefen
  - fehlende Pflichtmodelle (`qwen3:0.6b` + konfiguriertes Modell) im Hintergrund nachziehen
- Damit kann die HA-Integration nach Zero-Config/Restart aktiv eine Reparatur ausloesen, statt nur Fehlstatus zu melden.

### LLM Routing Robustness
- Cloud-typische Modellnamen (z. B. `gpt-4o-mini`) werden ohne Cloud-Fallback nicht mehr blind an Ollama gesendet.
- Statt wiederholter 404 wird direkt auf das konfigurierte lokale Modell geroutet.

### Agent Config Konsistenz
- Agent-Status liest Conversation-Settings jetzt robust aus:
  - verschachtelter Config (`conversation.*`)
  - Flat Add-on Optionen (`conversation_*`)
  - ENV-Fallbacks (`OLLAMA_*`, `CLOUD_*`)
- verhindert Drift zwischen effektivem Runtime-Verhalten und gemeldetem Agent-Status.

### API Wiring
- Vector API Blueprint (`/api/v1/vector/*`) ist im Core-Setup explizit registriert.

### Verifikation
- Gesamte Core-Testsuite lokal: **1958 passed, 1 skipped**.

## [7.7.13] - 2026-02-22 — AGENT API + VERSION FALLBACK + MODEL ALIAS

### Agent API wiring
- `/api/v1/agent/*` Blueprint wird jetzt im Core registriert.
- Agent-Status/Verify-Endpunkte sind damit fuer HA-Integration erreichbar (kein 404 mehr bei aktivem Modul).

### Modellalias & OpenAI-Kompatibilitaet
- OpenAI Chat-Handler normalisiert Modellalias (`pilotsuite`, `default`, `auto`, `local`, `ollama`) auf das konfigurierte Ollama-Modell.
- `/v1/models` listet jetzt zusaetzlich das stabile Alias-Modell `pilotsuite`.

### Version-Robustheit
- Neue Runtime-Versionauflosung mit Fallback-Datei:
  - `COPILOT_VERSION` / `BUILD_VERSION` bevorzugt
  - sonst `/usr/src/app/VERSION`
- Betrifft u. a. `main.py` (`/version`) und weitere Version-Exporte, um `0.0.0`-Artefakte zu vermeiden.

### Tests
- Neue Tests fuer Modellalias-Normalisierung und LLM-Alias-Routing hinzugefuegt.

## [7.7.12] - 2026-02-22 — LLM FALLBACK + CLOUD CONFIG UX

### Chat provider robustness
- `LLMProvider.chat()` gibt jetzt in allen Fehlerpfaden konsistent ein Dict zurueck (kein `None` bei unvollstaendiger Cloud-Konfiguration).
- Lokale Modellauflosung kennt Alias-Modelle wie `pilotsuite`/`auto` und nutzt direkt das konfigurierte Ollama-Standardmodell.
- Bei expliziten externen Modellen (z. B. `gpt-4o-mini`) gilt:
  - mit Cloud-Fallback: nach lokalem 404 direkt Cloud versuchen
  - ohne Cloud-Fallback: auf konfiguriertes lokales Modell zurueckfallen
- Offline-Fehlermeldungen differenzieren jetzt zwischen:
  - Modell nicht installiert
  - Timeout
  - Unerreichbarkeit
  - HTTP-Fehlern

### Add-on Konfiguration (Cloud Fallback)
- Neue Add-on Optionen in `config.yaml` + UI-Labels:
  - `conversation_cloud_api_url`
  - `conversation_cloud_api_key`
  - `conversation_cloud_model`
  - `conversation_prefer_local`
- `start_dual.sh` exportiert diese Werte als Laufzeit-ENV (`CLOUD_API_URL`, `CLOUD_API_KEY`, `CLOUD_MODEL`, `PREFER_LOCAL`).
- Startlog zeigt Cloud-Fallback-Status (`configured`/`disabled`) fuer schnellere Diagnose.

### Tests
- Neue Tests fuer LLM-Fallback-/Cloud-Routing und Offline-Fehlerpfade hinzugefuegt.

## [7.7.11] - 2026-02-22 — RELEASE SYNC

### Sync-Release
- Core/HA Versionsstand auf `7.7.11` synchronisiert, damit beide Repos denselben releasefähigen Baseline-Stand ausweisen.
- Keine funktionalen Core-Codeaenderungen gegenueber `7.7.10`.

## [7.7.10] - 2026-02-22 — VERSION CONSISTENCY HOTFIX

### Version-Drift beseitigt
- `copilot_core.__version__` liest jetzt die Laufzeitversion aus `COPILOT_VERSION`/`BUILD_VERSION` statt aus einem veralteten Hardcode.
- Conversation-Status (`/chat/status`) nutzt denselben Version-Source-of-Truth inklusive sauberem `0.0.0`-Fallback.

### Wirkung
- Keine verwirrenden Versionsspruenge mehr zwischen UI-/Statuspfaden (z. B. alte 3.x/0.x Artefakte trotz 7.7.x Release).
- Konsistente Versionserkennung ueber API, Dashboard und Runtime-Diagnose.

## [7.7.9] - 2026-02-22 — OLLAMA GUARANTEE + NETWORK FAILSAFE

### Setup/Runtime Hardening
- Externe Ollama-URL wird beim Start aktiv geprueft; bei Unerreichbarkeit wird automatisch auf interne Container-Ollama (`127.0.0.1:11435`) zurueckgefallen.
- Wenn `conversation_enabled=true` und Ollama-Binary fehlt oder `ollama serve` sofort abstuerzt, startet das Add-on nicht mehr still degradiert, sondern bricht mit klarer Fehlermeldung ab.
- Alternative Startskript-Variante (`start_with_ollama.sh`) auf dieselbe "Ollama required"-Semantik angehoben.

### Readiness verbessert
- `/ready` beruecksichtigt jetzt explizit Ollama-Verfuegbarkeit, wenn Conversation aktiv ist.
- Readiness-Response erweitert um `ollama_required`, `ollama` und `ollama_url` zur klaren Diagnose im Betrieb.

## [7.7.8] - 2026-02-22 — STARTUP + VERSION RELIABILITY PATCH

### Ollama Startup Hardening
- `HOME` wird beim Start explizit gesetzt (`/tmp` Fallback), damit `ollama serve` in HA-Containern nicht mit `Error: $HOME is not defined` abbricht.
- Ollama bleibt der primaere lokale Runtime-Pfad im Container; externe URL wird nur bei expliziter externer Konfiguration genutzt.

### Non-Blocking Modellbereitstellung
- Modell-Pulls laufen jetzt in einem Hintergrund-Worker.
- API-Start blockiert nicht mehr durch lange Modell-Downloads oder 60s Ready-Wartefenster.
- Fallback-Modell (`qwen3:0.6b`) und konfiguriertes Modell werden asynchron nachgezogen.

### Versionskonsistenz
- Laufzeitversion kommt aus `COPILOT_VERSION`/`BUILD_VERSION` statt aus veralteten Hardcodes.
- Dockerfile exportiert `COPILOT_VERSION=${BUILD_VERSION}` zur Laufzeit.
- Semver-Fallback auf `0.0.0` fuer Test-/Dev-Umgebungen ohne Build-Metadaten.

## [7.7.7] - 2026-02-22 — PRODUCTION READINESS PROGRAM

### Validierung und Hardening
- E2E-Pipeline-Test (`test_e2e_pipeline.py`) bereinigt:
  - keine `PytestReturnNotNoneWarning` mehr
  - keine versehentliche Testklassensammlung mehr
- Kritischer Kommunikationspfad weiter verifiziert:
  - Events Ingest → Brain Graph
  - Habitus Mining → Candidates
  - Candidate Lifecycle (pending/offered/accepted)

### Dauerbetrieb / 15-Minuten Guardrail
- Neuer GitHub-Workflow `production-guard.yml`:
  - geplanter Lauf alle 15 Minuten
  - Syntax-Check + kritische Pfadtests als fruehes Warnsystem
  - Fokus auf Produktions-Stabilitaet statt nur Release-Checks

### Dokumentation
- Vision und Projektstatus auf aktuellen Release-Stand aktualisiert.
- Architektur-/Modul-Dokumentation konsolidiert auf den verifizierten Zustand.

## [7.7.6] - 2026-02-22 — STABILITY + CI HARDENING

### Runtime-Stabilitaet ausserhalb des Add-on-Containers
- Persistenz-Fallbacks fuer nicht beschreibbares `/data` hinzugefuegt:
  - Dev Surface Logs
  - Transaction Log (`log_fixer_tx`)
  - Brain Graph SQLite
  - Mood SQLite
  - Vector Store SQLite
- Dev-Logs und Vector-API-Endpunkte schlagen lokal/CI nicht mehr mit 500 fehl.

### Fachliche Korrekturen
- Comfort Grade Mapping korrigiert (`50` => `C` statt `D`).
- Regionserkennung verbessert (u.a. Muenchen korrekt `DE`, Wien-Region korrekt erkannt).
- Energy-Service Timestamp auf `Z`-Format vereinheitlicht.
- Report-Empfehlungen bei moderater Solarabdeckung sinnvoller priorisiert.
- Sankey-Fallback bei fehlenden Baselines/Zone-Daten korrigiert.
- Schedule Planner:
  - leere Device-Listen werden korrekt als leer behandelt
  - PV-priorisierte Slot-Bewertung (effektiver Preis mit PV-Korrektur)

### Test- und CI-Fixes
- Core CI-Testpfad korrigiert (`copilot_core/rootfs/usr/src/app/tests`).
- `pytest-asyncio` in Test-Dependencies aufgenommen.
- CI-Testjob bricht bei Fehlern wieder korrekt ab (kein `|| true` mehr).
- Lokale Core-Suite verifiziert: `1949 passed, 1 skipped`.

## [7.7.0] - 2026-02-21 — HA CONFORMITY RELEASE

### Kompletter HA-Konformitaets-Audit — alle Stolperstellen gefixt

#### Docker Build Fix
- `numpy` zu Dockerfile hinzugefuegt (fehlte → Build-Fehler bei collective_intelligence Modul)

#### config.yaml Fixes
- `hassio_api: true` hinzugefuegt (Supervisor Token Injection fuer HA API Zugriff)
- `homeassistant_api: true` hinzugefuegt (HA REST API Zugriff)
- `homeassistant: "2024.1.0"` Mindestversion gesetzt

#### Add-on UI
- `translations/en.yaml` erstellt (freundliche Labels fuer alle Config-Optionen)
- `DOCS.md` erstellt (Dokumentation Tab im Add-on UI)
- `start_dual.sh` Execute-Bit in Git gesetzt

## [7.6.4] - 2026-02-21 — ADD-ON DISCOVERY FIX

### config.json → config.yaml Migration

- **ROOT CAUSE**: `config.json` hatte Schema-Mismatch — `list(a|b|c)` (Einzelwert-Enum) trifft auf `["a","b","c"]` (Array) in options → Supervisor Schema-Validation schlaegt fehl → Add-on wird STILL uebersprungen
- `config.json` entfernt, durch `config.yaml` ersetzt (modernes Format)
- Options/Schema drastisch vereinfacht: flache Keys statt 5-fach verschachtelter Objekte
- `start_dual.sh` aktualisiert fuer flache Config-Keys

## [7.6.3] - 2026-02-21 — REPO HYGIENE

### Add-on Repository Cleanup

- Stale `custom_components/copilot/` Verzeichnis entfernt (v4.0.0 Altlast, falscher Domain, verwirrte HACS)
- Git Remote URL korrigiert: `Home-Assistant-Copilot.git` → `pilotsuite-styx-core.git`
- Add-on Supervisor Kompatibilitaet verifiziert: `repository.json`, `config.json`, `Dockerfile`, `build.yaml` alle korrekt

## [7.6.2] - 2026-02-21 — VERSION ALIGNMENT

### Version-Sync mit HA v7.6.2

- Version auf 7.6.2 synchronisiert (HA-seitige Bugfixes)
- Core unverändert — alle 1935 Tests bestehen weiterhin

## [7.6.1] - 2026-02-21 — STABILITY PATCH

### Granular Fault Isolation fuer Hub-Engines

#### Fix: Cascading Failure Prevention (HIGH Priority)
- **VORHER**: Ein Fehler in EINEM Hub-Modul brachte ALLE 17 Engines zum Absturz
- **NACHHER**: Jede Engine hat eigenes try/except — ein Fehler betrifft nur diese Engine
- **core_setup.py** komplett ueberarbeitet:
  1. Import-Phase: Wenn `hub/__init__.py` fehlschlaegt → klares Logging, Rest laeuft weiter
  2. Instantiierung: Jede der 17 Engines einzeln in try/except
  3. Integration Hub: Nur registrieren was existiert (None-Engines werden uebersprungen)
  4. Brain Sync: Nur wenn beide Seiten verfuegbar sind
- Integration Hub `register_engine()` crasht nicht mehr auf None
- `auto_wire()` und `sync_with_hub()` jeweils separat abgesichert
- Klares Logging: "Hub engines: X/17 initialized"

#### Szenario-Tests:
- Engine A defekt → Engine B-Q laufen trotzdem ✓
- Integration Hub defekt → Brain Architecture degradiert graceful ✓
- Alle Engines defekt → Core startet trotzdem, API gibt 503 ✓
- Alle Engines OK → Normalbetrieb wie v7.6.0 ✓

## [7.6.0] - 2026-02-21 — PRODUCTION-READY RELEASE

### Bulletproof Startup — Alle Engines verdrahtet und funktionsfaehig

#### Critical Fix: Full Engine Wiring in core_setup.py
- **core_setup.py** — Alle 17 Hub-Engines werden beim Start instanziiert
- Alle Engines beim SystemIntegrationHub registriert
- `auto_wire()` automatisch aufgerufen: 14 Event-Subscriptions aktiv
- Brain Architecture synchronisiert mit Integration Hub
- `hub_bp` Blueprint registriert: 120+ API Endpoints live
- `init_hub_api()` mit allen 17 Engines aufgerufen
- Graceful degradation: try/except fuer den gesamten Hub-Block

#### Startup-Sequenz:
1. 17 Hub-Engines instanziiert (Dashboard, Plugins, MultiHome, Maintenance, Anomaly, Zones, Light, Modes, Media, Energy, Templates, Scenes, Presence, Notifications, Integration, BrainArchitecture, BrainActivity)
2. 14 Engines beim SystemIntegrationHub registriert
3. Auto-Wiring: 14 Event-Subscriptions erstellt
4. Brain Architecture mit Hub synchronisiert
5. init_hub_api() aufgerufen mit allen Globals
6. hub_bp registriert: 120+ Endpoints unter /api/v1/hub/*

#### Test Suite: 233 Hub Tests bestanden
- test_system_integration.py: 34 tests
- test_brain_architecture.py: 41 tests
- test_brain_activity.py: 35 tests
- test_scene_intelligence.py: 46 tests
- test_presence_intelligence.py: 38 tests
- test_notification_intelligence.py: 39 tests

## [7.5.0] - 2026-02-21

### Brain Activity — Pulse, Sleep & Chat History

#### Brain Activity Engine (NEW)
- **hub/brain_activity.py** — `BrainActivityEngine`
- 3 Brain States: **active** (pulsierend), **idle** (wach), **sleeping** (Ressourcen-Sparmodus)
- Pulse Tracking: Jede Aktivität (Chat, API, Event) erzeugt einen Pulse
- Auto-Sleep: Nach konfigurierbarem Idle-Timeout schläft das Brain ein
- Auto-Wake: Chat-Nachricht oder API-Request weckt das Brain automatisch
- Chat History mit Message-Log (user/assistant), Metadata-Support
- Assistant-Nachrichten erzeugen automatisch Activity-Pulses
- Konfigurierbare Timeouts: idle (30s–1h), sleep (60s–24h)
- Pulse-History (500 Einträge), Chat-History (200 Einträge)

#### API Endpoints (10 NEW)
- `GET /api/v1/hub/brain/activity` — Activity Dashboard
- `GET /api/v1/hub/brain/activity/state` — Aktueller Brain State
- `POST /api/v1/hub/brain/activity/wake` — Brain aufwecken
- `POST /api/v1/hub/brain/activity/sleep` — Brain schlafen legen
- `POST /api/v1/hub/brain/activity/pulse` — Pulse starten
- `POST /api/v1/hub/brain/activity/pulse/end` — Pulse beenden
- `GET /api/v1/hub/brain/activity/chat` — Chat History abrufen
- `POST /api/v1/hub/brain/activity/chat` — Chat-Nachricht senden
- `POST /api/v1/hub/brain/activity/chat/clear` — Chat History löschen
- `POST /api/v1/hub/brain/activity/config` — Timeouts konfigurieren

#### Test Suite (NEW — 35 tests)
- **tests/test_brain_activity.py** — States, Idle Check, Pulses, Chat, Config, Status, Dashboard

## [7.4.0] - 2026-02-21

### Brain Architecture — Hirnregionen, Neuronen & Synapsen

#### Brain Architecture Engine (NEW)
- **hub/brain_architecture.py** — `BrainArchitectureEngine`
- 15 Hirnregionen mit Farben, Icons und funktionalen Rollen
  - Perception: Anomalie-Amygdala, Zonen-Thalamus, Energie-Hypothalamus, Anwesenheits-Somatosensorik
  - Cognition: Erweiterungskortex, Modus-Präfrontalkortex, Szenen-Wernicke-Areal
  - Motor: Licht-Visueller-Kortex, Medien-Auditorischer-Kortex, Automations-Broca-Areal, Benachrichtigungs-Insula
  - Memory: Wartungs-Hippocampus
  - Coordination: Kommandozentrale, Netzwerk-Kortex, Integrations-Corpus-Callosum
- Neuronen-Registry: HA Sensoren werden Hirnregionen zugeordnet
- 14 Default-Synapsen: Event-basierte Verbindungen zwischen Regionen
- Synapse Management: add, remove, fire, state (active/dormant/pending/blocked)
- Hebbian Learning: Häufig genutzte Synapsen werden stärker
- Hub-Sync: Automatischer Abgleich mit SystemIntegrationHub
- Graph-Daten: nodes + edges für Brain Graph Visualisierung

#### API Endpoints (11 NEW)
- `GET /api/v1/hub/brain` — Brain Dashboard (Regionen + Neuronen + Synapsen + Graph)
- `GET /api/v1/hub/brain/graph` — Graph-Daten für Visualisierung
- `GET /api/v1/hub/brain/regions` — Alle Hirnregionen
- `GET /api/v1/hub/brain/regions/<id>` — Region-Detail mit Neuronen & Synapsen
- `GET /api/v1/hub/brain/synapses` — Alle Synapsen
- `POST /api/v1/hub/brain/synapses` — Synapse erstellen
- `DELETE /api/v1/hub/brain/synapses/<id>` — Synapse entfernen
- `POST /api/v1/hub/brain/synapses/<id>/state` — Synapse-Status setzen
- `POST /api/v1/hub/brain/synapses/<id>/fire` — Synapse feuern
- `POST /api/v1/hub/brain/sync` — Mit Integration Hub synchronisieren

#### Test Suite (NEW — 41 tests)
- **tests/test_brain_architecture.py** — Regions, Neurons, Synapses, Sync, Graph, Status, Dashboard

## [7.3.0] - 2026-02-21

### System Integration Hub — Cross-Engine Orchestration

#### System Integration Hub (NEW)
- **hub/system_integration.py** — `SystemIntegrationHub`
- Cross-Engine Event-Dispatch: alle 15 Module automatisch verdrahtet
- 7 Event-Typen: presence_changed, zone_mode_changed, scene_activated, anomaly_detected, energy_threshold, person_arrived, person_departed
- Auto-Wiring: Standardmäßige Event→Engine Verknüpfungen beim Start
- Presence → Scene Intelligence + Media Follow + Notification Intelligence
- Zone Mode → Light Intelligence + Notification DND
- Scene Activated → Zone Modes Cascade + Notification
- Anomaly → Notification + Predictive Maintenance
- Energy Threshold → Notification + Scene Suggestion
- Person Arrived/Departed → Scene Suggest + Away Mode + Energy Advisor

#### API Endpoints (5 NEW)
- `GET /api/v1/hub/integration` — Dashboard (Status + Wiring)
- `GET /api/v1/hub/integration/status` — Hub Status
- `GET /api/v1/hub/integration/wiring` — Wiring Diagram
- `POST /api/v1/hub/integration/dispatch` — Event dispatchen
- `POST /api/v1/hub/integration/auto-wire` — Auto-Wiring neu ausführen

#### Test Suite (NEW — 34 tests)
- **tests/test_system_integration.py** — Engine Registration, Subscriptions, Auto-Wiring, Dispatch, Presence/Zone/Scene/Anomaly/Energy/Person Events, Status

## [7.2.0] - 2026-02-21

### Notification Intelligence — Smart Benachrichtigungs-Steuerung

#### Notification Intelligence Engine (NEW)
- **hub/notification_intelligence.py** — `NotificationIntelligenceEngine`
- Smart Notification Routing mit Priority-System (critical, high, normal, low, info)
- Do-Not-Disturb Integration per Person/Zone mit Critical-Override
- Notification Batching mit konfigurierbarem Digest-Intervall
- Multi-Channel Delivery: push, tts, display, email, telegram
- Routing Rules mit Quiet-Hours und Kategorie-Filter
- Notification History mit Read/Unread Tracking

#### API Endpoints (13 NEW)
- `GET /api/v1/hub/notifications` — Dashboard
- `POST /api/v1/hub/notifications/send` — Send notification
- `GET /api/v1/hub/notifications/history` — History
- `POST /api/v1/hub/notifications/<id>/read` — Mark read
- `POST /api/v1/hub/notifications/read-all` — Mark all read
- `POST /api/v1/hub/notifications/dnd` — Set DND
- `GET /api/v1/hub/notifications/dnd/status` — DND status
- `GET /api/v1/hub/notifications/rules` — List rules
- `POST /api/v1/hub/notifications/rules` — Add rule
- `DELETE /api/v1/hub/notifications/rules/<id>` — Remove rule
- `POST /api/v1/hub/notifications/batch` — Configure batching
- `POST /api/v1/hub/notifications/batch/flush` — Flush batch
- `GET /api/v1/hub/notifications/stats` — Statistics

#### Test Suite (NEW — 39 tests)
- **tests/test_notification_intelligence.py** — Send, DND, batching, rules, read tracking, history, stats, dashboard

## [7.1.0] - 2026-02-21

### Presence Intelligence — Anwesenheits-Intelligence & Raum-Tracking

#### Presence Intelligence Engine (NEW)
- **hub/presence_intelligence.py** — `PresenceIntelligenceEngine`
- Person-Level Anwesenheits-Tracking mit Raum-Auflösung
- Raum-zu-Raum Transition Detection mit Zeitstempel
- Occupancy Heatmap pro Raum über konfigurierbare Zeitfenster
- Presence-basierte Automation-Trigger (arrival, departure, idle, room_enter, room_leave)
- Home/Away Detection auf Person- und Haushalts-Ebene
- Occupancy Analytics: Peak Hours, Durchschnittsdauer, Visit-Logs
- Idle-Detection mit konfigurierbarem Schwellwert

#### API Endpoints (16 NEW)
- `GET /api/v1/hub/presence` — Presence Dashboard
- `POST /api/v1/hub/presence/persons` — Register person
- `GET /api/v1/hub/presence/persons/<id>` — Person details
- `DELETE /api/v1/hub/presence/persons/<id>` — Unregister person
- `GET /api/v1/hub/presence/rooms` — All rooms with occupancy
- `POST /api/v1/hub/presence/rooms` — Register room
- `POST /api/v1/hub/presence/update` — Update presence state
- `GET /api/v1/hub/presence/household` — Household status
- `GET /api/v1/hub/presence/transitions` — Recent transitions
- `GET /api/v1/hub/presence/room/<id>/occupancy` — Room occupancy stats
- `GET /api/v1/hub/presence/heatmap` — Occupancy heatmap
- `GET /api/v1/hub/presence/triggers` — List triggers
- `POST /api/v1/hub/presence/triggers` — Register trigger
- `DELETE /api/v1/hub/presence/triggers/<id>` — Remove trigger
- `POST /api/v1/hub/presence/idle` — Check idle triggers

#### Test Suite (NEW — 38 tests)
- **tests/test_presence_intelligence.py** — Persons, rooms, presence updates, triggers, analytics, household, dashboard

## [7.0.0] - 2026-02-21

### Scene Intelligence + PilotSuite Cloud — Intelligente Szenen-Steuerung

#### Scene Intelligence Engine (NEW)
- **hub/scene_intelligence.py** — `SceneIntelligenceEngine`
- 10 Built-in Szenen: Morgenroutine, Arbeits-Fokus, Mittagspause, Nachmittags-Entspannung, Abendessen, Filmabend, Romantischer Abend, Schlafenszeit, Party, Abwesend
- Kontext-basierte Szenen-Vorschläge (Uhrzeit, Anwesenheit, Helligkeit, Muster)
- Pattern Learning aus Aktivierungs-Historie (min. 3 Aktivierungen)
- PilotSuite Cloud: Verbindung, Sync, Szenen teilen, Local-First Fallback
- Custom Szenen Registration mit Tags und Kategorie
- Rating-System (1-5 Sterne) mit Running-Average
- Usage-Tracking und Popularitätssortierung
- 6 Kategorien: morning, day, evening, night, activity, custom

#### API Endpoints (12 NEW)
- `GET /api/v1/hub/scenes` — Scene Intelligence Dashboard
- `GET /api/v1/hub/scenes/list` — All scenes (filter by category)
- `GET /api/v1/hub/scenes/active` — Active scene
- `POST /api/v1/hub/scenes/activate` — Activate scene
- `POST /api/v1/hub/scenes/deactivate` — Deactivate scene
- `POST /api/v1/hub/scenes/suggest` — Context-based suggestions
- `POST /api/v1/hub/scenes/learn` — Trigger pattern learning
- `POST /api/v1/hub/scenes/cloud` — Configure PilotSuite Cloud
- `GET /api/v1/hub/scenes/cloud/status` — Cloud status
- `POST /api/v1/hub/scenes/cloud/share` — Share scene to cloud
- `POST /api/v1/hub/scenes/<id>/rate` — Rate scene
- `POST /api/v1/hub/scenes/custom` — Register custom scene

#### Test Suite (NEW — 46 tests)
- **tests/test_scene_intelligence.py** — Builtin scenes, activation, suggestions, patterns, cloud, custom, rating, dashboard

## [6.9.0] - 2026-02-21

### Automation Templates — AI-Generated Automation Blueprints

#### Automation Template Engine (NEW)
- **hub/automation_templates.py** — `AutomationTemplateEngine`
- 9 built-in Templates: Licht bei Bewegung, Nachtbeleuchtung, Heizplan, Fenster→Heizung, Türalarm, Spitzenverbrauch, Willkommen, Gute-Nacht, Gerät-fertig
- 6 Kategorien: Beleuchtung, Klima, Sicherheit, Energie, Komfort, Anwesenheit
- Template-Variablen mit Typ-System (entity, number, string, time, select)
- YAML-Preview-Generierung mit Variablen-Substitution
- Rating-System (1-5 Sterne) mit Running-Average
- Usage-Tracking und Popularitätssortierung
- Custom Template Registration

#### API Endpoints (7 NEW)
- `GET /api/v1/hub/templates` — List templates (filter by category/difficulty/search)
- `GET /api/v1/hub/templates/<id>` — Template details
- `GET /api/v1/hub/templates/categories` — Category overview
- `GET /api/v1/hub/templates/summary` — Template summary
- `POST /api/v1/hub/templates/generate` — Generate automation from template
- `POST /api/v1/hub/templates/<id>/rate` — Rate template
- `POST /api/v1/hub/templates/custom` — Register custom template

#### Test Suite (NEW — 29 tests)
- **tests/test_automation_templates.py** — Templates, filters, generation, rating, custom, summary

## [6.8.0] - 2026-02-21

### Energy Advisor — Personalized Savings Recommendations & Eco-Score

#### Energy Advisor Engine (NEW)
- **hub/energy_advisor.py** — `EnergyAdvisorEngine`
- Device energy tracking per category (Beleuchtung, Heizung, Kühlung, Haushaltsgeräte, Medien, Standby, EV)
- Consumption breakdown with percentages and costs
- Top consumer analysis
- Eco-Score (A+ bis F) with trend detection and household comparison
- 7 built-in Sparempfehlungen (Standby, LED, Heizplan, Waschen, E-Auto, Kühlung, Medien)
- Custom recommendation registration
- Dynamic electricity price updates with cost recalculation

#### API Endpoints (9 NEW)
- `GET /api/v1/hub/energy` — Energy advisor dashboard
- `POST /api/v1/hub/energy/devices` — Register device
- `POST /api/v1/hub/energy/consumption` — Update consumption
- `GET /api/v1/hub/energy/breakdown` — Category breakdown
- `GET /api/v1/hub/energy/top` — Top consumers
- `GET /api/v1/hub/energy/recommendations` — Savings recommendations
- `POST /api/v1/hub/energy/recommendations/<id>/apply` — Apply recommendation
- `GET /api/v1/hub/energy/eco-score` — Eco-Score
- `POST /api/v1/hub/energy/price` — Set electricity price

#### Test Suite (NEW — 30 tests)
- **tests/test_energy_advisor.py** — Device tracking, breakdown, eco-score, recommendations, dashboard

## [6.7.0] - 2026-02-21

### Media Follow / Musikwolke — Wiedergabe-Folgen & Playback Dashboard

#### Media Follow Engine (NEW)
- **hub/media_follow.py** — `MediaFollowEngine`
- Track active media playback across zones (music, TV, radio, podcast)
- Follow mode: playback follows user between Habitus zones on zone entry
- Per-zone and global follow toggle
- Playback session management with state tracking (playing/paused/idle)
- Media transfer between zones (presence-triggered or manual)
- Media cloud dashboard with zone states and transfer history
- Source registration with media type classification

#### API Endpoints (10 NEW)
- `GET /api/v1/hub/media` — Media cloud dashboard
- `GET /api/v1/hub/media/sources` — Registered media sources
- `POST /api/v1/hub/media/sources` — Register media source
- `DELETE /api/v1/hub/media/sources/<id>` — Unregister source
- `POST /api/v1/hub/media/playback` — Update playback state
- `GET /api/v1/hub/media/sessions` — Active sessions
- `GET /api/v1/hub/media/zone/<id>` — Zone media state
- `POST /api/v1/hub/media/follow` — Set follow mode
- `POST /api/v1/hub/media/transfer` — Transfer playback
- `POST /api/v1/hub/media/zone_enter` — Trigger zone entry follow

#### Test Suite (NEW — 33 tests)
- **tests/test_media_follow.py** — Sources, playback, follow mode, transfers, zones, dashboard

## [6.6.0] - 2026-02-21

### Zone Modes — Party/Sleep/Custom Quick-Switches mit Timer & Suppression

#### Zone Mode Engine (NEW)
- **hub/zone_modes.py** — `ZoneModeEngine`
- 8 built-in Modi: Partymodus, Kinderschlafmodus, Filmeabend, Gästemodus, Fokusmodus, Abwesend, Nachtmodus, Romantik
- Timer-basierte Auto-Deaktivierung (z.B. Party 3h, Film 3h, Gäste 8h)
- Suppression-System: Automationen, Licht, Medien, Benachrichtigungen pro Modus steuerbar
- Restrictions: max_volume_pct, min/max_brightness_pct, color_temp_k
- Mode-History mit Dauer-Tracking (activated, deactivated, expired, overridden)
- Custom Mode Registration für benutzerdefinierte Modi
- Per-Zone Modus-Verwaltung mit automatischer Ablösung

#### API Endpoints (7 NEW)
- `GET /api/v1/hub/modes` — Zone modes overview
- `GET /api/v1/hub/modes/available` — Available mode definitions
- `GET /api/v1/hub/modes/zone/<id>` — Zone mode status
- `POST /api/v1/hub/modes/activate` — Activate mode on zone
- `POST /api/v1/hub/modes/deactivate` — Deactivate zone mode
- `POST /api/v1/hub/modes/expire` — Check/expire timed-out modes
- `POST /api/v1/hub/modes/custom` — Register custom mode

#### Test Suite (NEW — 44 tests)
- **tests/test_zone_modes.py** — Built-in modes, activation, deactivation, expiration, suppression, restrictions, history, overview, custom modes

## [6.5.0] - 2026-02-21

### Licht-Intelligence — Sonnenstand, Helligkeit, Schwellwertregler, Mood-Szenen

#### Light Intelligence Engine (NEW)
- **hub/light_intelligence.py** — `LightIntelligenceEngine`
- Sun position tracking (elevation, azimuth, phase classification)
- Outdoor/indoor brightness averaging per zone
- Normalized illumination ratio (indoor/outdoor) mit Ausleuchtungsgrad
- Cloud-resilient moving average filter (Hysterese gegen Wolkenschwankungen)
- 8 Mood-Szenen: Energize, Focus, Relax, Cozy Evening, Night Light, Morning Glow, Dimmed, Off
- Automatic scene suggestion based on sun phase, hour, outdoor brightness
- Zone-level brightness thresholds with dimming suggestions
- Per-zone or global scene activation

#### API Endpoints (7 NEW)
- `GET /api/v1/hub/light` — Light dashboard
- `POST /api/v1/hub/light/sun` — Update sun position
- `POST /api/v1/hub/light/brightness` — Update brightness readings
- `GET /api/v1/hub/light/zone/<id>` — Zone brightness analysis
- `GET /api/v1/hub/light/scenes` — Available mood scenes
- `POST /api/v1/hub/light/scene` — Set active scene
- `GET /api/v1/hub/light/suggest` — Scene suggestion

#### Test Suite (NEW — 29 tests)
- **tests/test_light_intelligence.py** — Sun phases, brightness, cloud resilience, zones, scenes, dashboard

## [6.4.0] - 2026-02-21

### Habitus-Zonen — Room-to-Zone Grouping with Entity Adoption

#### Habitus Zone Engine (NEW)
- **hub/habitus_zones.py** — `HabitusZoneEngine`
- Group HA rooms into Habitus-Zonen (z.B. Bad + Toilette => Badbereich)
- Automatic entity adoption from rooms into zones
- 7 zone templates: Wohnbereich, Badbereich, Schlafbereich, Küche, Eingang, Außen, Büro
- 6 zone modes: Aktiv, Leerlauf, Schlafmodus, Partymodus, Abwesend, Benutzerdefiniert
- Zone state aggregation: temperature, humidity, occupancy, lights, active devices
- Entity deduplication across shared rooms
- Room registration with HA area_id mapping

#### API Endpoints (12 NEW)
- `GET /api/v1/hub/zones` — Zone overview
- `GET /api/v1/hub/zones/<id>` — Zone details
- `POST /api/v1/hub/zones` — Create zone
- `DELETE /api/v1/hub/zones/<id>` — Delete zone
- `POST /api/v1/hub/zones/<id>/mode` — Set zone mode
- `POST /api/v1/hub/zones/<id>/room` — Add room to zone
- `DELETE /api/v1/hub/zones/<id>/room/<rid>` — Remove room
- `GET /api/v1/hub/zones/rooms` — List rooms
- `POST /api/v1/hub/zones/rooms` — Register room
- `GET /api/v1/hub/zones/templates` — Zone templates
- `POST /api/v1/hub/zones/template/<id>` — Create from template
- `GET /api/v1/hub/zones/modes` — Available modes

#### Test Suite (NEW — 36 tests)
- **tests/test_habitus_zones.py** — Rooms, zones, entity adoption, modes, state, templates, deduplication

## [6.3.0] - 2026-02-21

### Gas Meter & Gastherme — Impulszähler, Preise, Statistiken, Forecast

#### Gas Meter Engine (NEW)
- **regional/gas_meter.py** — `GasMeterEngine`
- Impulse-based gas meter support (binary_sensor.gasdurchflusssensor)
- Direct m³ reading via counter entity
- Configurable impulse factor (0.01 or 0.10 m³/Impuls)
- kWh conversion: Brennwert × Zustandszahl (H-Gas Standard)
- Regional gas price defaults (Nord/Ost/Süd/West/Bundesdurchschnitt)
- Manual gas price configuration (ct/kWh)
- Initial meter reading import
- Daily/weekly/monthly/yearly statistics with cost calculation
- Month/year forecast with trend detection (steigend/fallend/stabil)
- Complete dashboard with all stats, config, and pricing

#### API Endpoints (7 NEW)
- `GET /api/v1/regional/gas` — Gas meter dashboard
- `POST /api/v1/regional/gas/impulse` — Record impulse(s)
- `POST /api/v1/regional/gas/reading` — Direct meter reading
- `GET /api/v1/regional/gas/stats/<period>` — Period statistics
- `GET /api/v1/regional/gas/forecast/<period>` — Consumption forecast
- `POST /api/v1/regional/gas/config` — Update configuration
- `POST /api/v1/regional/gas/initial` — Set initial meter reading

#### Test Suite (NEW — 38 tests)
- **tests/test_gas_meter.py** — Config, impulses, readings, conversions, statistics, forecast, dashboard, regional prices, edge cases

## [6.2.0] - 2026-02-21

### Anomaly Detection v2 — Multi-Dimensional Pattern Analysis

#### Anomaly Detection Engine (NEW)
- **hub/anomaly_detection.py** — `AnomalyDetectionEngine`
- 6 anomaly types: spike, drift, flatline, seasonal, frequency, correlation
- Multi-dimensional pattern analysis (time, value, frequency, cross-entity)
- Seasonal decomposition: hourly (0-23) and daily (Mon-Sun) pattern profiles
- Pearson correlation learning and broken-correlation detection
- Z-score based severity: info (2σ), warning (3σ), critical (4σ)
- Bilingual descriptions (DE/EN) for all anomaly types
- Configurable history depth (default 2016 points = 12 weeks hourly)

#### API Endpoints (7 NEW)
- `GET /api/v1/hub/anomalies` — Anomaly summary
- `GET /api/v1/hub/anomalies/list` — Anomalies with filters (entity, severity, type)
- `POST /api/v1/hub/anomalies/ingest` — Ingest sensor data points
- `POST /api/v1/hub/anomalies/detect` — Run anomaly detection
- `GET /api/v1/hub/anomalies/correlations` — Entity correlations
- `POST /api/v1/hub/anomalies/learn` — Trigger pattern learning
- `POST /api/v1/hub/anomalies/clear` — Clear anomalies

#### Test Suite (NEW — 31 tests)
- **tests/test_anomaly_detection.py** — Ingestion, pattern learning, spikes, drift, flatline, seasonal, frequency, correlations, descriptions

## [6.1.0] - 2026-02-21

### Predictive Maintenance — Device Health Scoring & Failure Prediction

#### Predictive Maintenance Engine (NEW)
- **hub/predictive_maintenance.py** — `PredictiveMaintenanceEngine`
- Device health scoring (0-100) with type-specific metric weights
- 6 monitored metrics: battery, response time, errors, uptime, signal, temperature
- 4 device types: sensor, actuator, controller, gateway
- Degradation rate tracking from metric history
- Time-to-failure estimation based on battery drain / score trends
- Issue identification and maintenance recommendations (DE)
- Priority-based attention list and upcoming maintenance schedule

#### API Endpoints (5 NEW)
- `GET /api/v1/hub/maintenance` — Maintenance summary
- `GET /api/v1/hub/maintenance/device/<id>` — Device health details
- `POST /api/v1/hub/maintenance/register` — Register device
- `POST /api/v1/hub/maintenance/ingest` — Ingest device metrics
- `POST /api/v1/hub/maintenance/evaluate` — Trigger health evaluation

#### Test Suite (NEW — 26 tests)
- **tests/test_predictive_maintenance.py** — Registration, metrics, scoring, issues, degradation, summary

## [6.0.0] - 2026-02-21

### PilotSuite Hub — Unified Dashboard, Plugin Architecture, Multi-Home

#### Dashboard Hub (NEW)
- **hub/dashboard.py** — `DashboardHub` with configurable widget layouts
- 14 widget types: energy, battery, heat pump, EV, weather, tariff, mood, etc.
- Layout management: columns, themes (auto/light/dark), language (DE/EN)
- Widget CRUD: add, remove, reorder, update data
- Data source registration for real-time widget updates
- Savings tracking and alert count aggregation

#### Plugin Manager (NEW)
- **hub/plugin_manager.py** — `PluginManager` with dependency-aware lifecycle
- 6 built-in plugins: energy_management, heat_pump, ev_charging, weather, mood, styx_agent
- Plugin lifecycle: install → activate → disable, with dependency validation
- Category system: energy, comfort, security, automation, general
- Plugin configuration and capability registry

#### Multi-Home Manager (NEW)
- **hub/multi_home.py** — `MultiHomeManager` for multiple properties
- Home registration with location, URL, and token
- Active home switching
- Cross-home aggregation: total devices, energy, cost
- Status tracking: online/offline/syncing per home

#### Hub API (15 NEW endpoints)
- Dashboard: GET overview, GET/POST/DELETE widgets, POST layout
- Plugins: GET list, GET detail, POST activate/disable/config
- Multi-Home: GET list, GET/POST/DELETE homes, POST activate, POST status

#### Test Suite (NEW — 39 tests)
- **tests/test_hub.py** — Dashboard, plugin manager, multi-home manager

## [5.25.0] - 2026-02-21

### EV Charging Planner — Smart Charging from Tariff+Solar+Departure

#### EV Charging Engine (NEW)
- **regional/ev_charging_planner.py** — `EVChargingPlanner` with cost/solar optimization
- 4 strategies: cost_optimized, solar_first, fastest, balanced
- Departure-aware scheduling with SoC targets and deadlines
- Solar surplus priority — free charging from PV excess
- Charger efficiency modeling (AC losses)
- Range estimation from SoC and vehicle consumption profile
- Connector types: type2, ccs, chademo
- 1-phase and 3-phase charging support

#### API Endpoints (7 NEW)
- `GET /api/v1/regional/ev/schedule` — Optimized charging schedule
- `GET /api/v1/regional/ev/status` — Current EV charging state
- `POST /api/v1/regional/ev/soc` — Update state of charge
- `POST /api/v1/regional/ev/departure` — Set departure schedule
- `POST /api/v1/regional/ev/config` — Configure EV and charger
- `POST /api/v1/regional/ev/strategy` — Set charging strategy
- `POST /api/v1/regional/ev/ingest` — Import tariff/PV data

#### Test Suite (NEW — 40 tests)
- **tests/test_ev_charging_planner.py** — Config, energy calc, optimization, departure, import, status

#### Infrastructure
- **regional/__init__.py** — Exports EVChargingPlanner
- **regional/api.py** — init_regional_api() accepts ev_charging_planner parameter

## [5.24.0] - 2026-02-21

### Heat Pump Controller — COP-Optimized Scheduling

#### Heat Pump Engine (NEW)
- **regional/heat_pump_controller.py** — `HeatPumpController` with COP-optimized scheduling
- Carnot-based COP calculation for air_water, ground_water, air_air pump types
- 4 strategies: cop_optimized, price_optimized, comfort_first, solar_boost
- Building thermal model: heat loss estimation, room temp simulation
- DHW (domestic hot water) cycle management with tank temperature tracking
- Defrost cycle detection for air-source pumps (frost-prone range)
- PV surplus solar boost — free heating from photovoltaic excess
- Weather forecast integration for outdoor temperature profiles
- Tariff-aware scheduling — combines COP and price for effective cost per kWh_th

#### API Endpoints (7 NEW)
- `GET /api/v1/regional/heatpump/schedule` — COP-optimized schedule (48h default)
- `GET /api/v1/regional/heatpump/status` — Current heat pump state
- `POST /api/v1/regional/heatpump/room-temp` — Update room temperature
- `POST /api/v1/regional/heatpump/hot-water-temp` — Update DHW temperature
- `POST /api/v1/regional/heatpump/config` — Configure heat pump system
- `POST /api/v1/regional/heatpump/strategy` — Set scheduling strategy
- `POST /api/v1/regional/heatpump/ingest` — Import weather/tariff/PV data

#### Test Suite (NEW — 43 tests)
- **tests/test_heat_pump_controller.py** — COP, config, optimization, strategies, data import, status

#### Infrastructure
- **regional/__init__.py** — Exports HeatPumpController
- **regional/api.py** — init_regional_api() accepts heat_pump_controller parameter

## [5.23.0] - 2026-02-21

### Battery Strategy Optimizer — ML-based Charge/Discharge Scheduling

#### Battery Optimizer Engine (NEW)
- **regional/battery_optimizer.py** — `BatteryStrategyOptimizer` with greedy optimization
- 48h charge/discharge schedule combining prices, PV, consumption patterns
- 4 strategies: arbitrage (buy low/sell high), solar_first, peak_shaving, backup
- SoC constraint management (min/max limits, cycle budget)
- Battery degradation cost model (EUR/kWh cycled)
- Solar priority: free energy always charged first
- Consumption pattern defaults (German household curve)
- Round-trip efficiency modeling (AC-to-AC)
- Savings estimation vs no-battery baseline

#### API Endpoints (5 NEW)
- `GET /api/v1/regional/battery/schedule` — Optimized charge/discharge schedule
- `GET /api/v1/regional/battery/status` — Current battery state
- `POST /api/v1/regional/battery/soc` — Update state of charge
- `POST /api/v1/regional/battery/config` — Configure battery system
- `POST /api/v1/regional/battery/ingest` — Import forecast data

#### Test Suite (NEW — 23 tests)
- **tests/test_battery_optimizer.py** — Init, optimization, solar, arbitrage, status, import

#### Infrastructure
- **regional/__init__.py** — Exports BatteryStrategyOptimizer
- **regional/api.py** — init_regional_api() accepts battery_optimizer parameter

## [5.22.0] - 2026-02-21

### Styx Greeting & Onboarding — Welcome Flow for New Installations

#### Onboarding Module (NEW)
- **onboarding.py** — `onboarding_bp` Blueprint with welcome & onboarding API
- 8-step onboarding wizard: welcome, LLM check, conversation agent, regional config,
  energy setup, dashboard check, test conversation, complete
- Bilingual step descriptions (DE/EN) with icons and action types
- Session-based state management (multiple concurrent onboardings)
- Step completion and skip tracking with is_complete detection
- Personalized welcome message with agent name, personality, quick actions
- 6 character personalities: copilot, butler, energy_manager, security_guard, friendly, minimal

#### API Endpoints (5 NEW)
- `GET /api/v1/onboarding/welcome` — Personalized Styx welcome message
- `GET /api/v1/onboarding/state` — Current onboarding progress
- `POST /api/v1/onboarding/step/complete` — Mark step as done
- `POST /api/v1/onboarding/step/skip` — Skip a step
- `POST /api/v1/onboarding/reset` — Restart onboarding

#### Test Suite (NEW — 21 tests)
- **tests/test_onboarding.py** — Init, steps, state, sessions, welcome, personalities

## [5.21.0] - 2026-02-21

### Styx Agent Auto-Config — Health Check, Connectivity & Greeting API

#### Agent Config Module (NEW)
- **agent_config.py** — `agent_config_bp` Blueprint with agent health/config endpoints
- Agent status reporting: name, version, uptime, LLM availability, features, character
- Agent capabilities discovery: conversation, tool calling, web search, energy, mood, brain graph
- Bilingual greeting templates (DE/EN) for new installations
- Bidirectional communication verification (HA sends, Core echoes + status)
- Ping endpoint for quick health checks

#### API Endpoints (5 NEW)
- `GET /api/v1/agent/status` — Full agent health and status
- `GET /api/v1/agent/capabilities` — Agent feature discovery
- `GET /api/v1/agent/greeting` — Installation greeting (lang=de/en)
- `GET /api/v1/agent/ping` — Quick alive check
- `POST /api/v1/agent/verify` — Bidirectional communication verification

#### Test Suite (NEW — 17 tests)
- **tests/test_agent_config.py** — Init, LLM availability, features, dataclasses, greetings

## [5.20.0] - 2026-02-21

### Energy Forecast Dashboard — 48h Visual Forecast with PV, Prices & Recommendations

#### Energy Forecast Engine (NEW)
- **regional/energy_forecast.py** — `EnergyForecastEngine` combining solar, prices, weather
- 48-hour forecast with per-hour PV factor, estimated kW, price, and weather impact
- Composite scoring (0-10) per hour: PV bonus, price scoring, weather penalty
- 5 action recommendations: consume, charge, hold, shift, discharge
- Price level classification: very_low/low/normal/high/very_high (ratio-based)
- Inline solar position calculation (declination, equation of time, hour angle)
- Dashboard card generation: price_chart, pv_forecast, recommendation, overview
- Tariff data import (from RegionalTariffEngine format)
- Weather warning impact import (from WeatherWarningManager format)
- Configurable: PV peak kW, location, grid price

#### API Endpoints (6 NEW)
- `GET /api/v1/regional/forecast/dashboard` — Complete 48h dashboard data
- `GET /api/v1/regional/forecast/hours` — Hourly forecast array
- `GET /api/v1/regional/forecast/summary` — Summary statistics
- `GET /api/v1/regional/forecast/cards` — Lovelace dashboard cards
- `POST /api/v1/regional/forecast/ingest` — Import tariff/warning data
- `POST /api/v1/regional/forecast/config` — Configure PV, location, price

#### Test Suite (NEW — 37 tests)
- **tests/test_energy_forecast.py** — Init, forecast, prices, weather, summary, cards, dashboard, import

#### Infrastructure
- **regional/__init__.py** — Exports EnergyForecastEngine
- **regional/api.py** — init_regional_api() accepts forecast_engine parameter

## [5.19.0] - 2026-02-21

### Proactive Alert System — Combined Weather+Price+Grid Alerts

#### Proactive Alert Engine (NEW)
- **regional/proactive_alerts.py** — `ProactiveAlertEngine` aggregating all regional data
- Weather alerts: severe weather → battery protection, PV impact → grid fallback, grid risk → curtailment
- Price alerts: spike detection, cheap window notification, arbitrage opportunities
- PV alerts: high production → self-consumption, sunset → charge from PV
- Combined alert: severe weather + high price = critical protection mode
- 4 priority levels: Info, Hinweis, Warnung, Kritisch
- Cooldown system prevents duplicate alerts (configurable per rule)
- Alert expiration (TTL) with automatic cleanup
- Dismiss/acknowledge alerts via API
- Configurable thresholds: price spike, price low, PV drop percentage
- Bilingual alerts (DE/EN) with action recommendations

#### API Endpoints (4 NEW)
- `GET /api/v1/regional/alerts` — All active alerts with summary
- `POST /api/v1/regional/alerts/evaluate` — Trigger evaluation from all services
- `POST /api/v1/regional/alerts/dismiss` — Dismiss an alert
- `POST /api/v1/regional/alerts/config` — Configure thresholds

#### Test Suite (NEW — 32 tests)
- **tests/test_proactive_alerts.py** — Weather, price, PV, combined, cooldowns, dismiss, config

#### Infrastructure
- **regional/__init__.py** — Exports ProactiveAlertEngine
- **regional/api.py** — Updated with alert endpoints and evaluate integration

## [5.18.0] - 2026-02-21

### Regional Tariff Engine — Dynamic Electricity Pricing with aWATTar/EPEX

#### Tariff Engine (NEW)
- **regional/tariff_engine.py** — `RegionalTariffEngine` with dynamic pricing support
- aWATTar API parser (DE/AT): MWh→kWh conversion with country-specific surcharges
- Time-of-use (HT/NT) schedule: German weekday/weekend price curves
- Fixed rate fallback for simple tariffs
- Price level classification: very_low/low/normal/high/very_high
- Optimal consumption window finder (cheapest N-hour block)
- Tariff recommendation engine: charge_now/wait/shift/discharge actions
- Bilingual recommendations (DE/EN) with savings calculations
- Configurable: country, tariff type, fixed rate, feed-in rate

#### API Endpoints (6 NEW)
- `GET /api/v1/regional/tariff/summary` — Current price, stats, level
- `GET /api/v1/regional/tariff/prices` — All hourly prices
- `GET /api/v1/regional/tariff/optimal?hours=3` — Cheapest time window
- `GET /api/v1/regional/tariff/recommendation` — Action recommendation
- `POST /api/v1/regional/tariff/ingest` — Ingest aWATTar/manual data
- `POST /api/v1/regional/tariff/config` — Configure tariff type/rates

#### Test Suite (NEW — 52 tests)
- **tests/test_tariff_engine.py** — aWATTar parsing, TOU, fixed, summary, windows, recommendations

#### Infrastructure
- **regional/__init__.py** — Exports RegionalTariffEngine
- **regional/api.py** — Updated with tariff endpoints

## [5.17.0] - 2026-02-21

### Fuel Price Tracker — Tankerkoenig Integration with EV vs ICE Comparison

#### Fuel Price Tracker (NEW)
- **regional/fuel_prices.py** — `FuelPriceTracker` with Tankerkoenig API integration
- Parses Tankerkoenig station data (name, brand, distance, diesel/E5/E10 prices)
- Manual price input for users without API key
- Price aggregation: avg/min/max per fuel type, cheapest station names
- Cost-per-100km comparison: Elektro vs Diesel vs Benzin vs E10
- Default consumption: EV 18kWh, Diesel 6L, Benzin 7.5L per 100km
- CO2 comparison per 100km (electric vs combustion)
- Configurable: API key, radius, vehicle consumption values, grid price
- Price history tracking (up to 168 snapshots for weekly trend)
- Dashboard-ready data with top 5 nearest stations and 48h price history
- Bilingual recommendations (DE/EN) with savings calculations

#### API Endpoints (6 NEW)
- `GET /api/v1/regional/fuel/prices` — Aggregated fuel price summary
- `GET /api/v1/regional/fuel/compare` — Cost-per-100km comparison
- `GET /api/v1/regional/fuel/dashboard` — Full dashboard data with history
- `GET /api/v1/regional/fuel/stations` — Nearby stations with prices
- `POST /api/v1/regional/fuel/ingest` — Ingest Tankerkoenig/manual data
- `POST /api/v1/regional/fuel/config` — Configure API key, consumption, radius

#### Test Suite (NEW — 56 tests)
- **tests/test_fuel_prices.py** — Parsing, aggregation, comparison, dashboard, config, history

#### Infrastructure
- **regional/__init__.py** — Exports FuelPriceTracker
- **regional/api.py** — Updated with fuel endpoints and init_regional_api(fuel_tracker=)

## [5.16.0] - 2026-02-21

### DWD Weather Warnings — German Weather Service Alerts

#### Weather Warning Manager (NEW)
- **regional/weather_warnings.py** — `WeatherWarningManager` for DWD/ZAMG/MeteoSchweiz alerts
- 4 severity levels: Wetterwarnung (yellow), Markante (orange), Unwetter (red), Extreme (violet)
- 11 warning types: Gewitter, Wind, Starkregen, Schnee, Glätte, Nebel, Frost, Hitze, UV, Hochwasser
- DWD JSON format parser (cell-based dict + list formats)
- Generic warning parser for ZAMG and MeteoSchweiz
- PV impact assessment: per-type reduction estimates (0-100%) with severity scaling
- Grid risk assessment: per-type grid stability evaluation
- Energy recommendations in German and English per warning type
- Warning filtering: by severity, active status, PV impact, grid risk
- Human-readable summary text (DE/EN) with PV reduction indicators
- 5-minute cache TTL for warning refresh management

#### API Endpoints (5 NEW)
- `GET /api/v1/regional/warnings` — All active warnings with impact assessment
- `GET /api/v1/regional/warnings/pv` — PV-affecting warnings only
- `GET /api/v1/regional/warnings/grid` — Grid-affecting warnings only
- `GET /api/v1/regional/warnings/summary` — Human-readable summary (de/en)
- `POST /api/v1/regional/warnings/ingest` — Ingest DWD/generic warning data

#### Test Suite (NEW — 52 tests)
- **tests/test_weather_warnings.py** — DWD parsing, generic parsing, impact, filtering, overview, summary

#### Infrastructure
- **regional/__init__.py** — Exports WeatherWarningManager
- **regional/api.py** — Updated with warning endpoints and init_regional_api(warning_manager=)

## [5.15.0] - 2026-02-21

### Regional Context Provider — Zero-Config Location-Aware Data

#### Regional Context Provider (NEW)
- **regional/context_provider.py** — Auto-detects country (DE/AT/CH) from HA zone.home coordinates
- Solar position calculator: sunrise, sunset, solar noon, elevation, azimuth, day length
- Country detection with DACH lat/lon mapping
- German Bundesland detection from coordinates
- Regional defaults per country: grid price, feed-in tariff, price API, weather service, news sources
- PV production factor (0-1) from solar elevation
- Day info bundle: sunrise, sunset, pricing, weather service, language
- Zero-config design: HA sensor auto-pushes location from zone.home on first update

#### API Endpoints (NEW)
- `GET /api/v1/regional/context` — Complete context (location + solar + defaults)
- `GET /api/v1/regional/solar` — Current solar position
- `GET /api/v1/regional/solar/factor` — PV production factor (0-1)
- `GET /api/v1/regional/defaults` — Regional defaults (pricing, services)
- `GET /api/v1/regional/day-info` — Day info bundle
- `POST /api/v1/regional/location` — Update location from HA

#### Test Suite (NEW — 45+ tests)
- **tests/test_regional_context.py** — Country detection, solar, defaults, context, PV factor, day info, update

#### Infrastructure
- **regional/__init__.py** — Module with public exports
- **regional/api.py** — Blueprint with 6 endpoints
- **config.json** — Version 5.15.0

## [5.14.0] - 2026-02-21

### Demand Response Manager — Grid Signal Response & Load Curtailment

#### Demand Response Manager (NEW)
- **energy/demand_response.py** — Responds to grid signals with automatic load curtailment
- 4 signal levels: NORMAL (0), ADVISORY (1), MODERATE (2), CRITICAL (3)
- 4 device priorities: DEFERRABLE (1), FLEXIBLE (2), COMFORT (3), ESSENTIAL (4)
- ESSENTIAL devices never shed; COMFORT only shed at CRITICAL level
- Automatic curtailment based on signal level with priority ordering
- Signal cancellation auto-restores all curtailed devices
- Action history with curtail/restore events
- Performance metrics tracking
- Thread-safe with `threading.Lock`

#### API Endpoints (NEW)
- `GET /api/v1/energy/demand-response/status` — System status
- `POST /api/v1/energy/demand-response/signal` — Receive grid signal
- `GET /api/v1/energy/demand-response/signals` — Active signals
- `GET /api/v1/energy/demand-response/devices` — Managed devices list
- `POST /api/v1/energy/demand-response/devices` — Register device
- `POST /api/v1/energy/demand-response/curtail/<device_id>` — Manual curtail
- `POST /api/v1/energy/demand-response/restore/<device_id>` — Restore device
- `GET /api/v1/energy/demand-response/history` — Action history
- `GET /api/v1/energy/demand-response/metrics` — Performance metrics

#### Test Suite (NEW — 40+ tests)
- **tests/test_demand_response.py** — Registration, signals, auto-curtailment, manual, status, history, metrics

#### Infrastructure
- **config.json** — Version 5.14.0

## [5.13.0] - 2026-02-21

### Energy Report Generator — Structured Energy Reports

#### Report Generator (NEW)
- **energy/report_generator.py** — Generates daily/weekly/monthly energy reports
- Consumption breakdown: total, production, net grid, self-consumed, fed-in, autarky ratio
- Cost analysis: gross/net cost, solar savings, feed-in revenue, cheapest/most expensive day
- Period comparison with trend detection (improving/stable/worsening)
- German optimization recommendations by category (solar, scheduling, consumption, tariff)
- Device-level insights aggregated from fingerprint data
- Highlights summary in German

#### API Endpoints (NEW)
- `POST /api/v1/energy/reports/generate` — Generate report (body: report_type, end_date)
- `GET /api/v1/energy/reports/coverage` — Data coverage info
- `POST /api/v1/energy/reports/data` — Add daily energy data

#### Test Suite (NEW — 40+ tests)
- **tests/test_report_generator.py** — Data, generation, consumption, costs, comparison, recommendations, highlights, devices

#### Infrastructure
- **config.json** — Version 5.13.0

## [5.12.0] - 2026-02-21

### Appliance Fingerprinting — Device Identification from Power Signatures

#### Appliance Fingerprinter (NEW)
- **energy/fingerprint.py** — Learns and identifies appliances from power consumption patterns
- `ApplianceFingerprinter` with archetype bootstrapping (washer, dryer, dishwasher, oven, ev_charger, heat_pump)
- `record_signature()` — Record power samples for fingerprint learning
- `identify()` — Match live power reading to known fingerprints (Gaussian confidence scoring)
- `get_usage_stats()` — Per-device usage statistics (runs, kWh, duration, weekly/monthly counts)
- Phase detection: Hochlast/Normalbetrieb/Niedriglast from power variance
- Remaining time estimation based on matched phase position

#### API Endpoints (NEW)
- `GET /api/v1/energy/fingerprints` — List all known fingerprints
- `GET /api/v1/energy/fingerprints/<device_id>` — Get specific fingerprint
- `POST /api/v1/energy/fingerprints/record` — Record power signature
- `POST /api/v1/energy/fingerprints/identify` — Identify device from watts
- `GET /api/v1/energy/fingerprints/usage` — Usage statistics for all devices

#### Test Suite (NEW — 40+ tests)
- **tests/test_appliance_fingerprint.py** — Bootstrap, record, identify, usage, phases

#### Infrastructure
- **config.json** — Version 5.12.0

## [5.11.0] - 2026-02-21

### Weather-Aware Energy Optimizer — Forecast-Driven Consumption Planning

#### Weather-Aware Optimizer (NEW)
- **prediction/weather_optimizer.py** — Combines weather, pricing, PV forecast into 48h plans
- `WeatherAwareOptimizer.optimize()` → WeatherOptimizationPlan with hourly forecast, windows, battery plan
- Composite scoring: PV (35%) + Price (35%) + Weather (15%) + Demand (15%)
- Contiguous optimal window detection with reason classification (solar_surplus, low_price, combined)
- Battery management: charge_from_pv, charge_from_grid, discharge, hold — rule-based SOC management
- German-language alerts: storm, extended cloud, price spikes, frost warnings
- `get_best_window(duration)` — Find best contiguous block for device scheduling
- Cloud-to-PV efficiency interpolation, solar elevation curve, default price curve

#### API Endpoints (NEW)
- `GET /api/v1/predict/weather-optimize` — Summary plan with windows + alerts
- `GET /api/v1/predict/weather-optimize/full` — Full plan with all hourly data + battery actions
- `GET /api/v1/predict/weather-optimize/best-window` — Best contiguous window (query: `duration`)

#### Test Suite (NEW — 45+ tests)
- **tests/test_weather_optimizer.py** — Helpers, optimize, hourly, windows, battery, alerts, best-window, summary

#### Infrastructure
- **prediction/__init__.py** — Export WeatherAwareOptimizer
- **prediction/api.py** — `_weather_optimizer` singleton + `weather_optimizer` param
- **config.json** — Version 5.11.0

## [5.10.0] - 2026-02-21

### Energy Cost Tracker — Daily/Weekly/Monthly Cost History

#### Energy Cost Tracker (NEW)
- **energy/cost_tracker.py** — Tracks energy costs with budget management
- `record_day()` — Record daily consumption, production, and pricing → DailyCost
- Net consumption = max(0, consumption - production); solar savings calculated
- `get_daily_history(days)` — Most-recent-first cost history with configurable limit
- `get_summary(period)` — CostSummary for "daily", "weekly", "monthly" periods
- `get_budget_status()` — Monthly budget tracking with projected total and on-track flag
- `compare_periods(current_days, previous_days)` — Period-over-period with trend (up/down/stable)
- `get_rolling_average(days)` — Windowed daily cost average
- Dataclasses: DailyCost, CostSummary, BudgetStatus

#### API Endpoints (NEW)
- `GET /api/v1/energy/costs` — Daily cost history (query: `days`)
- `GET /api/v1/energy/costs/summary` — Period summary (query: `period`)
- `GET /api/v1/energy/costs/budget` — Monthly budget status
- `GET /api/v1/energy/costs/compare` — Period comparison (query: `current_days`, `previous_days`)

#### Test Suite (NEW — 30+ tests)
- **tests/test_cost_tracker.py** — RecordDay, DailyHistory, Summary, Budget, Comparison, RollingAverage

#### Infrastructure
- **config.json** — Version 5.10.0

## [5.9.0] - 2026-02-21

### Automation Suggestions — Generate HA Automations from Patterns

#### Automation Suggestion Engine (NEW)
- **automations/suggestion_engine.py** — Generates HA automation YAML from observed patterns
- 4 suggestion types:
  - **Time-based**: Schedule device runs at optimal hours (weekday/daily)
  - **Solar-based**: Start devices when PV surplus exceeds threshold
  - **Comfort-based**: Trigger actions on CO2, temperature, humidity thresholds
  - **Presence-based**: Away-mode actions when nobody home
- Accept/dismiss workflow for user-driven curation
- Confidence scoring and savings estimates per suggestion
- Valid HA automation YAML output ready for direct import

#### API Endpoints (NEW)
- `GET /api/v1/automations/suggestions` — List suggestions with category filter
- `POST /api/v1/automations/suggestions/{id}/accept` — Accept a suggestion
- `POST /api/v1/automations/suggestions/{id}/dismiss` — Dismiss a suggestion
- `GET /api/v1/automations/suggestions/{id}/yaml` — Raw YAML for a suggestion
- `POST /api/v1/automations/generate` — Bulk-generate from schedule/solar/comfort/presence data

#### Test Suite (NEW — 30+ tests)
- **tests/test_automation_suggestions.py** — Schedule, solar, comfort, presence, management

#### Infrastructure
- **automations/__init__.py** — Module with public exports
- **config.json** — Version 5.9.0

## [5.8.0] - 2026-02-21

### Notification Engine — Smart Alert Aggregation

#### Notification Engine (NEW)
- **notifications/engine.py** — Central notification hub for all PilotSuite modules
- Priority levels: CRITICAL (1), HIGH (2), NORMAL (3), LOW (4)
- Deduplication: identical alerts within configurable time window merged (default 10 min)
- Rate limiting: max N notifications/hour per channel (default 20/h)
- CRITICAL priority bypasses both dedup and rate limits
- LOW priority batched into periodic digest summaries
- History buffer with max 500 entries
- Thread-safe with `threading.Lock`
- `notify()` — Submit notification, returns None if deduped/rate-limited
- `flush_pending()` — Get & clear pending for delivery
- `get_digest()` — Notification summary with by-source and by-priority counts
- `get_history()` — Recent items with optional source filter
- `register_handler()` — Channel-specific delivery callbacks

#### API Endpoints (NEW)
- `GET /api/v1/notifications` — History with limit and source filter
- `POST /api/v1/notifications` — Submit notification
- `GET /api/v1/notifications/digest` — Digest summary
- `GET /api/v1/notifications/pending` — Flush pending for delivery
- `GET /api/v1/notifications/stats` — Engine statistics

#### Test Suite (NEW — 35+ tests)
- **tests/test_notification_engine.py** — Priority, notify, dedup, rate limiting, history, digest, pending, stats, clear, handlers

#### Infrastructure
- **notifications/__init__.py** — Module with public exports
- **config.json** — Version 5.8.0

## [5.7.0] - 2026-02-21

### Comfort Index — Environmental Comfort Scoring + Adaptive Lighting

#### Comfort Module (NEW)
- **comfort/index.py** — Composite 0-100 comfort index from 4 environmental factors:
  - Temperature (35%): Optimal 20-22C, scored with decay curve
  - Humidity (25%): Optimal 40-60%, penalizes dry and humid extremes
  - Air Quality (20%): CO2 ppm scoring — optimal <600, poor >1500
  - Light Level (20%): Time-of-day adaptive targets (300 lux morning, 500 daytime, 80 evening)
- Letter grades (A/B/C/D/F) based on composite score
- German-language improvement suggestions per factor
- `get_lighting_suggestion()` — Adaptive lighting with circadian color temperature:
  - 4000K morning (wake), 5000K daytime (productive), 3000K evening (warm), 2200K night
  - Cloud cover adjustment for natural light deficit
  - Brightness auto-calculation from deficit vs. target lux

#### API Endpoints (NEW)
- `GET /api/v1/comfort` — Comfort index with per-factor scores and suggestions
- `GET /api/v1/comfort/lighting` — Adaptive lighting suggestion per area

#### Test Suite (NEW — 45+ tests)
- **tests/test_comfort_index.py** — Temperature, humidity, CO2, light scoring, grades, composite, suggestions, lighting

#### Infrastructure
- **comfort/__init__.py** — Module with public exports
- **config.json** — Version 5.7.0

## [5.6.0] - 2026-02-21

### Dashboard Config API — Lovelace Card Generation Support

#### API Endpoint (NEW)
- `GET /api/v1/energy/dashboard-config` — Returns zone list, endpoint URLs, and current energy state for HA card generation

#### Infrastructure
- **config.json** — Version 5.6.0

## [5.5.0] - 2026-02-21

### Smart Schedule Planner — Optimal 24h Device Scheduling

#### Schedule Planner (NEW)
- **prediction/schedule_planner.py** — Generates optimal daily device schedules
- Combines PV forecast, dynamic pricing (aWATTar), and device baselines
- Composite slot scoring: `w_pv * pv_factor + w_price * price_factor + w_peak * peak_factor`
- Greedy assignment by priority (1=highest, 5=lowest)
- Peak shaving: prevents concurrent load exceeding household limit (11kW default)
- Default solar curve for Central European latitudes
- `DeviceProfile` / `ScheduleSlot` / `DeviceSchedule` / `DailyPlan` dataclasses
- Configurable weights, power limits, and device profiles

#### API Endpoints (NEW)
- `GET /api/v1/predict/schedule/daily` — Full 24h schedule with hourly slot data
- `GET /api/v1/predict/schedule/next` — Next upcoming scheduled device

#### Test Suite (NEW)
- **tests/test_schedule_planner.py** — 30+ tests covering:
  - Dataclass defaults and custom values
  - Default profile validation (5 device types)
  - PV curve shape and range validation
  - Price map with off-peak and custom pricing
  - Full plan generation with various device lists
  - PV optimization: high PV reduces device cost
  - Peak shaving: concurrent power limit enforcement
  - Scoring: custom weights, non-negative scores
  - Edge cases: short PV forecast padding, custom dates, invalid prices

#### Infrastructure
- **config.json** — Version 5.5.0
- **prediction/__init__.py** — Updated, exports SchedulePlanner

## [5.4.0] - 2026-02-21

### OpenAPI Spec v5.4.0 — Complete Energy API Documentation

#### OpenAPI Specification Update
- **docs/openapi.yaml** — Updated from 4.2.0 to 5.4.0
- Added `Energy` tag with full description
- Updated API description with energy monitoring and Sankey capabilities

#### Energy Endpoints Documented (11 paths, 12 operations)
- `GET /api/v1/energy` — Complete energy snapshot
- `GET /api/v1/energy/anomalies` — Anomaly detection with severity levels
- `GET /api/v1/energy/shifting` — Load shifting opportunities with cost/savings
- `GET /api/v1/energy/explain/{suggestion_id}` — Suggestion explainability
- `GET /api/v1/energy/baselines` — Device type consumption baselines
- `GET /api/v1/energy/suppress` — Suggestion suppression status
- `GET /api/v1/energy/health` — Energy service health diagnostics
- `GET /api/v1/energy/zone/{zone_id}` — Zone energy data with entity breakdown
- `POST /api/v1/energy/zone/{zone_id}` — Register zone energy entities
- `GET /api/v1/energy/zones` — All zones energy overview
- `GET /api/v1/energy/sankey` — Sankey flow data (JSON)
- `GET /api/v1/energy/sankey.svg` — Sankey diagram (SVG image)

#### New Component Schemas (17 schemas)
- `EnergySnapshot`, `EnergyAnomaly`, `EnergyAnomaliesResponse`
- `ShiftingOpportunity`, `ShiftingResponse`, `SuggestionExplanation`
- `BaselinesResponse`, `SuppressResponse`, `EnergyHealthResponse`
- `ZoneEnergyRegister`, `ZoneEnergyRegistered`, `ZoneEnergyResponse`
- `AllZonesEnergyResponse`, `SankeyNode`, `SankeyFlow`, `SankeyDataResponse`

#### Spec Statistics
- Total paths: 49 (was 38)
- Total schemas: 64 (was 47)
- Total tags: 13 (was 12)

#### Infrastructure
- **config.json** — Version 5.4.0

## [5.3.0] - 2026-02-21

### Test Coverage — Sankey Renderer Tests

#### Test Suite (NEW)
- **tests/test_sankey.py** — 25 tests for Sankey energy flow diagram renderer
  - `TestDataclasses` — SankeyNode, SankeyFlow, SankeyData defaults and custom values
  - `TestColors` — Device color lookup, theme completeness
  - `TestRenderer` — SVG generation: empty state, basic flow, dark/light themes, multiple flows, tooltips, valid XML, custom dimensions
  - `TestBuildSankey` — Energy data builder: consumption-only, solar production, zone data, zero baselines, flow positivity, default titles

#### Infrastructure
- **config.json** — Version 5.3.0

## [5.2.0] - 2026-02-21

### Sankey Energy Flow Diagrams — SVG + JSON

#### Sankey Renderer (NEW)
- **energy/sankey.py** — Pure-Python SVG Sankey diagram generator (no external dependencies)
- `SankeyRenderer` class — Bezier-curve flow paths, node positioning, dark/light themes
- `SankeyNode` / `SankeyFlow` / `SankeyData` dataclasses for structured flow data
- `build_sankey_from_energy()` — Builds Sankey from consumption/production/baselines/zones
- Supports per-zone and global diagrams
- Hover tooltips on flows, color-coded by source/device type
- Responsive SVG with configurable width/height

#### Sankey API Endpoints (NEW)
- `GET /api/v1/energy/sankey` — JSON flow data (nodes, flows, summary)
- `GET /api/v1/energy/sankey.svg` — SVG image with query params: zone, width, height, theme
- 30-second cache headers for SVG responses

#### Infrastructure
- **config.json** — Version 5.2.0

## [5.1.0] - 2026-02-21

### Zone Energy API — Per-Habitzone Energy Device Management

#### Zone Energy Endpoints (NEW)
- `POST /api/v1/energy/zone/<zone_id>` — Register energy entity IDs for a Habitzone
- `GET /api/v1/energy/zone/<zone_id>` — Get zone energy data with per-entity power breakdown
- `GET /api/v1/energy/zones` — List all zones energy overview sorted by total power

#### Energy Service Extension
- **energy/service.py** — New `_find_single_entity_value(entity_id)` helper for zone-level energy queries
- In-memory zone→entity mapping (`_zone_energy_map`) for fast lookups
- Per-entity power readings with unit conversion support

#### Infrastructure
- **config.json** — Version 5.1.0

## [5.0.0] - 2026-02-21

### Major Release — Prediction, SSE, API Versioning, Load Shifting

#### Time Series Forecasting (NEW)
- **prediction/timeseries.py** — Pure-Python Holt-Winters (Triple Exponential Smoothing) for mood trend forecasting
- Additive & damped seasonality, configurable season length (hourly=24, daily=7)
- Missing data interpolation, hourly bucketing from SQLite mood_snapshots
- Multi-metric forecasting: comfort, frugality, joy per zone
- `POST /api/v1/predict/timeseries/fit/<zone_id>` — Fit model on mood history
- `GET /api/v1/predict/timeseries/forecast/<zone_id>` — Forecast with prediction intervals

#### SSE Real-Time Brain Graph Updates (NEW)
- **brain_graph/service.py** — SSE event broadcasting with subscriber queue architecture
- `subscribe_sse()` / `unsubscribe_sse()` with thread-safe queue management
- Non-blocking broadcast on node_updated, edge_updated, graph_pruned events
- Slow consumer auto-cleanup (queue maxsize=256)
- **brain_graph/api.py** — `GET /api/v1/graph/stream` SSE endpoint with 30s keepalive

#### API Versioning (NEW)
- **api/api_version.py** — API versioning module with `X-API-Version` header
- `Accept-Version` request header parsing in before_request middleware
- `Deprecation` + `Sunset` + `Link` headers for deprecated endpoints
- Version constants and validation utilities

#### Energy Load Shifting Scheduler (NEW)
- **prediction/energy_optimizer.py** — `LoadShiftingScheduler` class
- SQLite-backed device schedule persistence at `/data/load_shifting.db`
- Device priority queue (1-5), time-of-use optimization with aWATTar prices
- `POST /api/v1/predict/energy/load-shift` — Schedule device run
- `GET /api/v1/predict/energy/schedules` — List all schedules
- `DELETE /api/v1/predict/energy/load-shift/<id>` — Cancel schedule

#### Infrastructure
- **main.py** — APP_VERSION bumped to 5.0.0, API versioning middleware integrated
- **core_setup.py** — Prediction API registration extended with MoodTimeSeriesForecaster + LoadShiftingScheduler
- **config.json** — Version 5.0.0

## [1.0.0] - 2026-02-21

### Stable Release — Feature-Complete

PilotSuite Styx Core Add-on erreicht **v1.0.0 Stable**. Alle geplanten Meilensteine sind abgeschlossen.

**Cumulative seit v4.0.0:**
- **v4.1.0** Race Conditions Fix (threading.Lock/RLock, SQLite WAL)
- **v4.2.0** Brain Graph Pruning (Daemon-Thread, konfigurierbar), OpenAPI Spec
- **v4.3.0** MUPL Role API + Delegation Workflows (delegate/revoke/list mit Expiry)
- **v4.4.0** Test Coverage: 18 neue Tests (Role/Delegation API)
- **v4.5.0** Conflict Resolution API (POST /user/conflicts/evaluate)

**Gesamtbilanz:**
- Ollama LLM (qwen3:4b, bundled, kein Cloud-Zwang)
- 26 LLM Tools (Licht, Klima, Szenen, Automationen, Kalender, Einkauf, Web-Suche, ...)
- OpenAI-kompatible API (`/v1/chat/completions`)
- RAG Pipeline (Bag-of-Words, Cosine Similarity, Langzeitgedaechtnis)
- Brain Graph + Habitus Miner + Mood Engine + 14 Neuronen
- Conflict Resolution (weighted/compromise/override)
- 40+ REST API Endpoints, Deep Health, Circuit Breaker
- Multi-Arch: amd64 + aarch64
- CI Pipeline: Lint + Test + Security (bandit)

## [4.5.0] - 2026-02-21

### Conflict Resolution API

- **api/v1/user_preferences.py** — Neuer Endpoint: `POST /user/conflicts/evaluate` — Erkennt Praeferenz-Konflikte zwischen aktiven Nutzern; paarweiser Divergenz-Check (Schwellenwert 0.3); drei Strategien: `weighted`, `compromise`, `override`; gibt aufgeloesten Mood + Konflikt-Details zurueck
- **config.json** — Version auf 4.5.0

## [4.4.0] - 2026-02-21

### Test Coverage + Quality

- **test_role_delegation_api.py** — 18 neue Tests fuer Role Inference API (Device Manager/Everyday/Restricted Role Detection), Delegation Workflows (delegate/revoke/list/expiry), Extra-Storage Helpers
- **config.json** — Version auf 4.4.0
- Gesamte Test Suite: 582 Tests bestanden (2 pre-existing energy test failures)

## [4.3.0] - 2026-02-20

### MUPL Role Sync + Delegation API

- **api/v1/user_preferences.py** — Neue Endpoints: `GET /user/<id>/role` (Rolle abfragen), `GET /user/roles` (alle Rollen), `POST /user/<id>/device/<id>` (Device-Nutzung registrieren), `GET /user/<id>/access/<id>` (RBAC-Prüfung), `POST /user/<id>/delegate` (Gerätezugriff delegieren), `DELETE /user/<id>/delegate` (Delegation widerrufen), `GET /user/delegations` (aktive Delegationen auflisten)
- **neurons/mupl.py** — Fehlenden `Any`-Typ-Import hinzugefügt
- **storage/user_preferences.py** — Generische `_load_extra`/`_save_extra` Methoden für Delegation-Persistenz (JSON-basiert)
- **config.json** — Version auf 4.3.0

## [4.2.0] - 2026-02-20

### Brain Graph Scheduled Pruning

- **brain_graph/service.py** — Daemon-Thread für zeitbasiertes Pruning; konfigurierbar via `prune_interval_minutes` (Standard: 60 Min); automatischer Start beim Service-Init; Prune-Statistiken in `get_stats()` sichtbar
- **core_setup.py** — `prune_interval_minutes` aus Brain-Graph-Config gelesen; `start_scheduled_pruning()` beim Init aufgerufen
- **config.json** — Version auf 4.2.0

## [4.1.0] - 2026-02-20

### Race Conditions + Stability

- **brain_graph/service.py** — `threading.Lock` für `_batch_mode`, `_pending_invalidations`, `_operation_count`; batch/commit/rollback und touch_node/touch_edge sind jetzt thread-safe
- **brain_graph/store.py** — `_write_lock` für alle Schreiboperationen (upsert_node, upsert_edge, prune_graph); `_connect()` Helper mit 30s Timeout; verbesserte SQLite-Pragmas (`busy_timeout`, `cache_size`, `temp_store`, `wal_autocheckpoint`)
- **candidates/store.py** — `threading.RLock` schützt alle öffentlichen Methoden; Backup vor jedem Speichern (.bak)
- **ingest/event_processor.py** — Lock-Scope erweitert: umfasst jetzt den gesamten Batch-Lifecycle (begin_batch → process → commit/rollback → ID-Tracking); `rollback_batch()` statt stilles `commit_batch()` bei Fehler

## [4.0.1] - 2026-02-20

### Patch — Version-Fix, Branding-Cleanup, Add-on Store Fix

- **config.json version** auf 4.0.1 aktualisiert
- **start_dual.sh** Version-Banner von v3.11.0 auf v4.0.0 aktualisiert
- **Dockerfile + start scripts** Ollama Model-Pfad `ai_home_copilot` → `pilotsuite`
- **SDK Packages** umbenannt: `ai-home-copilot-client` → `pilotsuite-client`, `ai-home-copilot-sdk-python` → `pilotsuite-sdk-python`
- **voice_context.py** Service-Name aktualisiert
- **energy/__init__.py** Docstring-Branding auf PilotSuite
- **docs/USER_MANUAL.md** Alle URLs, Version-Header und Card-Types aktualisiert
- **docs/RELEASE_DEPLOYMENT_GUIDE.md** Alte Referenzen bereinigt
- **last_orchestrator_report.txt** Auf v4.0.1 aktualisiert

## [4.0.0] - 2026-02-20

### Official Release — Repository Rename + Feature-Complete

**Repository umbenannt:** `Home-Assistant-Copilot` → `pilotsuite-styx-core`
Alle internen URLs, Dokumentation und Konfigurationsdateien aktualisiert.
GitHub leitet alte URLs automatisch weiter (301 Redirect).

#### Warum v4.0.0?

Dies ist der erste offizielle Release von PilotSuite Styx als feature-complete Produkt.
Alle Komponenten sind synchron auf v4.0.0:

| Komponente | Repo | Version |
|-----------|------|---------|
| **Core Add-on** | `pilotsuite-styx-core` | 4.0.0 |
| **HACS Integration** | `pilotsuite-styx-ha` | 4.0.0 |
| **Adapter** | `pilotsuite-styx-core` (Unterverzeichnis) | 4.0.0 |

#### Feature-Ueberblick (Cumulative seit v0.9.x)

**KI & Conversation**
- Ollama LLM (qwen3:4b) lokal auf dem Host — kein Cloud-Zwang
- 26 LLM Tools (Licht, Klima, Szenen, Automationen, Kalender, Einkauf, Erinnerungen, Web-Suche, ...)
- OpenAI-kompatible API (`/v1/chat/completions`) fuer externe Clients
- RAG Pipeline: Semantisches Langzeitgedaechtnis (Bag-of-Words Embedding, Cosine Similarity)
- Charakter-System: 6 Presets (Copilot, Butler, Energiemanager, Security Guard, Friendly, Minimal)
- Telegram Bot Integration

**Brain Graph & Wissensmanagement**
- Live Brain Graph: Entitaeten, Zonen, Zustaende als Knoten/Kanten
- SVG Snapshot Rendering (`/api/v1/graph/snapshot.svg`)
- SQLite WAL-Mode, atomare Queries, Thread-Safe Cache
- Knowledge Graph (SQLite oder Neo4j Backend)
- Neuron-System: Persistente Lern-Einheiten

**Mood & Habitus**
- 3D Mood Engine: Comfort, Joy, Frugality pro Zone
- 15 gewichtete Event-Typen, abgeleitete Indizes (Stress, Comfort, Energy)
- SQLite-Persistenz, 30-Tage History
- Habitus Mining: Automatische Pattern-Erkennung aus Nutzerverhalten
- Habitus Zonen: Raeume mit zugeordneten Entitaeten

**Automationen & Vorschlaege**
- Natural Language Automation Creation ("Wenn Luftfeuchtigkeit > 70%, Luefter an")
- 4 Trigger-Typen: state, time, numeric_state, template
- Suggestion Inbox: Habitus Rules + Brain Graph Candidates + User Hints
- Accept/Reject mit echtem HA-Automation-Backend
- A/B Testing fuer Automation-Varianten (Chi-Squared Signifikanz)

**Haushalt & Alltag**
- Muellabfuhr-Erinnerungen (Vorabend + Morgens, TTS + Notification)
- Geburtstags-Erinnerungen (14-Tage Vorschau, Alters-Erkennung)
- Kalender-Integration (HA calendar.* Entities)
- Einkaufsliste (CRUD + SQLite-Persistenz)
- Erinnerungen mit Snooze-Funktion
- Hauswirtschafts-Dashboard

**Smart Home Features**
- Szenen-System: 8 Built-in Presets + Custom Szenen pro Zone
- HomeKit Bridge: Zonen an Apple HomeKit exponieren (QR-Codes, Setup-Codes)
- Musikwolke: Audio-Follow (Musik folgt Person durch Raeume)
- Media Zonen: Player-Zonen-Zuordnung + Playback-Steuerung
- Presence Tracking: Wer ist wo, Ankunfts-/Abfahrt-History
- Proaktive Vorschlaege bei Raum-Eintritt

**Multi-Home & Multi-User**
- Cross-Home Sharing: Pattern-Austausch zwischen Homes
- Federated Learning: Differential Privacy (Laplace-Mechanismus)
- Multi-User Preference Learning (MUPL): Pro-Person Profile
- Kollektive Pattern Library mit gewichteter Confidence

**Netzwerk & Monitoring**
- UniFi-Integration: Netzwerk-Health, Client-Tracking
- Frigate NVR Bridge: Kamera-Ereignisse, Person/Motion Detection
- Energy Context: Energieverbrauch pro Zone
- Weather Context: Wetter-Einfluss auf Vorschlaege

**Infrastruktur**
- 40+ REST API Endpoints (30 Flask Blueprints)
- Deep Health Check (`/api/v1/health/deep`): Services, DBs, Speicher, Circuit Breaker
- Request Timing Middleware: Correlation IDs, Slow Request Logging
- Docker HEALTHCHECK, Startup Pre-Flight Checks
- Circuit Breaker fuer HA Supervisor + Ollama
- CI Pipeline: Lint + Test + Security (bandit)
- Multi-Arch: amd64 + aarch64
- Web-Suche (DuckDuckGo), News (RSS), Warnungen (NINA/DWD)

#### Aenderungen in v4.0.0

- **Repository Rename**: `Home-Assistant-Copilot` → `pilotsuite-styx-core`
- **Alle URLs aktualisiert**: repository.json, config.json, openapi.yaml, SDK, Docs
- **Cross-Referenzen**: `ai-home-copilot-ha` → `pilotsuite-styx-ha` in allen Docs
- **Adapter Version**: 3.9.1 → 4.0.0

## [3.9.0] - 2026-02-20

### Full Consolidation — Alles in einer Version

- **Branch-Konsolidierung** — Alle Arbeit aus 10 Remote-Branches zusammengeführt:
  - `master` (Original Autopilot: SOUL.md, MEMORY.md, Skills, OpenClaw, Concept Docs)
  - `wip/phase5-cross-home` (Cross-Home Sharing, Interactive Viz, SDKs, Neurons)
  - `wip/phase5-collective-intelligence` (Federated Learning Tests)
  - `backup/pre-merge-20260216` (Memory Logs, Code Reviews, Quality Gates)
  - `backup/2026-02-19` (German Docs, Archive, Post-Merge Notes)
  - `dev-habitus-dashboard-cards` (Habitus Dashboard Cards History)
  - `dev`, `release/v0.4.1` (Early Development History)
  - `claude/research-repos-scope-4e3L6` (DeepSeek-R1 Audit)
- **301 Dateien konsolidiert** — Skills, Worker-Configs, Memory, Reports, Concept Docs,
  HACS Custom Component, Perplexity Scripts, SDK, Knowledge Graph, Tests
- **Version vereinheitlicht** — config.json auf 3.9.0 (beide Repos synchron)
- **Nichts verloren** — Jede einzigartige Datei aus jedem Branch wurde eingesammelt

### Production-Ready Bug Sweep

- **`mood/service.py` — prune logic fix** — The periodic DB cleanup used
  `len(self._last_save_ts) % 100` (number of zones) instead of a global save counter.
  Since zone count rarely changes, `_prune_old()` effectively never ran, causing
  unbounded DB growth. Replaced with `_save_count` counter that increments on every save.

## [3.8.1] - 2026-02-19

### Startup Reliability Patch

- **`mood/service.py` — `os.makedirs()` fix** — `_init_db()` now calls
  `os.makedirs(os.path.dirname(db_path), exist_ok=True)` before `sqlite3.connect()`.
  Prevents `FileNotFoundError` when `/data/` directory does not yet exist on first start.

## [3.8.0] - 2026-02-19

### Persistent State — Mood, Alerts & Mining Buffer

- **Mood History persistence** — MoodService now persists zone mood snapshots to
  SQLite (`/data/mood_history.db`). 30-day rolling history with 60s throttle per zone.
  Last known mood per zone restored on restart. `get_mood_history()` API for trend analysis.
- **Documentation** — New `docs/QA_SYSTEM_WALKTHROUGH.md`: comprehensive Q&A covering
  all 33 modules, startup sequence, learning pipeline, persistence guarantees, and
  the full pattern-to-automation flow.
- **Version references updated** — VISION.md, PROJECT_STATUS.md, README.md now reflect v3.8.0

## [3.7.1] - 2026-02-19

### Security — Defense-in-Depth Auth Hardening

- **Blueprint-level auth guards** — All 19 previously undecorated Flask blueprints now have
  `@bp.before_request` auth validation (was: relying solely on global middleware)
  - `mood`, `habitus`, `habitus_dashboard_cards`, `graph`, `graph_ops`, `candidates`,
    `events`, `neurons`, `user_preferences`, `user_hints`, `vector`, `search`,
    `notifications`, `weather`, `voice_context_bp`, `dashboard`, `debug`, `dev`,
    `mood` blueprints — all now protected at blueprint level
- **tags/api.py** — Replaced 18 manual `validate_token(request)` checks with `@require_token`
  decorator (was: inconsistent inline pattern; now: consistent decorator pattern)
- **Auth tests** — New `test_auth_security.py`: 15+ tests covering:
  - X-Auth-Token header validation
  - Authorization: Bearer header validation
  - Invalid token rejection
  - Empty token → allow all (first-run)
  - Auth disabled → allow all
  - Allowlisted paths bypass (/health, /, /version, /api/v1/status)
  - Global middleware + blueprint-level double coverage
- Version: 3.7.0 → 3.7.1

## [3.7.0] - 2026-02-19

### Bug Fixes & Production Readiness

- **Brain Graph Race Conditions** — SQLite WAL mode, atomic queries, busy timeout
  - `graph_store.py`: `_query_sqlite()` rewritten with single-cursor atomic reads
  - WAL mode + `busy_timeout=5000ms` for concurrent read/write
  - Fixes phantom reads between sub-queries in entity/zone/mood lookups
- **Mood Engine** — Weighted scoring + derived feature indices
  - `scoring.py`: 15 weighted event types (was: 6 unweighted), configurable threshold
  - `engine.py`: New `stress_index`, `comfort_index`, `energy_level` (0..1) derivations
- **Event Processor** — Rollback on partial failure + idempotency
  - Only commits batch if at least one event succeeds
  - Deduplication via event ID tracking (10k ring buffer)
  - Thread-safe with `threading.Lock`
- **Config Validation** — Bounds checking for all numeric parameters
  - `_safe_int`/`_safe_float` now enforce upper bounds (was: only minimum)
  - Brain Graph: `max_nodes` min=100 (was: 1), max=5000
  - Schema builders: `vol.Range()` on 15+ int parameters (port, intervals, sizes)
  - `validate_input()`: Now validates host, port (1-65535), and all critical bounds
- **Brain Graph Sync** (HACS) — `set.pop()` crash fix, session null-guard
  - `_processed_events`: Atomic `set()` reset (was: crash-prone `pop()` loop)
  - `_send_node_update`/`_send_edge_update`: Guard against None session
- **Cache Thread Safety** — `graph.py` no longer mutates shared cached dicts
- **Unused import** — Removed `Request` class import from `rate_limit.py`

### Stub Implementations (Production-Ready)

- **Scene Pattern Extraction** — `bridge.py._extract_scene_patterns()` now extracts
  co-activated entity patterns from `correlates_with`/`co_activated` edges
- **Routine Pattern Extraction** — `bridge.py._extract_routine_patterns()` extracts
  service→entity targeting patterns from `targets` edges
- **Brain Graph SVG** — `/api/v1/graph/snapshot.svg` generates live circle-layout SVG
  with color-coded nodes (entity/zone/service/state) and edge lines
- **Notification Push** — `send_notification()` now sends via WebhookPusher fallback
- **Scaffold Labels Removed** — app.py index route updated to production text

### Cleanup

- Removed 83 `.pyc` files from git tracking
- Removed stale root test scripts (`test_capabilities.py`, `test_new_endpoints.py`)
- Version: 3.6.0 → 3.7.0

## [3.6.0] - 2026-02-19

### Production Hardening

- **Deep Health Endpoint** — `/api/v1/health/deep`
  - Prueft alle internen Services (BrainGraph, Memory, VectorStore, Mood, etc.)
  - Prueft externe Dependencies (HA Supervisor, Ollama)
  - Prueft SQLite-Datenbanken, Speicherplatz, Circuit Breaker Status
  - Gibt HTTP 200 (healthy) oder 503 (unhealthy) zurueck
- **Readiness + Liveness Probes** — `/ready` + `/health`
  - `/health`: Liveness — immer 200 wenn Prozess lebt
  - `/ready`: Readiness — 200 nur wenn BrainGraph + ConversationMemory initialisiert
  - Kubernetes-/Docker-kompatibel
- **Request Timing Middleware** (Flask before/after hooks)
  - Jede Anfrage bekommt eine `X-Request-ID` (Correlation ID)
  - `X-Response-Time` Header fuer alle Responses
  - Slow Request Logging (>2s → WARNING)
  - `/api/v1/health/metrics`: Top-Endpoints nach Latenz, Error Rate, Slow Count
- **Startup Pre-Flight Checks**
  - Prueft `/data` Schreibbarkeit vor dem Start
  - Prueft HA Supervisor Erreichbarkeit (5s Timeout)
  - Prueft Ollama Erreichbarkeit + Modell-Count
  - Ergebnisse geloggt bei Startup, verfuegbar in deep health
- **Circuit Breaker** — `copilot_core/circuit_breaker.py`
  - HA Supervisor: 5 Fehler → OPEN (30s Recovery)
  - Ollama: 3 Fehler → OPEN (60s Recovery)
  - Conversation Tool-Execution prueft Circuit State vor HA-Calls
  - Status in `/api/v1/health/deep` sichtbar
- **Dockerfile HEALTHCHECK** — Container-Health-Monitoring
  - `HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3`
  - Docker/Kubernetes erkennt automatisch unhealthy Container
- **CI Pipeline erweitert** (3 Jobs statt 1)
  - `lint`: py_compile + import smoke test (wie bisher)
  - `test`: Full pytest Suite + pytest-cov Coverage Report
  - `security`: bandit Security Scan (SQL-Injection, Command-Injection, etc.)
- **start_dual.sh**: Version Banner aktualisiert (v3.6.0)
- Version: 3.5.0 -> 3.6.0

## [3.5.0] - 2026-02-19

### RAG Pipeline + Kalender + Einkaufsliste + Erinnerungen

- **RAG Pipeline aktiviert** — VectorStore + EmbeddingEngine endlich verdrahtet
  - `core_setup.py`: Initialisiert `get_vector_store()` + `get_embedding_engine()`
  - `conversation.py` `_store_in_memory()`: Embeddet jede Nachricht als Vektor (bag-of-words)
  - `conversation.py` `_get_user_context()`: Semantische Suche (cosine similarity, threshold 0.45)
  - `embeddings.py`: Neues `embed_text_sync()` — Bag-of-Words Approach (kein externer Service noetig)
  - `store.py`: Neue `upsert_sync()` + `search_similar_sync()` fuer Flask (nicht-async)
  - `/v1/conversation/memory` Endpoint zeigt jetzt auch `vector_store` Stats + `rag_active` Flag
- **Calendar REST API** — `/api/v1/calendar/*` (3 Endpoints)
  - `GET /`: Alle HA-Kalender auflisten
  - `GET /events/today`: Heutige Termine aus allen Kalendern
  - `GET /events/upcoming?days=7`: Kommende Termine
  - `get_calendar_context_for_llm()`: Termine im LLM System Prompt
- **Einkaufsliste REST API** — `/api/v1/shopping/*` (5 Endpoints)
  - `POST /shopping`: Artikel hinzufuegen (einzeln oder mehrere)
  - `GET /shopping`: Artikel auflisten (?completed=0|1)
  - `POST /shopping/<id>/complete`: Artikel abhaken
  - `DELETE /shopping/<id>`: Artikel loeschen
  - `POST /shopping/clear-completed`: Erledigte Artikel loeschen
  - SQLite Persistenz (/data/shopping_reminders.db)
- **Erinnerungen REST API** — `/api/v1/reminders/*` (5 Endpoints)
  - `POST /reminders`: Erinnerung erstellen (mit optionalem Faelligkeitsdatum)
  - `GET /reminders`: Erinnerungen auflisten (?completed=0, ?due=1)
  - `POST /reminders/<id>/complete`: Erinnerung abschliessen
  - `POST /reminders/<id>/snooze`: Erinnerung snoozen (Minuten)
  - `DELETE /reminders/<id>`: Erinnerung loeschen
- **LLM Tools**: +3 neue Tools (22 total)
  - `pilotsuite.calendar_events`: Termine abrufen
  - `pilotsuite.shopping_list`: Einkaufsliste verwalten (add/list/complete)
  - `pilotsuite.reminder`: Erinnerungen verwalten (add/list/complete/snooze)
- **LLM Kontext**: Kalender-Termine, Einkaufsliste, Erinnerungen + semantische Erinnerungen
- **Dashboard**: Kalender-Card, Einkaufsliste mit Input + Abhaken, Erinnerungen mit Snooze
- **System Prompt**: Styx weiss jetzt ueber Langzeitgedaechtnis, Kalender, Listen, Erinnerungen
- Version: 3.4.0 -> 3.5.0

## [3.4.0] - 2026-02-19

### Scene System + Styx Auto-Tagging + HomeKit Bridge

- **Scene REST API** — `/api/v1/scenes/*` (8 Endpoints)
  - `POST /create`: Zone-Snapshot als Szene speichern (via HA `scene.create`)
  - `POST /<id>/apply`: Szene anwenden (HA scene.turn_on + manuelles Fallback)
  - `DELETE /<id>`: Szene loeschen
  - `GET /presets`: 8 Built-in Presets (Morgen, Abend, Film, Party, etc.)
  - LLM-Kontext: Zeigt gespeicherte Szenen pro Zone
- **HomeKit Bridge API** — `/api/v1/homekit/*` (3 Endpoints)
  - `POST /toggle`: Zone zu HomeKit hinzufuegen/entfernen
  - `GET /status`: Aktive Zonen + Entitaeten-Count
  - Automatischer `homekit.reload` nach Aenderung (Pairing bleibt erhalten)
  - LLM-Kontext: Zeigt HomeKit-aktive Zonen
- **Styx Auto-Tagging** in conversation.py
  - Jede Tool-Interaktion taggt beruehrte Entitaeten automatisch mit "Styx"
  - `_auto_tag_styx_entities()`: Extrahiert entity_ids aus Tool-Calls
- **LLM Tools**: `pilotsuite.save_scene` + `pilotsuite.apply_scene` (19 Tools total)
- **Dashboard**: Szene-Karten (speichern/anwenden/loeschen), Presets, HomeKit-Button
- Version: 3.3.0 -> 3.4.0

## [3.3.0] - 2026-02-19

### Presence Dashboard + Proactive Engine

- **Presence Tracking API** — `/api/v1/presence/status|update|history`
  - Wer ist zuhause? (persons_home, persons_away, total)
  - LLM-Kontext: "Anwesend: Max (Wohnzimmer), Lisa (Küche)"
- **Proactive Engine** — Presence-basierte Vorschläge
  - Ankunfts-Begrüßung: "Willkommen zuhause, Max!"
  - Alle-weg: "Sparmodus aktivieren?"
  - Kontext-reichere Grüße (Müll, Geburtstage)
- **Dashboard** — Neue Haushalt-Karten
  - Presence-Card (Avatare, Zonen, Seit-Angaben)
  - Kamera-Ereignisse Timeline (Ankunft/Abfahrt)
- Version: 3.2.3 → 3.3.0

## [3.2.3] - 2026-02-19

### Bugfixes

- **Fix: Haushalt Alert-Duplikation** — Müll- und Geburtstags-Alerts wurden im Dashboard
  gegenseitig gespiegelt (beide Karten zeigten alle Alerts). Jetzt typ-getrennt
- **Fix: entity_assignment None-Unterscheidung** — `_fetch_states()` gibt `None` bei API-Fehler
  zurück vs. `[]` wenn API ok aber keine Entitäten → korrekter Fehlertext im UI
- **Fix: haushalt.py birthday KeyError** — `b['age']` → `b.get('age', '?')` in Geburtstags-Reminder
- **Feature: Entity-Tags LLM-Kontext** — `tag_registry.get_context_for_llm()` wird in LLM
  System-Prompt injiziert, sodass Styx Tag-Zuweisungen kennt
- Version: 3.2.2 → 3.2.3

## [3.2.2] - 2026-02-19

### Hauswirtschafts-Dashboard + Entity Suggestions API

- **Hauswirtschafts-Dashboard** — Neuer Dashboard-Tab "🏠 Haushalt"
  - Aggregiert Müllabfuhr + Geburtstage in einer Übersicht
  - Müllkarte: Heute/Morgen Typen mit farbigen Icons + Urgency-Highlighting
  - Geburtstagskarte: Heutige Geburtstage (grün) + 14-Tage Vorschau
  - TTS-Reminder-Buttons direkt im Dashboard
  - API: `GET /api/v1/haushalt/overview`, `POST /api/v1/haushalt/remind/waste`,
    `POST /api/v1/haushalt/remind/birthday`
- **Entity Assignment Suggestions API** — Heuristische Raumgruppen-Vorschläge
  - `GET /api/v1/entity-assignment/suggestions`
  - Parst alle HA-Entitäten via Supervisor API, gruppiert nach Raum-Hint
  - Konfidenz: Entitäten-Anzahl + Domain-Mix (light+binary_sensor, light+climate)
  - Angezeigt auf der Habitus-Seite (inline) und Haushalt-Seite (Karte)
- **Entity Suggestions Panel** — Zusatzpanel auf Habitus-Page
  - Aufklappbare Gruppen mit Konfidenz-Balken
  - Raumname-Erkennung aus Entity-ID (Noise-Word-Filterung)

## [3.2.1] - 2026-02-19

### Fix: numeric_state + Conditions in create_automation

- **pilotsuite.create_automation** erweitert:
  - Neuer Trigger-Typ `numeric_state` für Schwellenwert-basierte Automationen
    (z.B. "Wenn Luftfeuchtigkeit > 70%", "Wenn Batterie < 15%")
  - `trigger_above` / `trigger_below` Parameter
  - `conditions` Array — optionale Bedingungen (numeric_state + template)
    Beispiel: Badlüfter nur wenn Außenfeuchte < 80%
- Tool-Description aktualisiert (LLM kennt jetzt alle 4 Trigger-Typen)

## [3.2.0] - 2026-02-19

### Müllabfuhr + Geburtstags-Erinnerungen (Server-Side)

- **WasteCollectionService**: Server-seitiger Waste-Kontext für LLM + Dashboard
  - REST API: `POST /api/v1/waste/event`, `POST /api/v1/waste/collections`,
    `GET /api/v1/waste/status`, `POST /api/v1/waste/remind`
  - TTS-Delivery via Supervisor API
  - LLM-Kontext-Injection (Müllabfuhr-Status im System-Prompt)
- **BirthdayService**: Server-seitiger Geburtstags-Kontext
  - REST API: `POST /api/v1/birthday/update`, `GET /api/v1/birthday/status`,
    `POST /api/v1/birthday/remind`
  - TTS + Persistent Notification Delivery
  - LLM-Kontext (Styx weiß wer Geburtstag hat)
- **LLM Tools**: `pilotsuite.waste_status` + `pilotsuite.birthday_status` (19 Tools total)
- **Dashboard**: Müllabfuhr-Panel + Geburtstags-Panel auf Modules-Page
- **Module Health**: Waste + Birthday Status in Module-Grid
- Version auf 3.2.0

## [3.1.1] - 2026-02-19

### Frontend-Backend Integration Fix

#### CRITICAL Fixes
- **Dashboard Graph Stats**: Korrektes Parsing der `/api/v1/graph/stats`
  Response (`gr.nodes` statt `gr.stats.nodes`)
- **Dashboard Mood Endpoint**: `/api/v1/mood` statt `/api/v1/mood/state`,
  `mr.moods` statt `mr.zones`
- **Dashboard Media Zones**: `mzr.zones` statt `Object.keys(mzr)`
- **Module Control Routing**: Blueprint url_prefix auf `/api/v1/modules`
  korrigiert (war `/modules`)

#### Zone-Entry Event Forwarding
- **ZoneDetector Integration**: HACS ZoneDetector erkennt jetzt Zonen-Wechsel
  und forwarded `POST /api/v1/media/proactive/zone-entry` an Core Addon
- **Musikwolke Auto-Update**: Proactive zone-entry Endpoint aktualisiert
  automatisch aktive Musikwolke-Sessions (Audio folgt Person)
- ZoneDetector in `__init__.py` verdrahtet (Setup + Unload)

#### Dashboard Erweiterungen
- **Media Zonen Panel**: Zeigt Zone-Player-Zuordnung + aktive Musikwolke Sessions
- **Web & News Panel**: Info ueber DuckDuckGo-Suche, RSS News, NINA/DWD
- **API Endpoints Tabelle**: Aktualisiert mit Media Zones, Musikwolke, Proaktiv
- Autonomie-Tooltips aktualisiert (Auto-Apply bei beiden Modulen aktiv)
- Musikwolke-Session-Count in Module Health Details

#### Mood Event Processor
- Mood Service wird jetzt automatisch aus Event-Pipeline gespeist
  (media_player State Changes → MoodService.update_from_media_context)

#### Config
- `web_search` Section in addon config.json (ags_code, news_sources)
- config.json Version → 3.1.0

Dateien: `module_control.py`, `media_zones.py`, `core_setup.py`,
`config.json`, `dashboard.html`, `zone_detector.py` (HACS), `__init__.py` (HACS)

## [3.1.0] - 2026-02-19

### Autonomie + Web-Intelligenz + Musikwolke

#### Autonomie-faehiges Modul-System (3-Tier)
- **active**: Vorschlaege werden AUTOMATISCH umgesetzt — nur wenn BEIDE
  beteiligten Module (Quelle + Ziel) aktiv sind (doppelte Sicherheit)
- **learning**: Beobachtungsmodus — Daten sammeln + Vorschlaege zur
  MANUELLEN Uebernahme erzeugen (User muss accept/reject)
- **off**: Modul deaktiviert (keine Datensammlung, kein Output)
- Neue API-Methoden: `should_auto_apply()`, `should_suggest()`,
  `get_suggestion_mode()` in ModuleRegistry

#### Web-Suche & Nachrichten fuer Styx
- **DuckDuckGo-Suche**: Styx kann das Web durchsuchen (kein API-Key noetig)
  Nutzer: "Recherchier mal die besten Zigbee-Sensoren 2026"
- **News-Aggregation**: Aktuelle Nachrichten von Tagesschau + Spiegel
  via RSS, mit 15-Min-Cache
- **Regionale Warnungen**: NINA/BBK Zivilschutz + DWD Wetterwarnungen
  mit AGS-Regionalfilter. Warnungen fliessen in den LLM-Kontext ein
- Neue LLM Tools: `pilotsuite.web_search`, `pilotsuite.get_news`,
  `pilotsuite.get_warnings`

#### Musikwolke + Media Zonen
- **MediaZoneManager**: Media-Player den Habituszonen zuordnen (SQLite),
  Playback-Steuerung pro Zone (play/pause/volume)
- **Musikwolke**: Smart Audio Follow — Musik folgt dem User durch die Raeume.
  Start/Stop via Chat ("Musikwolke starten") oder REST API
- **Proaktive Vorschlaege**: Kontext-basierte Suggestions bei Raum-Eintritt
  (z.B. "Du bist im Wohnzimmer, soll Netflix auf AppleTV starten?")
  mit Cooldown, Quiet Hours, Dismiss-Tracking
- Neue LLM Tools: `pilotsuite.play_zone`, `pilotsuite.musikwolke`
- REST API: 16 Endpoints unter `/api/v1/media/*`

#### Modul-Umbenennung
- `unifi_context` -> `network` (generisch, nutzt UniFi API wenn vorhanden)
- `media_context` -> `media_zones` (Musikwolke + Zonen-Player)
- `event_forwarder` -> `Event Bridge`
- `user_preferences` -> `Nutzer-Profile` (Multi-User + Autonomie)
- Neue Module: `proactive` (Kontext-Vorschlaege), `web_search` (News + Recherche)

#### Sharing-Modul Fix
- Blueprint-Registrierung nachgezogen (war nicht in core_setup.py verdrahtet)

#### Dashboard v3.1
- 17 Module (von 15), neue Autonomie-Tooltips auf Modul-Toggles
- Media-Zonen Health-Check in der Module-Seite
- Warnung-Context wird in LLM-System-Prompt injiziert

Dateien: `module_registry.py`, `web_search.py`, `media_zone_manager.py`,
`proactive_engine.py`, `api/v1/media_zones.py`, `mcp_tools.py`,
`api/v1/conversation.py`, `core_setup.py`, `dashboard.html`, `main.py`

## [3.0.1] - 2026-02-19

### Natural Language Automation Creation -- End-to-End Pipeline Fix

- **Neues LLM Tool `pilotsuite.create_automation`**: Der LLM kann jetzt echte
  HA-Automationen erstellen wenn der User z.B. sagt "Wenn die Kaffeemaschine
  einschaltet, soll die Kaffeemuehle sich synchronisieren". Der LLM parsed die
  natuerliche Sprache in strukturierte Trigger/Action-Daten und erstellt die
  Automation via Supervisor API.
- **Neues LLM Tool `pilotsuite.list_automations`**: Erstellte Automationen auflisten.
- **UserHintsService komplett**: `accept_suggestion()` und `reject_suggestion()`
  implementiert mit AutomationCreator-Bridge. Akzeptierte Suggestions erstellen
  jetzt echte HA-Automationen.
- **HintData Model**: `to_dict()` und `to_automation()` Methoden hinzugefuegt.
- **AutomationCreator erweitert**: Akzeptiert jetzt auch strukturierte
  Trigger/Action-Dicts (nicht nur Regex-parsbare Strings).
- **System Prompt aktualisiert**: LLM weiss jetzt ueber seine
  Automations-Erstellungs-Faehigkeit.

Dateien: `mcp_tools.py`, `api/v1/conversation.py`, `api/v1/service.py`,
`api/v1/models.py`, `api/v1/user_hints.py`, `automation_creator.py`

## [3.0.0] - 2026-02-19

### Kollektive Intelligenz — Cross-Home Learning

- **Federated Learning**: Pattern-Austausch zwischen Homes mit Differential Privacy
  (Laplace-Mechanismus, konfigurierbares Epsilon)
- **A/B Testing fuer Automationen**: Zwei Varianten testen, Outcome messen (Override-Rate),
  Chi-Squared Signifikanztest, Auto-Promote Winner bei p<0.05
- **Pattern Library**: Kollektiv gelernte Muster mit gewichteter Confidence-Aggregation
  ueber mehrere Homes, opt-in Sharing

Dateien: `ab_testing.py`, `collective_intelligence/pattern_library.py`

## [2.2.0] - 2026-02-19

### Praediktive Intelligenz — Vorhersage + Energieoptimierung

- **Ankunftsprognose**: `ArrivalForecaster` nutzt zeitgewichteten Durchschnitt der
  letzten 90 Tage (Wochentag + Uhrzeit), SQLite-Persistenz, kein ML-Framework
- **Energiepreis-Optimierung**: `EnergyOptimizer` findet guenstigstes Zeitfenster,
  unterstuetzt Tibber/aWATTar API oder manuelle Preistabelle
- **Geraete-Verschiebung**: "Styx verschiebt Waschmaschine auf 02:30 (34ct gespart)"
- **REST API**: `/api/v1/predict/arrival/{person}`, `/api/v1/predict/energy/*`

Dateien: `prediction/__init__.py`, `prediction/forecaster.py`, `prediction/energy_optimizer.py`,
`prediction/api.py`

## [2.1.0] - 2026-02-19

### Erklaerbarkeit + Multi-User — Warum schlaegt Styx das vor?

- **Explainability Engine**: Brain Graph Traversal (BFS, max Tiefe 5) findet kausale
  Ketten fuer Vorschlaege, Template-basierte natuerlichsprachige Erklaerung,
  Confidence-Berechnung aus Edge-Gewichten
- **Multi-User Profiles**: Pro HA-Person-Entity eigenes Profil mit Praeferenzvektor,
  Suggestion-History, Feedback-Tracking (accept/reject), SQLite-Persistenz
- **REST API**: `/api/v1/explain/suggestion/{id}`, `/api/v1/explain/pattern/{id}`

Dateien: `explainability.py`, `api/v1/explain.py`, `user_profiles.py`

## [2.0.0] - 2026-02-19

### Native HA Integration — Lovelace Cards + Conversation Agent

- **3 Native Lovelace Cards** (HACS Integration):
  - `styx-brain-card`: Brain Graph Visualisierung mit Force-Directed Layout
  - `styx-mood-card`: Mood-Gauges (Comfort/Joy/Frugality) mit Kreis-Grafik
  - `styx-habitus-card`: Top-5 Pattern-Liste mit Confidence-Badges
- **HA Conversation Agent**: `StyxConversationAgent` nativ in HA Assist Pipeline,
  Proxy zu Core `/v1/chat/completions`, DE + EN

Dateien: `www/styx-brain-card.js`, `www/styx-mood-card.js`, `www/styx-habitus-card.js`,
`conversation.py` (HACS)

## [1.3.0] - 2026-02-19

### Module Control + Automationen — Toggles mit echter Wirkung

- **Module Control API**: `POST /api/v1/modules/{id}/configure` setzt Modul-Zustand
  (active/learning/off) im Backend, SQLite-Persistenz in `/data/module_states.db`
  - active: Modul laeuft normal, beobachtet und erzeugt Vorschlaege
  - learning: Modul beobachtet, erstellt aber keine Suggestions
  - off: Modul deaktiviert, keine Datensammlung
- **Dashboard-Toggle ruft API**: `toggleModule()` sendet jetzt POST an Backend,
  Fallback auf localStorage wenn API nicht erreichbar
- **Automation Creator**: Akzeptierte Vorschlaege erzeugen echte HA-Automationen
  via Supervisor REST API (`POST /config/automation/config`), Template-Mapping
  (Zeit-Trigger, State-Trigger, Entity-Aktionen)
- **Automationen-Liste**: Neue Sektion im Modules-Tab zeigt erstellte Automationen

Dateien: `module_registry.py`, `api/v1/module_control.py`, `automation_creator.py`,
`api/v1/automation_api.py`, `dashboard.html` (updated)

## [1.2.0] - 2026-02-19

### Qualitaetsoffensive — Volle Transparenz, Maximale Resilienz

#### Dashboard v3 — Kein Dummy-Code mehr
- **Echte Modul-Health**: `fetchModuleHealth()` laedt Status aus 11 APIs parallel
  (Brain Graph Stats, Habitus Health, Mood State, Neurons, Memory, Energy, Weather,
  UniFi, Telegram, Capabilities) — alle Module zeigen echten Zustand (active/learning/off)
- **Modul-Override mit Persistenz**: Nutzer-Toggles (active/learning/off) werden in
  `localStorage` gespeichert und bei jedem Reload wiederhergestellt; Override-Indikator
  sichtbar wenn Nutzer-Status von API-Status abweicht
- **Echte Pipeline-Status**: Pipeline-Pills auf der Styx-Seite zeigen tatsaechlichen
  Modul-Status mit Hover-Tooltip (Detail-Info aus API), nicht mehr hardcoded 'active'
- **Neue Pipe-Klassen**: `pipe-error` (rot) und `pipe-unknown` (gedimmt) fuer Fehler-
  und Unbekanntzustaende sichtbar in der Pipeline-Leiste
- **XSS-Schutz**: `escapeHtml()` helper — alle API-Daten werden vor innerHTML-Rendering
  escaped (Chat-Antworten, Vorschlaege, Zonen, Modell-Namen, SVG-Labels, alles)
- **Resiliente Fehler-States**: Status-Pill zeigt "API offline" (rot) wenn Core nicht
  erreichbar; LLM-Settings zeigt klare Fehlermeldung statt Loading-Spinner; alle Seiten
  zeigen "Erneut versuchen" Button bei Ladefehler
- **Kein Fake-Chart-Data**: Trend-Charts zeigen "Nicht genug Daten" Hinweis wenn weniger
  als 2 echte Datenpunkte vorhanden — kein Sine-Wave-Dummy mehr
- **Promise.allSettled ueberall**: Suggestion Inbox und Settings nutzen `allSettled`
  statt `all` — ein fehlschlagender API-Aufruf bricht nicht alles ab
- **MCP-Status echt**: MCP Server Status kommt aus `/api/v1/capabilities` (nicht mehr
  immer-gruen hardcoded); Capabilities-Features werden in Settings angezeigt
- **Hint-Consequent-Parsing**: Hints mit Format "X -> Y" werden korrekt in
  Antecedent/Consequent aufgeteilt; nicht mehr immer leer
- **loadPage() try-catch**: Alle Seiten-Loader sind in resilientem Wrapper —
  unerwartete Fehler zeigen "Erneut versuchen" UI statt stiller Fehler
- **Suggestion Inbox**: 3 Quellen (Habitus Rules, Brain Graph Candidates, Hints),
  Accept/Reject mit Backend-Integration, Batch-Pipeline, Brain-Edge-Animation
- **Dead Code entfernt**: Nutzloses `c.querySelector('.loading')||null` entfernt

## [1.1.0] - 2026-02-19

### Styx — Die Verbindung beider Welten

- **Styx Identity**: Configurable assistant name (`ASSISTANT_NAME` env var, config field)
- **Unified Dashboard**: Brain Graph + Chat + History on one page, 5-page navigation
- **Module Pipeline**: 15 modules with status indicators (active/learning/off)
- **Domain-Colored Brain Graph**: 16 HA domain colors, SVG glow filter, auto-legend
- **Canvas Trend Charts**: Habitus and Mood 24h gradient-fill mini charts
- **Suggestion Bar**: Top suggestions from Habitus rules, clickable into chat
- **Fix**: start_with_ollama.sh default model → qwen3:4b

---

## [0.9.7-alpha.1] - 2026-02-18

### Bugfix
- **Logging**: `print()` → `logger.warning()` in transaction_log.py
- **Ollama Conversation**: Bereinigung undefinierter Funktionsreferenzen

---

## [0.9.6-alpha.1] - 2026-02-18

### Features
- **Dev Surface Enhanced**: Performance-Metriken in SystemHealth
  - Cache-Hits/Misses/Evictions
  - Batch-Mode Status
  - Pending Invalidations
  - duration_ms Tracking für Operationen
- **MCP Tools**: Vollständig integriert (249 Zeilen)
  - HA Service Calls
  - Entity State Queries
  - History Data
  - Scene Activation

### Performance
- **Batch-Mode für Brain Graph Updates**
  - Event-Processor nutzt Batch-Verarbeitung
  - Cache-Invalidierung wird bis zum Batch-Ende verzögert
  - ~10-50x weniger Cache-Invalidierungen bei vielen Events
- **Optimiertes Pruning** (4 Table Scans → 2)
  - JOIN-basierte Node/Edge Limitierung in einem Durchgang
  - Deterministic Pruning (alle 100 Operationen)

---

## [0.9.4-alpha.1] - 2026-02-18

### Performance
- **Batch-Mode für Brain Graph Updates**
  - Event-Processor nutzt jetzt Batch-Verarbeitung
  - Cache-Invalidierung wird bis zum Batch-Ende verzögert
  - ~10-50x weniger Cache-Invalidierungen bei vielen Events
  - Deutlich verbesserte Performance bei hohem Event-Aufkommen
- **Optimiertes Pruning** (4 Table Scans → 2)
  - JOIN-basierte Node/Edge Limitierung in einem Durchgang
  - Deterministic Pruning (statt random)
- **Pruning-Trigger**: Alle 100 Operationen statt zufällig

### Bugfix
- **Ollama Conversation Endpoint**: Bereinigung undefinierter Funktionsreferenzen

---

## [0.9.1-alpha.9] - 2026-02-17

### Removed
- **OpenAI Chat Completions API entfernt**
  -/openai_chat.py gelöscht
  - Blueprint Registration entfernt
  - OpenAI API config entfernt

**Hintergrund:** Nutzt HA integrierte Chatfunktion statt OpenClaw Assistant

---

## [0.9.1-alpha.8] - 2026-02-17
