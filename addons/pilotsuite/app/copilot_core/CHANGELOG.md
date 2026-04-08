# Add-on Changelog – PilotSuite Core

This file exists so Home Assistant can show an add-on changelog.
For full history, see the repository-level `CHANGELOG.md`.

## 7.8.8
- LLM-Routing erweitert: Primary/Secondary Provider (`offline`/`cloud`) mit robustem Fallback.
- Neue API-Endpunkte fuer Routing/Katalog:
  - `GET /chat/models/catalog`
  - `GET /chat/routing`
  - `POST /chat/routing`
- Dashboard Settings: getrennte Offline/Cloud-Modellauswahl + Routing-Steuerung.
- Cloud-Defaults aktualisiert: `https://ollama.com/v1` + `gpt-oss:20b`.

## 7.8.7
- Dashboard ingress detection unterstützt jetzt beide HA-Routen
  (`/api/hassio_ingress/...` und `/hassio/ingress/...`).
- Styx-Chat im Dashboard kann jetzt das Modell direkt umschalten (persistente Auswahl).
- Runtime-Versioning synchronisiert: Add-on-Version und `/usr/src/app/VERSION` sind wieder konsistent.

## 7.8.6
- Add-on-Info (`DOCS.md`) enthält jetzt eine exakte Produktions-Installationsanleitung
  inklusive Lovelace-YAML, Cloud-Fallback-Setup und Smoke-Checks.
- README verweist explizit auf den Add-on-Info-Screen als primäre Setup-Quelle.
- Dashboard-Template entfernt statische interne UI-Versionsbeschriftung.

## 7.8.5
- Dashboard zeigt keine feste `v1.0.0` Platzhalter-Version mehr.
- Versionsanzeige ist jetzt strikt runtime-basiert (aus `/chat/status`) oder `--`.
- Klarstellung: `X-API-Version` ist die API-Schema-Version, nicht die Add-on-Release-Version.

## 7.8.4
- Styx Dashboard nutzt jetzt persistente Chat-History via `/api/v1/hub/brain/activity/chat`.
- Neuer Chat-Clear-Button im Dashboard.
- Neue Modul-Konfigurationsoberfläche im Module-Tab (Habitus Miner + Brain Activity Timeouts).
- Dashboard-Health/Mood-Routing robuster für unterschiedliche API-Antwortformate.

## 7.8.3
- Dashboard erkennt HA-Ingress-Pfade jetzt korrekt und routed API-Calls nicht mehr ins HA-Root.
- Modul-Toggles synchronisieren mit dem Backend (`/api/v1/modules/`) als Source-of-Truth.
- Fehlgeschlagene Modul-Konfigurationen rollen den UI-Zustand automatisch zurück.
- Settings zeigt neue `API Route` Diagnose (Ingress/Direct).

## 7.8.2
- **Onyx Bridge API**: neue Endpunkte unter `/api/v1/onyx/*` fuer produktive Agenten-Integration.
- **Deterministische HA-Aktionen**: `POST /api/v1/onyx/ha/service-call` mit optionalem State-Readback.
- **OpenAPI Actions aktualisiert**: `docs/integrations/onyx_styx_actions.openapi.yaml` erweitert (Onyx Bridge + Habitus-Zonen-Flow).
- **Onyx Setup Guide**: konkrete Produktionsfelder fuer `192.168.30.18` in `docs/ONYX_INTEGRATION.md`.
- **E2E Tooling**: `tools/onyx_styx_e2e.sh` fuer schnellen Live-Pipeline-Test.

## 7.8.0
- **Zero-Config Enhancement**: Verbesserte Auto-Discovery fuer Core-Endpoint
- **Entity Auto-Discovery**: Media-Player Erkennung (Sonos, Apple TV, Smart TV)
- **Zone Inference**: Automatische Zonen-Erkennung aus Entity-Namen und HA Areas
- **Self-Heal**: Erweiterte automatische Wiederherstellung bei Ausfaellen
- **Vision Update**: Zero-Config und Maximaler-User-Comfort als Ziel

## 7.7.27
- **Version Sync**: auf v7.7.27 angehoben (Matching mit HA Integration)
- **aiohttp Session Leak Fix**: HA Integration nutzt jetzt async_get_clientsession() statt direkte ClientSession

## 7.7.26
- **Version Sync**: auf v7.7.26 angehoben (Matching mit HA Integration)
- **Module Registry Hardening**: Runtime-Modulregistrierung jetzt robust fuer alle _MODULES-Eintraege
- **ML Context Lifecycle**: MLContextModule jetzt kompatibel mit CopilotRuntime Lifecycle-Schema
- **Dashboard Wiring**: Automatische Lovelace-Dashboard-Registrierung inkl. Habitus v2
- **Device Dedup**: Legacy-Device Cleanup erweitert, verwaiste Devices werden entfernt
- **Runtime Stability**: Unload-Rueckgaben normalisiert, OptionsFlow stabilisiert
- **Connection Normalization**: Host/Token-Persistenz ueber Updates stabilisiert

## 7.7.19
- Habitus-Dashboard nutzt jetzt die korrekten Hub-Zonen-Endpunkte (`/api/v1/hub/zones*`) statt Mining-Config.
- Zonen lassen sich wieder anlegen (inkl. Mehrfach-Raumauswahl im Dropdown).
- Falls keine Räume vorhanden sind: optionaler Fallback über manuelle Entitätsliste (synthetischer Raum wird automatisch registriert).
- Raumliste im Dashboard ist jetzt aktualisierbar (Reload-Button) und kann initial aus Entity-Assignment-Vorschlägen vorbefüllt werden.

## 7.7.18
- Dashboard nutzt jetzt automatisch den konfigurierten Auth-Token fuer alle API-Calls.
- Chat/Suggestions/Szenen/HomeKit/Habitus/Module im Dashboard funktionieren damit auch bei aktivierter API-Authentifizierung (`auth_token` gesetzt).

## 7.7.17
- **Ollama Cloud URL Hardening**: `ollama.com` Eingaben werden robust auf `https://ollama.com/v1` normalisiert.
- **Cloud Model Mapping**: unpassende OpenAI-Modelnamen (z. B. `gpt-4o-mini`) werden fuer Ollama Cloud automatisch auf `gpt-oss:20b` korrigiert.
- **Regression-Tests**: neue Tests fuer URL-Normalisierung und Modell-Mapping.

## 7.7.16
- **LLM Guardrail**: cloud-typische Modellnamen im lokalen `OLLAMA_MODEL` werden automatisch auf `qwen3:0.6b` korrigiert.
- **Status Diagnose**: neue Felder `ollama_model_configured` und `ollama_model_overridden` fuer einfacheres Troubleshooting.

## 7.7.15
- **Default LLM**: `qwen3:0.6b` ist jetzt der Standard fuer neue Installationen.
- **Runtime Fallbacks**: Startup-Skripte, Conversation-API, Agent-Status und LLM-Provider verwenden konsistent `qwen3:0.6b` als Default.
- **Docs Sync**: README/DOCS/API/Architektur auf die neue Modellstrategie aktualisiert.

## 7.7.14
- **Self-Heal API**: `POST /api/v1/agent/self-heal` hinzugefuegt (LLM config reload + best-effort model pull).
- **Zero-Config Hardening**: Agent-Status liest jetzt korrekt auch `conversation_*` Flat-Optionen.
- **LLM Routing**: Cloud-Modelnamen ohne Cloud-Fallback werden direkt auf lokales Modell gemappt (weniger 404-Noise).
- **API Wiring**: Vector API `/api/v1/vector/*` explizit registriert.

## 7.7.13
- **Agent API**: `/api/v1/agent/*` Blueprint registriert (kein 404 mehr bei Agent-Status/Verify).
- **Model Alias**: `pilotsuite/default/auto/local/ollama` werden auf das konfigurierte Modell aufgeloest.
- **Versioning**: Runtime-Version nutzt `COPILOT_VERSION/BUILD_VERSION` mit Datei-Fallback.

> Hinweis: Aeltere Eintraege unterhalb dieser Linie stammen aus Legacy-Historie vor der aktuellen `7.7.x` Release-Linie.

## 3.9.1
- **HA Conformity** — Version sync with HACS integration
- **Branding** — Port description updated to PilotSuite
- **Security** — Token validation confirmed working (hmac.compare_digest)

## 0.8.5
- **Phase 5 Feature: Cross-Home Sync API v0.2**
  - `/api/v1/sharing/discover` - mDNS peer discovery
  - `/api/v1/sharing/share` - Entity sharing registration
  - `/api/v1/sharing/unshare` - Stop sharing entity
  - `/api/v1/sharing/sync` - Real-time state synchronization
  - `/api/v1/sharing/resolve` - Conflict resolution strategies
- **Phase 5 Feature: Collective Intelligence API v0.2**
  - `/api/v1/federated/models` - Local model registration
  - `/api/v1/federated/patterns` - Pattern creation and sharing
  - `/api/v1/federated/peers` - Peer discovery
  - `/api/v1/federated/aggregates` - Aggregate stats from collective
- **Phase 5 Feature: Brain Graph Panel v0.8**
  - Interactive HTML generation with D3.js visualization
  - Zoom/pan support for large graphs (200 nodes, 400 edges)
  - Node filtering by kind, zone, or search
  - Click nodes for detailed metadata display
  - Local-only rendering (no external dependencies)
- **Core API**: `/api/v1/sharing/*` and `/api/v1/federated/*` endpoints fully documented
- **Tests**: 44+ tests passing ✅ (federated_learning + privacy_preserver fixed)

## 0.5.0
- **Knowledge Graph Module**: Neo4j-backed graph storage with SQLite fallback
  - Captures relationships between entities, patterns, moods, and contexts
  - Node types: ENTITY, DOMAIN, AREA, ZONE, PATTERN, MOOD, CAPABILITY, TAG, TIME_CONTEXT
  - Edge types: BELONGS_TO, HAS_CAPABILITY, HAS_TAG, TRIGGERS, CORRELATES_WITH, ACTIVE_DURING, RELATES_TO_MOOD
  - Dual backend: Neo4j (preferred) or SQLite (fallback)
- **Graph Builder**: Build graph from HA states, entities, areas, and tags
- **Pattern Importer**: Import Habitus A→B rules as PATTERN nodes
- **API Endpoints**: `/api/v1/kg/*` for graph queries and management
  - `GET /api/v1/kg/stats` - Graph statistics
  - `GET/POST /api/v1/kg/nodes` - Node CRUD
  - `GET/POST /api/v1/kg/edges` - Edge CRUD
  - `POST /api/v1/kg/query` - Custom graph queries
  - `GET /api/v1/kg/entity/{id}/related` - Get related entities
  - `GET /api/v1/kg/zone/{id}/entities` - Get zone entities
  - `GET /api/v1/kg/mood/{mood}/patterns` - Get mood-related patterns
  - `POST /api/v1/kg/import/entities` - Import from HA states
  - `POST /api/v1/kg/import/patterns` - Import from Habitus miner
- Environment variables for Neo4j:
  - `COPILOT_NEO4J_URI` (default: none, uses SQLite)
  - `COPILOT_NEO4J_USER` (default: neo4j)
  - `COPILOT_NEO4J_PASSWORD`
  - `COPILOT_NEO4J_ENABLED` (default: true)
  - `COPILOT_KG_SQLITE_PATH` (default: /data/knowledge_graph.db)

## 0.2.7
- Brain Graph Ops: `POST /api/v1/graph/ops` (v0.1: touch_edge; idempotent; allowlist: observed_with, controls).

## 0.2.6
- Dev Surface: `GET /api/v1/dev/status`.
- Diagnostics Contract: `GET /api/v1/dev/support_bundle` liefert ein privacy-first, bounded ZIP.
- DevLogs ingest: Payloads werden vor Persistenz best-effort sanitisiert.
- Graph→Candidates Bridge: `GET /api/v1/candidates/graph_candidates` (Preview, bounded).

## 0.2.5
- Brain Graph wird jetzt aus eingehenden `/api/v1/events` Batches gefüttert (privacy-first, bounded).
- Capabilities zeigen `brain_graph.feeding_enabled`.

## 0.2.4
- Events ingest ist jetzt idempotent (TTL+LRU Dedupe); Retries erzeugen keine doppelten Events.
- Neu: Brain Graph Skeleton API (v0.1) unter `/api/v1/graph/state` + `snapshot.svg` (Placeholder).

## 0.2.3
- Logs the listening port on startup.
- `/health` includes the effective port.
- Respects add-on `log_level` option.

## 0.2.2
- Default port changed from 8099 to 8909.

## 0.2.1
- Fix startup crash (DevLogs used current_app at import time).
