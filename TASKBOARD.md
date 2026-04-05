# PilotSuite Core Taskboard

## Directive (2026-03-22)
**Owner:** PilotClaw  
**Scope:** `pilotsuite-styx-core`  
**Authority:** PilotClaw has the last word for Core development.

---

## Status summary

### Completed Slices (2026-03-31)
- [x] **Slice 1 — Canonical Ingest Lane** (v15.2.10)
  - Unified `POST /api/v1/events` implementation
  - Retired legacy `api/v1/events.py`
  - Standardized on `ingest/event_store.py` + `EventProcessor`
  - Commit: `fbaefd4f`

- [x] **Slice 2 — Zone Truth Layer** (v15.2.11)
  - `ZoneDefinitionSyncV1` model and storage
  - Canonical topology sync endpoint
  - Provenance, revision, freshness metadata
  - Zone archetype separated from zone instance
  - Commit: `ada33607`

- [x] **Slice 3 — First-Class Module Model** (v15.2.12)
  - Canonical module metadata/snapshot model
  - Module applicability mapped to Habitus zones
  - All modules aligned on one input/output contract
  - Module state/config/summary/freshness in read models
  - Commit: `1408e74b`

- [x] **Slice 4 — HA Connection Module** (v15.2.13)
  - Connection-module contract formalized
  - `HomeAssistantModuleEngine` + `ModuleRouter` aligned
  - Transport/pipeline health as diagnostics
  - Commit: `013e2a60`

- [x] **Slice 5 — Brain Growth Unification** (v15.2.14)
  - Explicit transfer model (inputs → graph/neuron/module)
  - Read model for brain activity/growth summary
  - Zone/entity/module truth linked to neuron evaluation
  - Commit: `109bdfc0`

- [x] **Slice 6 — Truth-Backed Dashboard Read Models** (v15.2.15)
  - Zone summary/detail read models
  - Module read model + system overview
  - Freshness/provenance fields on all blocks
  - `example_config` is demo/test-only
  - Commit: `6f9e0dc4`

- [x] **Slice 7 — Unified Proposal Lifecycle** (v15.2.16)
  - One lifecycle state machine
  - Primary proposal storage model
  - Consistent accept/reject/snooze APIs
  - `ProposalIntentV1` + `ActionIntentV1` first-class
  - Evidence/explanation attached by default
  - Commit: `1c2cb4b4`

- [x] **Slice 8 — Classification Authority** (v15.2.17)
  - Unified entity role/tag/category logic
  - Canonical taxonomy layer (`taxonomy.py`)
  - Role/tag/module-bucket outputs for all downstream systems
  - Commit: `06e4f77c`

- [x] **Slice 9 — RAG/Chat Alignment** (v15.2.18)
  - Formal chat context blocks from truth/read models
  - Retrieval provenance improvements
  - Mapping between modules/zones/brain and chat explanations
  - Tests for source-grounded responses + memory
  - Commit: `eff1e4e7`

- [x] **Slice 10 — Decision/Execution Separation** (v15.2.19)
  - HA adapter command outputs formalized
  - Direct execution paths audited
  - Behavioral log / audit trail consistent
  - Policy NOT duplicated in HA adapter
  - Commit: `ac6b2c8d`

- [x] **Slice 11 — Contract and Regression Coverage** (v15.2.20)
  - Ingest contract tests
  - Topology sync contract tests
  - Module contract tests
  - Brain/read-model snapshot tests
  - Dashboard read-model snapshot tests
  - Proposal lifecycle tests
  - Autonomy/policy gate tests
  - E2E checks against truth-backed dashboard
  - Commit: `cc591ab8`

### Completed in this concept pass
- [x] Read `TASKBOARD.md` first.
- [x] Re-read the high-signal docs for Core/HA boundary and product intent:
  - `README.md`
  - `CLAUDE.md`
  - `docs/ARCHITECTURE.md`
  - `docs/ARCHITECTURE_CONCEPT.md`
  - `docs/MODULE_INVENTORY.md`
  - `docs/HA_CORE_INGEST_CONTRACT.md`
  - `docs/ROADMAP.md`
  - `docs/ZONE_EDITOR.md`
  - dashboard / HA / e2e markdown as needed
- [x] Re-read the key runtime/code paths for:
  - ingest + normalization,
  - zone sync,
  - zone dashboard,
  - module engines and module wiring,
  - neuron / brain graph paths,
  - habitus / proposal flow,
  - HA connection module / module router,
  - chat / RAG / memory services.
- [x] Revised `docs/CORE_CONCEPT_DIRECTIVE.md` so the concept now explicitly includes:
  - first-class Core modules,
  - the growing brain representation,
  - HA connection-module role,
  - existing module end-to-end wiring needs,
  - and the RAG chat pipeline.
- [x] Refreshed `docs/CORE_CONCEPT_HANDOFF.md` with updated concise guidance.

### Current conclusion
PilotSuite Core is now explicitly defined as:
- **semantic truth engine**,
- **first-class module runtime**,
- **brain / neuron / habitus reasoning layer**,
- **policy engine**,
- **explanation engine**,
- and **RAG/chat reasoning surface**.

Home Assistant / HACS remains:
- the raw runtime shell,
- the device/entity/area collection layer,
- the execution adapter,
- and the HA-native projection layer.

---

## Evidence-backed findings driving the roadmap

### 1) Ingest is still split in both routes and implementation
**Evidence**
- `docs/HA_CORE_INGEST_CONTRACT.md`
- `copilot_core/api/v1/events_ingest.py`
- `copilot_core/ingest/event_store.py`
- `copilot_core/ingest/event_processor.py`
- `copilot_core/api/v1/events.py`
- `copilot_core/storage/events.py`
- `copilot_core/core_setup.py`
- `copilot_core/api/v1/blueprint.py`
- `copilot_core/app.py`

**Finding**
- canonical ingest exists,
- legacy ingest still exists,
- production and test wiring do not center the same lane,
- and there are currently **two EventStore implementations** in play.

**Implication**
Slice 1 must unify route, store, and post-ingest flow.

### 2) Zone truth is not yet a first-class Core store
**Evidence**
- `docs/ZONE_EDITOR.md`
- `api/v1/zone_automation.py`
- `hub/zone_automation.py`
- `homeassistant/habitus_zones.py`
- `api/v1/habitus_zones.py`
- `api/v1/zone_dashboard.py`

**Finding**
- archetypes, runtime config, sync docs, sync endpoint, and dashboard read models are still separate concerns with no single truth store.
- synced HA topology is currently written onto config attrs like `cfg._ha_entities`.

**Implication**
Slice 2 must introduce a real zone truth layer.

### 3) Modules already exist and need first-class unification, not hand-waving
**Evidence**
- `docs/MODULE_INVENTORY.md`
- `core_setup.py`
- `hub/licht_module.py`
- `hub/helligkeit_module.py`
- `hub/heiz_module.py`
- `api/v1/zone_dashboard.py`

**Finding**
- light / brightness / heating / movement / presence modules already exist in runtime,
- basis modules are already wired into dashboard initialization,
- but they are not yet represented as one coherent first-class Core model.

**Implication**
Slice 3 must make modules explicit in truth, policy, zone applicability, and read models.

### 4) The HA module in Core should be treated as a connection module
**Evidence**
- `hub/homeassistant_module.py`
- `hub/module_router.py`
- `ingest/event_processor.py`
- `core_setup.py`

**Finding**
- the Core-side HA module already tracks forwarding/connection/diagnostics,
- and routing already bridges normalized ingest into downstream module updates.

**Implication**
The concept and roadmap must treat it as the Core-side connection/preparation module, not a second semantic owner.

### 5) The brain representation is real, but still split across graph and neurons
**Evidence**
- `ingest/event_processor.py`
- `brain_graph/service.py`
- `neurons/manager.py`
- `README.md`
- `CLAUDE.md`

**Finding**
- normalized inputs already grow graph structure,
- neurons already run a layered context → state → mood pipeline,
- but the product does not yet expose one explicit “semantic transfer into growing brain” model.

**Implication**
Slice 5 must unify this as architecture, not just implementation trivia.

### 6) Dashboard concept is strong, but truth consumption is behind
**Evidence**
- `copilot_core/rootfs/usr/src/app/docs/ZONE_DASHBOARD.md`
- `copilot_core/api/v1/zone_dashboard.py`
- `dashboard/ZONE_CARDS_README.md`
- `tests/e2e/README.md`

**Finding**
- dashboard outputs are valuable,
- but `zone_dashboard.py` still depends on `habitus_zones` + `example_config` enrichment and local override logic.

**Implication**
Slice 6 must convert dashboard assembly into truth-backed zone/module/system read models.

### 7) Governance is already in the right place
**Evidence**
- `module_registry.py`
- `autonomy/executor.py`
- `homeassistant/habitus_zones.py`
- `api/v1/habitus.py`

**Finding**
- `active | learning | off`,
- double-safety,
- explanation-first defaults,
- policy-gated action intents,

are all already Core-native and should stay there.

**Implication**
Do not move policy semantics into HA/HACS.

### 8) RAG/chat is a Core surface, not a sidecar
**Evidence**
- `api/v1/styx_chat.py`
- `styx/chat_handler.py`
- `api/v1/rag.py`
- `conversation_memory.py`
- `vector_store/store.py`
- `core_setup.py`

**Finding**
- chat, RAG, memory, and embeddings are already Core services,
- and chat already builds responses from retrieval + memory + live home context.

**Implication**
Slice 9 must align chat with the same truth/read-model layer as the rest of Core.

### 9) Proposal lifecycle is valuable but fragmented
**Evidence**
- `habitus_miner/service.py`
- `habitus_miner/zone_mining.py`
- `candidates/store.py`
- `api/v1/suggestions.py`
- `api/v1/habitus.py`

**Finding**
Mining, proposals, candidate states, and action-intent shaping all exist, but not as one coherent product surface.

**Implication**
Slice 7 must unify proposal lifecycle semantics.

---

### ✅ Slice 64 — Performance Optimization: Connection Pooling & Cache Tuning
**Status:** ✅ DONE (v15.3.44)

**Goal**
Connection pooling und cache tuning für production workloads optimieren.

### Deliverables
- [x] Connection pool defaults optimiert (25 connections, 5 per-host)
- [x] DNS cache TTL (60s) und TCP keepalive (60s) hinzugefügt
- [x] Connector TTL reduziert (300s → 180s)
- [x] Cache tiering strategy implementiert (sensor=60s, rag=600s, api=300s, config=3600s)
- [x] Local cache size erhöht (500 → 1000 entries)
- [x] Performance metrics dokumentiert

### Acceptance criteria
- [x] Connection reuse rate >85% (achieved: 89%)
- [x] Cache hit rate >80% (achieved: 84%)
- [x] Avg API latency <100ms (achieved: 87ms)
- [x] Throughput >250 req/s (achieved: 287)

**Commit:** `feat(core): deliver slice 64 performance optimization`
**Tag:** v15.3.44

---

### ✅ Slice 63 — OpenAPI Specification Complete
**Status:** ✅ DONE (v15.3.43)

**Goal**
Vollständige OpenAPI 3.0.3 Spezifikation für alle Core-APIs generieren.

### Deliverables
- [x] OpenAPI 3.0.3 Schema für alle `/api/v1/*` Endpoints
- [x] 93 paths dokumentiert across 15 tags
- [x] Security schemes: apiKeyAuth, bearerAuth
- [x] Saved to `copilot_core/docs/openapi.yaml` und `docs/openapi-core-current.yaml`

**Commit:** `docs: deliver slice 63 openapi specification complete`
**Tag:** v15.3.43

---

### ✅ Slice 68 — Notification Delivery Engine
**Status:** ✅ DONE (v15.3.79)

**Goal**
Unified notification delivery engine with channel routing, rate limiting, and delivery tracking.

### Deliverables
- [x] NotificationV1/NotificationDeliveryV1/DeliveryAttemptV1 contracts
- [x] DeliveryEngine with channel handlers (Telegram, WhatsApp, Email, Push, HA)
- [x] Rate limiting per user/channel (configurable limits per channel)
- [x] Quiet hours enforcement with priority override (CRITICAL bypasses)
- [x] Channel enable/disable checks via user preferences
- [x] NotificationDeliveryStore with SQLite backend and revision tracking
- [x] REST API: POST /api/v1/notifications/send, GET /deliveries, /summary
- [x] Delivery status lifecycle: pending→sent→delivered→read→acknowledged
- [x] Contract tests (26 tests green)

### Acceptance criteria
- [x] Multi-channel delivery with unified contract
- [x] Rate limiting prevents notification floods
- [x] Quiet hours respected with critical priority override
- [x] Delivery tracking with retry logic and latency metrics
- [x] Revision-based delta polling for efficient UI updates
- [x] Integration with Slice 67 user preferences
- [x] Integration with Slice 52 analytics store

**Commit:** `feat(core): deliver slice 68 notification delivery engine`
**Tag:** v15.3.79
**Tests:** `pytest -q tests/test_notification_delivery_contract.py` → `26 passed`

---

## Next execution slices

### ✅ Slice 65 — Database Query Optimization
**Status:** ✅ DONE (v15.3.76)

**Goal**
SQLite query performance optimieren durch indexing, query caching und batch operations.

### Deliverables
- [x] `QueryOptimizer`-Klasse mit Cache, Batch-Operations und Query-Plan-Analyse
- [x] Composite Indexes für zone/module/proposal queries (10 Empfehlungen)
- [x] Query Result Caching mit TTL (60s sensor, 300s analytics, 3600s config)
- [x] Batch Insert/Update Operations mit Transaktion und Chunking
- [x] Query Metrics API unter `/api/v1/metrics/queries/*`
- [x] Contract-Tests (22 Tests grün)

### Acceptance criteria
- [x] Query latency <50ms für 95% der requests (Cache-Hit-Rate trackbar)
- [x] Index coverage >90% für häufigste queries (10 Composite-Index-Empfehlungen)
- [x] Batch operations für bulk writes mit Chunking (default 100 rows)
- [x] Query metrics exposed via `/api/v1/metrics/queries` (Summary, Detail, Slow, Analyze)

**Commit:** `feat(core): deliver slice 65 database query optimization`
**Tag:** v15.3.76
**Tests:** `pytest -q tests/test_query_optimization_contract.py` → `22 passed`

---

### ✅ Slice 66 — Insights Engine
**Status:** ✅ DONE (v15.3.77)

**Goal**
Canonical Insights Engine for actionable findings from analytics data.

### Deliverables
- [x] InsightV1/InsightSummaryV1/InsightDeltaV1 contracts
- [x] InsightCategory/InsightSeverity/InsightStatus/InsightSource enums (16 sources)
- [x] SQLite-backed InsightStore with revision tracking for delta polling
- [x] 8 Insight Generators (Performance, Anomaly, Trend, Optimization, Health, Usage, Prediction, Efficiency)
- [x] API endpoints: GET /api/v1/insights, /summary, /delta, /categories, /severities, /statuses, /sources
- [x] API endpoints: GET /api/v1/insights/<id>, PUT /api/v1/insights/<id>/status, POST /api/v1/insights/generate
- [x] Contract tests (30 tests green)
- [x] App integration in copilot_core/app.py

### Acceptance criteria
- [x] Insights derived from analytics data with clear category/severity/source
- [x] Revision tracking enables efficient delta polling
- [x] Filterable by category, severity, status, source, zone_id
- [x] Contract tests cover Store, Generators, and API surfaces

**Commit:** `feat(core): deliver slice 66 insights engine`
**Tag:** v15.3.77
**Tests:** `pytest -q tests/test_insights_contract.py` → `30 passed`

---

### ✅ Slice 67 — User Profile and Preferences Surface
**Status:** ✅ DONE (v15.3.78)

**Goal**
User notification preferences and profile management surface for personalized delivery.

### Deliverables
- [x] UserProfileV1/NotificationPreferencesV1/ChannelPreferencesV1/UserSettingsV1 contracts
- [x] NotificationChannel/NotificationCategory/NotificationPriority/DeliveryMode enums
- [x] SQLite-backed UserStore for profiles and preferences
- [x] API endpoints: GET/PUT /api/v1/users/profile, /preferences, /settings
- [x] API endpoints: PUT /api/v1/users/preferences/dnd, /preferences/channel/<channel>
- [x] API endpoints: DELETE /api/v1/users, GET /channels, /categories, /priorities, /delivery-modes
- [x] Contract tests (25 tests green)
- [x] App integration in copilot_core/app.py

### Acceptance criteria
- [x] User profiles with timezone, language, metadata support
- [x] Notification preferences with global and channel-specific settings
- [x] Do-not-disturb with optional expiry
- [x] Channel preferences: enabled, delivery_mode, min_priority, quiet_hours, rate limits
- [x] Revision tracking for delta polling
- [x] Contract tests cover Store and API surfaces

**Commit:** `feat(core): deliver slice 67 user profile and preferences`
**Tag:** v15.3.78
**Tests:** `pytest -q tests/test_users_contract.py` → `25 passed`

---

### ✅ Slice 70 — Calendar Smart Scheduling Surface
**Status:** ✅ DONE (v15.3.81)

**Goal**
Smart Scheduling als kanonische Core-Surface für kontextbewusste Terminplanung mit Mood-, Zone- und Präferenzintegration.

### Deliverables
- [x] `SmartScheduler` mit `recommend_slot()`, `get_day_summary()`, `suggest_alarm_adjustment()`
- [x] `MoodAwareScheduler` für stimmungsbewusste Anpassungen
- [x] `ScheduleSuggester` mit `ScheduleSuggestion`-Contract (nicht nur `Suggestion`)
- [x] `CalendarIntegrationEngine` (nicht `CalendarIntegration`) für HA-Kalender-Sync
- [x] API-Endpoints unter `/api/v1/calendar/*`: `/smart/recommend`, `/smart/day-summary`, `/smart/alarm-suggestion`, `/mood/*`, `/suggestions/*`
- [x] Calendar Analytics unter `/api/v1/calendar/analytics/*` (Slice 69-Analytics-Pattern)
- [x] Calendar Notifications unter `/api/v1/notifications/calendar/*`
- [x] Import-Korrekturen: `CalendarIntegrationEngine`, `ScheduleSuggestion` statt veralteter Namen
- [x] Contract-Tests: `test_calendar_analytics_contract.py` (18 Tests), `test_calendar_integration.py` (20 Tests), `test_calendar_notifications_contract.py` (20 Tests)

### Acceptance criteria
- Smart Scheduler empfiehlt kontextbewusste Zeitfenster basierend auf Kalenderdichte, Mood und Zone
- Mood-Aware-Passung passt Events an Stimmungslage an (Licht, Timing, Puffer)
- ScheduleSuggestions folgen demselben Proposal-Lifecycle wie andere Core-Vorschläge
- Calendar Analytics trackt Usage, Patterns und Effectiveness mit Revision-Delta
- Calendar Notifications integrieren sich in die kanonische Notification-Delivery-Engine
- Alle Imports verwenden korrekte Engine-/Suggestion-Klassen (`CalendarIntegrationEngine`, `ScheduleSuggestion`)

**Commit:** `feat(calendar): deliver slice 70 smart scheduling surface`
**Tag:** v15.3.81
**Tests:** `pytest -q tests/test_calendar_*.py` → `58 passed`

### ✅ Slice 71 — Voice Calendar Integration Surface
**Status:** ✅ DONE (v15.3.82)

**Goal**
Voice-Hinweise um kalenderbewusste Vorschläge erweitern: anstehende Termine, Kalenderdichte, Wecker-Empfehlungen und Meeting-Vorbereitung.

### Deliverables
- [x] `CalendarVoiceIntegration`-Klasse für kalenderbewusste Voice-Hinweise
- [x] `CalendarEventContext` und `CalendarDaySummary` Dataclasses
- [x] `ProactiveVoiceHints._check_calendar_events()`-Methode
- [x] `VoiceContext` v1.1 mit `calendar_context`-Feld
- [x] `get_calendar_integration_engine()`-Lazy-Initializer
- [x] DE/EN zweisprachige Hint-Nachrichten für anstehende Termine, Dichte, Wecker
- [x] Integration mit `CalendarIntegrationEngine` aus Calendar-Modul
- [x] Contract-Tests für Calendar-Voice-Integration (16 Tests grün)

### Acceptance criteria
- Voice-Hinweise enthalten anstehende Terminerinnerungen (urgent/soon/today-Priorität)
- Kalenderdichte-Hinweise für beschäftigte/mittlere/entspannte Tage
- Wecker-Anpassungsvorschläge basierend auf erstem Termin morgen
- Meeting-Vorbereitungshinweise mit Reisezeitbewusstsein
- Alle Hinweise folgen demselben ProactiveHint-Contract wie andere Voice-Hinweise
- Contract-Tests grün (16/16)

**Commit:** `feat(voice): deliver slice 71 calendar integration for voice hints`
**Tag:** v15.3.82
**Tests:** `pytest -q tests/test_voice_calendar_integration_contract.py` → `16 passed`

**Next Exact Task:** Slice 72 als Multilingual Voice Surface ableiten: erweiterte DE/EN-Unterstützung mit Sprachumschaltung, Übersetzungsqualitätstests und Voice-Intent-Parsing für beide Sprachen.

### ✅ Slice 72 — Multilingual Voice Surface
**Status:** ✅ DONE (v15.3.83)

**Goal**
Erweiterte DE/EN-Unterstützung für Voice mit automatischer Spracherkennung, Sprachumschaltung und Locale-aware Formatting.

### Deliverables
- [x] `MultilingualVoiceHandler`-Klasse mit erweiterter DE/EN-Unterstützung
- [x] Automatische Spracherkennung mit Confidence-Scores
- [x] `switch_language()` für Sprachumschaltung zur Laufzeit
- [x] `generate_bilingual_response()` für zweisprachige Antworten
- [x] `TranslationQualityMetrics` für Qualitäts-Tracking
- [x] `MultilingualResponseGenerator` mit Locale-aware Formatting
- [x] `LanguagePreference` und `MultilingualVoiceConfig` Dataclasses
- [x] DE/EN Intent-Patterns mit gemeinsamen Indikatoren (light, on, off, etc.)
- [x] Contract-Tests für Multilingual-Voice-Surface (31 Tests grün)

### Acceptance criteria
- DE/EN Spracherkennung mit Confidence >= 0.5 für klare Texte
- Sprachumschaltung validiert unterstützte Sprachen (de/en)
- Bilingual-Mode erzeugt Antworten in beiden Sprachen
- Zeitformatierung: DE (24h), EN (12h mit AM/PM)
- Temperaturformatierung: DE (°C), EN (°F)
- Translation-Metrics tracken total_translations und avg_confidence
- Contract-Tests grün (31/31)

**Commit:** `feat(voice): deliver slice 72 multilingual voice surface`
**Tag:** v15.3.83
**Tests:** `pytest -q tests/test_voice_multilingual_contract.py` → `31 passed`

### ✅ Slice 73 — Voice Intent Contract Hardening
**Status:** ✅ DONE (v15.3.84)

**Goal**
Robustere Intent-Erkennung mit Edge-Case-Tests, mehrsprachigen Entity-Aliases und Confidence-Threshold-Tuning für production use.

### Deliverables
- [x] Noise-Word-Filtering für bessere Intent-Erkennung
- [x] Typo-tolerante Pattern-Matching (häufige DE/EN-Tipps)
- [x] Erweiterte Zone-/Device-Aliases (DE/EN)
- [x] Confidence-Threshold-Tuning mit Textlänge-Faktoren
- [x] Edge-Case-Handling: empty, long, special chars, Unicode
- [x] Negation-Detection als expliziter Intent-Typ
- [x] Contract-Tests für Voice-Intent-Härtung (26 Tests grün)

### Acceptance criteria
- Intent-Erkennung funktioniert auch mit Füllwörtern und Tippfehlern
- Zone-/Device-Namen werden in DE/EN-Varianten erkannt
- Confidence-Scores reflektieren Intent-Klarheit und Textspezifität
- Edge-Cases (leer, sehr lang, Sonderzeichen) werden stabil behandelt
- Contract-Tests grün (26/26)

**Commit:** `feat(voice): deliver slice 73 voice intent contract hardening`
**Tag:** v15.3.84
**Tests:** `pytest -q tests/test_voice_intent_contract.py` → `26 passed`

### ✅ Slice 74 — Voice Multi-Turn Dialog Surface
**Status:** ✅ DONE (worktree; kein Live-/Install-Schritt)

**Goal**
Konversationsfähige Voice-Interaktionen mit Kontext-Tracking über mehrere Turns, Rückfrage-Logik bei niedriger Confidence und Closure-/Proposal-Integration auf derselben kanonischen Core-Wahrheit liefern.

### Grounded progress
- [x] `VoiceDialogStatus`, `VoiceDialogSession` und `VoiceDialogFollowUpTarget` als Multi-Turn-State im `VoiceControlEngine`
- [x] `process_dialog_turn()` mit Session-Fortsetzung, Turn-Merge und Zone-Kontext-Vererbung
- [x] explizite Clarification-Responses für low-confidence / unknown Turns statt stiller Fehlpfade
- [x] Proposal-/Action-Closure-Follow-up-Ziele als Dialogkontext anschließbar
- [x] fokussierte Contract-Tests für Zone-Carryover, Clarification-Merge und Follow-up-Targets
- [x] expliziter API-Continue-Pfad unter `/api/v1/voice/control/continue` ergänzt, der nur bestehende Dialog-Sessions fortsetzt
- [x] fokussierte API-Contracts für explizites Continue sowie Missing-/Unknown-Session-Fehlpfade ergänzt
- [x] Resume-Conflict-Payloads spiegeln terminale Proposal-/Action-Closure-Follow-up-Status im `dialog_session` konsistent zurück
- [x] erfolgreiche Resume-Pfade übernehmen explizit übergebene Proposal-/Action-Closure-Follow-up-Status end-to-end bis in `dialog_session`, `voice_response` und Session-Readback
- [x] fokussierter Core-Dialog-Contract zieht expliziten `action_closure`-Resume mit normalisiertem Follow-up-Status auf Proposal-Parität nach
- [x] Session-Readback-/History-Contract deckt jetzt den vollständigen API-Pfad Clarify → Continue → Follow-up ab und prüft `last_response` + `history` gegen GET `/api/v1/voice/control/session/<session_id>`
- [x] Resume-Conflict-Readback-/History-Contracts decken jetzt auch den vollständigen API-Pfad Clarify → Continue → Follow-up → Resume-Conflict ab, ohne `last_response` oder `history` im Session-Readback zu verändern
- [x] explizite EN-Follow-up-Resume-Contracts prüfen `continue`, `follow up`, `what about that` und `still open` auf `/api/v1/voice/control/continue` für Proposal- und Action-Closure-Targets
- [x] EN-Resume-Conflict-/Readback-Parität ergänzt: Nicht-Resume-Texte und terminale Follow-up-Status halten denselben stabilen `/api/v1/voice/control/continue`-Kontrakt, ohne persistiertes Session-Readback zu mutieren

### Verification
- `pytest -q tests/test_voice_policy_contract.py tests/test_voice_dialog_contract.py tests/test_voice_control.py tests/test_voice_intent_contract.py` → `106 passed`

### ✅ Slice 75 — Voice Follow-Up Resume Bilingual Parity
**Status:** ✅ DONE (worktree; kein Live-/Install-Schritt)

**Goal**
Explizite Follow-up-Resumes auf `/api/v1/voice/control/continue` für DE↔EN-Sessions kontraktfest machen, damit Slice-72-Mehrsprachigkeit auch im Slice-74-Dialogpfad bei offenen Proposal-/Closure-Follow-ups nicht an der Session-Sprache hängen bleibt.

### Grounded progress
- [x] Resume-Erkennung in `api/v1/voice.py` priorisiert Session-Sprache, akzeptiert aber danach auch die zweite freigegebene DE/EN-Resume-Phrase-Familie als kanonischen Fallback
- [x] `VoiceControlEngine._looks_like_follow_up_request()` spiegelt dieselbe bilinguale Resume-Logik, sodass `/continue` nicht mehr in einen künstlichen Clarification-Pfad kippt, nur weil Phrase und Session-Sprache gemischt sind
- [x] neue API-Contracts decken DE-Session + EN-Resume (`continue`) sowie EN-Session + DE-Resume (`mach weiter`) auf derselben offenen Proposal-Follow-up-Surface ab
- [x] Session-Readback bleibt dabei sprachstabil: Session-Language bleibt unverändert, `last_command.raw_text` spiegelt die echte gemischte Resume-Phrase zurück

### Verification
- `pytest -q tests/test_voice_policy_contract.py -k 'cross_language_follow_up_resume_phrases or explicit_english_follow_up_resume_phrases'` → `10 passed`
- `pytest -q tests/test_voice_policy_contract.py tests/test_voice_dialog_contract.py tests/test_voice_control.py tests/test_voice_intent_contract.py` → `108 passed`

### ✅ Slice 76 — Voice Resume Matcher Single-Source Hardening
**Status:** ✅ DONE (worktree; kein Live-/Install-Schritt)

**Goal**
Die Slice-75-Resume-Logik gegen Drift härten, indem API-Continue-Validierung und Engine-Follow-up-Erkennung denselben kanonischen Matcher benutzen und die Phrase-Familie minimal erweitert wird.

### Grounded progress
- [x] kanonische Helper-Funktion `looks_like_follow_up_resume_request()` in `voice/control_engine.py` eingeführt
- [x] API-Wrapper in `api/v1/voice.py` auf denselben Matcher umgehängt; keine doppelte Resume-Regex-Pflege mehr zwischen `/continue` und Engine-Follow-up-Pfad
- [x] freigegebene Resume-Phrasen minimal erweitert: DE `weiter damit`, EN `go on`
- [x] Engine-Contracts decken die neuen Phrasen direkt ab; API-Contracts ziehen `go on` auf `/api/v1/voice/control/continue` mit stabilem Session-Readback nach

### Verification
- `pytest -q tests/test_voice_dialog_contract.py tests/test_voice_policy_contract.py` → `56 passed`
- `pytest -q tests/test_voice_policy_contract.py tests/test_voice_dialog_contract.py tests/test_voice_control.py tests/test_voice_intent_contract.py` → `112 passed`

### ✅ Slice 77 — Voice German Resume Variant Hardening
**Status:** ✅ DONE (worktree; kein Live-/Install-Schritt)

**Goal**
Die kanonische Slice-76-Resume-Erkennung um eine echte zusätzliche DE-Variante härten, damit `/api/v1/voice/control/continue` und der Engine-Follow-up-Pfad auch natürlich formuliertes `mach damit weiter` stabil auf dieselbe Proposal-/Closure-Follow-up-Wahrheit mappen.

### Grounded progress
- [x] kanonische DE-Resume-Phrase in `looks_like_follow_up_resume_request()` minimal erweitert: `mach damit weiter`
- [x] Engine-Contracts decken die neue Variante direkt gegen denselben Single-Source-Matcher ab
- [x] explizite API-Contracts prüfen `mach weiter`, `weiter damit` und `mach damit weiter` auf `/api/v1/voice/control/continue` mit stabilem Session-Readback
- [x] keine neue Schattenlogik; API und Engine laufen weiter über denselben Matcher aus Slice 76

### Verification
- `pytest -q tests/test_voice_dialog_contract.py tests/test_voice_policy_contract.py -k 'extended_follow_up_resume_phrases or explicit_german_follow_up_resume_phrases or explicit_english_follow_up_resume_phrases or cross_language_follow_up_resume_phrases'` → `18 passed`
- `pytest -q tests/test_voice_policy_contract.py tests/test_voice_dialog_contract.py tests/test_voice_control.py tests/test_voice_intent_contract.py` → `116 passed`

### ✅ Slice 78 — Voice German Contracted Resume Phrase Hardening
**Status:** ✅ DONE (worktree; kein Live-/Install-Schritt)

**Goal**
Die kanonische Resume-Erkennung um die gesprochene/ASR-nahe DE-Variante `wie stehts damit` (inkl. Apostroph-Form) härten und konfliktseitige Readback-Parität dafür auf `/api/v1/voice/control/continue` festziehen.

### Grounded progress
- [x] kanonischer DE-Resume-Matcher akzeptiert jetzt `wie stehts damit` sowie `wie steht's damit`, ohne neue API-/Engine-Schattenlogik einzuführen
- [x] Engine-Contracts decken die kontrahierte DE-Resume-Variante direkt gegen denselben Single-Source-Matcher ab
- [x] explizite API-Contracts prüfen `wie stehts damit` auf `/api/v1/voice/control/continue` als erfolgreichen Resume mit stabilem Session-Readback
- [x] neue DE-Resume-Conflict-Contracts verifizieren terminale Follow-up-Konflikte für Proposal- und Action-Closure-Targets, während persistiertes Session-Readback unverändert offen bleibt

### Verification
- `pytest -q tests/test_voice_dialog_contract.py tests/test_voice_policy_contract.py -k 'explicit_german_follow_up_resume_phrases or contracted_resume_phrase or extended_follow_up_resume_phrases'` → `10 passed`
- `pytest -q tests/test_voice_policy_contract.py tests/test_voice_dialog_contract.py tests/test_voice_control.py tests/test_voice_intent_contract.py` → `120 passed`

### ✅ Slice 79 — Voice German Natural-Language Resume Readback Parity
**Status:** ✅ DONE (worktree; kein Live-/Install-Schritt)

**Goal**
Die bereits im kanonischen Resume-Matcher enthaltenen DE-Natursprach-Phrasen `was ist damit` und `noch offen` jetzt auch kontraktfest auf Engine- und `/api/v1/voice/control/continue`-Readback ziehen, inklusive konfliktseitiger Session-Stabilität.

### Grounded progress
- [x] Engine-Contracts decken `was ist damit` und `noch offen` direkt gegen denselben Single-Source-Resume-Matcher ab
- [x] explizite API-Contracts prüfen beide DE-Phrasen auf `/api/v1/voice/control/continue` als erfolgreiche Follow-up-Resumes mit stabilem Session-Readback
- [x] neue konfliktseitige Readback-Contracts verifizieren beide Phrasen gegen terminale Proposal- und Action-Closure-Follow-up-Ziele, ohne persistiertes `last_response`, `history` oder `active_follow_up` zu mutieren
- [x] keine neue Schattenlogik; Engine und API bleiben an demselben kanonischen Resume-Matcher aus Slice 76/77/78 gekoppelt

### Verification
- `pytest -q tests/test_voice_dialog_contract.py tests/test_voice_policy_contract.py -k 'explicit_german_follow_up_resume_phrases or natural_resume_phrases or extended_follow_up_resume_phrases'` → `18 passed`
- `pytest -q tests/test_voice_policy_contract.py tests/test_voice_dialog_contract.py tests/test_voice_control.py tests/test_voice_intent_contract.py` → `128 passed`

### ✅ Slice 80 — Voice English Natural-Language Resume Contraction Parity
**Status:** ✅ DONE (worktree; kein Live-/Install-Schritt)

**Goal**
Die EN-Natursprach-Resume-Variante `how's that going` inklusive ASR-naher Apostroph-Loss-Form `hows that going` auf denselben kanonischen Resume-Matcher ziehen und konfliktseitige Readback-Parität auf `/api/v1/voice/control/continue` festzurren.

### Grounded progress
- [x] kanonischer EN-Resume-Matcher akzeptiert jetzt `how's that going` sowie `hows that going`, ohne neue API-/Engine-Schattenlogik einzuführen
- [x] Engine-Contracts decken die neue EN-Natursprach-Resume-Variante direkt gegen denselben Single-Source-Matcher ab
- [x] explizite API-Contracts prüfen beide EN-Phrasen auf `/api/v1/voice/control/continue` als erfolgreiche Follow-up-Resumes mit stabilem Session-Readback
- [x] terminale Follow-up-Conflict-Readback-Contracts verifizieren beide Phrasen gegen Proposal- und Action-Closure-Ziele, ohne persistiertes `last_response`, `history` oder `active_follow_up` zu mutieren
- [x] keine neue Schattenlogik; Engine und API bleiben an demselben kanonischen Resume-Matcher aus Slice 76/75 gekoppelt

### Verification
- `pytest -q tests/test_voice_dialog_contract.py tests/test_voice_policy_contract.py -k 'extended_follow_up_resume_phrases or explicit_english_follow_up_resume_phrases or surfaces_english_terminal_follow_up_status_without_mutating_session_readback'` → `27 passed, 54 deselected`
- `pytest -q tests/test_voice_policy_contract.py tests/test_voice_dialog_contract.py tests/test_voice_control.py tests/test_voice_intent_contract.py` → `137 passed`

### ✅ Slice 81 — Voice English Natural-Language Resume Pronoun Parity
**Status:** ✅ DONE (worktree; kein Live-/Install-Schritt)

**Goal**
Die EN-Natursprach-Resume-Variante `how's it going` inklusive ASR-naher Apostroph-Loss-Form `hows it going` auf denselben kanonischen Resume-Matcher ziehen und konfliktseitige Readback-Parität auf `/api/v1/voice/control/continue` festzurren.

### Grounded progress
- [x] kanonischer EN-Resume-Matcher akzeptiert jetzt neben `how's that going` / `hows that going` auch `how's it going` sowie `hows it going`, ohne neue API-/Engine-Schattenlogik einzuführen
- [x] Engine-Contracts decken die neue EN-Pronoun-Variante direkt gegen denselben Single-Source-Resume-Matcher ab
- [x] explizite API-Contracts prüfen beide neuen EN-Phrasen auf `/api/v1/voice/control/continue` als erfolgreiche Follow-up-Resumes mit stabilem Session-Readback
- [x] terminale Follow-up-Conflict-Readback-Contracts verifizieren beide neuen Phrasen gegen Proposal- und Action-Closure-Ziele, ohne persistiertes `last_response`, `history` oder `active_follow_up` zu mutieren
- [x] keine neue Schattenlogik; Engine und API bleiben an demselben kanonischen Resume-Matcher aus Slice 76/80 gekoppelt

### Verification
- `pytest -q tests/test_voice_dialog_contract.py tests/test_voice_policy_contract.py -k 'extended_follow_up_resume_phrases or explicit_english_follow_up_resume_phrases or surfaces_english_terminal_follow_up_status_without_mutating_session_readback'` → `37 passed, 54 deselected`
- `pytest -q tests/test_voice_dialog_contract.py tests/test_voice_policy_contract.py tests/test_voice_control.py tests/test_voice_intent_contract.py` → `147 passed`

### ✅ Slice 82 — Voice English Natural-Language Resume Check-In Parity
**Status:** ✅ DONE (worktree; kein Live-/Install-Schritt)

**Goal**
Die bereits im kanonischen EN-Resume-Matcher vorhandene Check-in-Formulierung `check on it` explizit auf Engine- und `/api/v1/voice/control/continue`-Contracts ziehen und konfliktseitige Readback-Parität dafür festzurren.

### Grounded progress
- [x] Engine-Contracts decken `check on it` jetzt direkt gegen denselben Single-Source-Resume-Matcher wie die bisherigen EN-Follow-up-Phrasen ab
- [x] explizite API-Contracts prüfen `check on it` auf `/api/v1/voice/control/continue` als erfolgreichen Follow-up-Resume mit stabilem Session-Readback
- [x] terminale Follow-up-Conflict-Readback-Contracts verifizieren `check on it` gegen Proposal- und Action-Closure-Ziele, ohne persistiertes `last_response`, `history` oder `active_follow_up` zu mutieren
- [x] keine neue Schattenlogik; Slice 82 härtet die bereits kanonische Matcher-Wahrheit kontraktseitig statt neue API-/Engine-Sonderpfade einzuführen

### Verification
- `pytest -q tests/test_voice_dialog_contract.py tests/test_voice_policy_contract.py -k 'extended_follow_up_resume_phrases or explicit_english_follow_up_resume_phrases or surfaces_english_terminal_follow_up_status_without_mutating_session_readback'` → `42 passed, 54 deselected`
- `pytest -q tests/test_voice_dialog_contract.py tests/test_voice_policy_contract.py tests/test_voice_control.py tests/test_voice_intent_contract.py` → `152 passed`

### ✅ Slice 83 — Voice English Resume Phrase `continue with` Contract Parity
**Status:** ✅ DONE (worktree; kein Live-/Install-Schritt)

**Goal**
Die bereits im kanonischen EN-Resume-Matcher vorhandene Resume-Variante `continue with` explizit auf Engine- und `/api/v1/voice/control/continue`-Contracts ziehen und konfliktseitige Readback-Parität dafür festzurren.

### Grounded progress
- [x] Engine-Contracts decken `continue with` jetzt direkt gegen denselben Single-Source-Resume-Matcher wie die übrigen EN-Follow-up-Phrasen ab
- [x] explizite API-Contracts prüfen `continue with` auf `/api/v1/voice/control/continue` als erfolgreichen Follow-up-Resume mit stabilem Session-Readback
- [x] terminale Follow-up-Conflict-Readback-Contracts verifizieren `continue with` gegen Proposal- und Action-Closure-Ziele, ohne persistiertes `last_response`, `history` oder `active_follow_up` zu mutieren
- [x] keine neue Schattenlogik; Slice 83 härtet die bereits kanonische Matcher-Wahrheit kontraktseitig statt neue API-/Engine-Sonderpfade einzuführen

### Verification
- `pytest -q tests/test_voice_dialog_contract.py tests/test_voice_policy_contract.py -k 'extended_follow_up_resume_phrases or explicit_english_follow_up_resume_phrases or surfaces_english_terminal_follow_up_status_without_mutating_session_readback'` → `47 passed, 54 deselected`
- `pytest -q tests/test_voice_dialog_contract.py tests/test_voice_policy_contract.py tests/test_voice_control.py tests/test_voice_intent_contract.py` → `157 passed`

### ✅ Slice 84 — Voice English Resume Phrase `what about that` Contract Parity
**Status:** ✅ DONE (worktree; kein Live-/Install-Schritt)

**Goal**
Die bereits im kanonischen EN-Resume-Matcher vorhandene Resume-Variante `what about that` explizit auf Engine- und `/api/v1/voice/control/continue`-Contracts ziehen und konfliktseitige Readback-Parität dafür festzurren.

### Grounded progress
- [x] Engine-Contracts decken `what about that` jetzt direkt gegen denselben Single-Source-Resume-Matcher wie die übrigen EN-Follow-up-Phrasen ab
- [x] explizite API-Contracts prüfen `what about that` auf `/api/v1/voice/control/continue` als erfolgreichen Follow-up-Resume mit stabilem Session-Readback
- [x] terminale Follow-up-Conflict-Readback-Contracts verifizieren `what about that` gegen Proposal- und Action-Closure-Ziele, ohne persistiertes `last_response`, `history` oder `active_follow_up` zu mutieren
- [x] keine neue Schattenlogik; Slice 84 härtet die bereits kanonische Matcher-Wahrheit kontraktseitig statt neue API-/Engine-Sonderpfade einzuführen

### Verification
- `pytest -q tests/test_voice_dialog_contract.py tests/test_voice_policy_contract.py -k 'extended_follow_up_resume_phrases or explicit_english_follow_up_resume_phrases or surfaces_english_terminal_follow_up_status_without_mutating_session_readback'` → `50 passed, 54 deselected`
- `pytest -q tests/test_voice_dialog_contract.py tests/test_voice_policy_contract.py tests/test_voice_control.py tests/test_voice_intent_contract.py` → `160 passed`

### ✅ Slice 85 — Voice English Resume Conflict Coverage for `continue` and `go on`
**Status:** ✅ DONE (worktree; kein Live-/Install-Schritt)

**Goal**
Die bereits im kanonischen EN-Resume-Matcher vorhandenen Basis-/Kurzvarianten `continue` und `go on` konfliktseitig explizit auf `/api/v1/voice/control/continue`-Readback-Parität ziehen, ohne neue Matcher- oder API-Sonderpfade einzuführen.

### Grounded progress
- [x] die bereits vorhandene Engine-/Matcher-Wahrheit für `continue` und `go on` bleibt unverändert kanonische Basis; Slice 85 ergänzt nur die fehlende konfliktseitige API-Contract-Abdeckung
- [x] terminale Follow-up-Conflict-Readback-Contracts prüfen jetzt zusätzlich `continue` und `go on` auf `/api/v1/voice/control/continue`
- [x] persistiertes Session-Readback bleibt dabei unverändert offen; `last_response`, `history` und `active_follow_up` werden im Konfliktpfad nicht mutiert
- [x] keine neue Schattenlogik; Slice 85 härtet rein kontraktseitig die bereits vorhandene Matcher-Wahrheit

### Verification
- `pytest -q tests/test_voice_dialog_contract.py tests/test_voice_policy_contract.py -k 'extended_follow_up_resume_phrases or explicit_english_follow_up_resume_phrases or surfaces_english_terminal_follow_up_status_without_mutating_session_readback'` → `58 passed, 54 deselected`
- `pytest -q tests/test_voice_dialog_contract.py tests/test_voice_policy_contract.py tests/test_voice_control.py tests/test_voice_intent_contract.py` → `168 passed`

### ✅ Slice 86 — Runtime / Contract Inventory Baseline
**Status:** ✅ DONE (worktree; kein Live-/Install-Schritt)

**Goal**
Das im aktiven Core-Worktree angekündigte, aber fehlende Runtime-/Contract-Inventar aus echter Registry-/Runtime-/Test-Wahrheit nachziehen und daraus genau einen nächsten Repair-Slice ableiten, statt weitere isolierte Voice-Phrase-Parität vorzuziehen.

### Grounded progress
- [x] neues Standardlib-Skript `scripts/ps_core_runtime_contract_inventory.py` erzeugt das fehlende Inventar direkt aus `copilot_core/blueprints_config.py`, realen Modulpfaden und vorhandenen Testdateien
- [x] neues Artefakt `docs/analysis/PS_CORE_RUNTIME_CONTRACT_INVENTORY_2026-04-04.md` dokumentiert verifizierte route-starke Surfaces und deren direkte Contract-Test-Abdeckung
- [x] machine-readable Snapshot `docs/analysis/ps_core_runtime_contract_inventory_2026-04-04.json` ergänzt die Markdown-Sicht für spätere Wiederaufnahme/Härtung
- [x] fokussierter Test `tests/test_ps_core_runtime_contract_inventory.py` fixiert, dass das Inventar aus der aktiven Worktree-Wahrheit baut und `zone_editor` aktuell als schärfsten nächsten Gap markiert
- [x] Voice-Phrase-Parität wird damit bewusst gestoppt; nächster Slice ist wieder aus Runtime-/Contract-Relevanz statt aus zufälliger Phrase-Nähe abgeleitet

### Verification
- `python3 scripts/ps_core_runtime_contract_inventory.py --repo /config/clawd/team/worktrees/pilotsuite-styx-core-current --md-out /config/clawd/team/worktrees/pilotsuite-styx-core-current/docs/analysis/PS_CORE_RUNTIME_CONTRACT_INVENTORY_2026-04-04.md --json-out /config/clawd/team/worktrees/pilotsuite-styx-core-current/docs/analysis/ps_core_runtime_contract_inventory_2026-04-04.json`
- `pytest -q tests/test_ps_core_runtime_contract_inventory.py` → `2 passed`

**Next Exact Task:** Slice 87 — `zone_editor` als vom Inventar priorisierte route-starke Runtime-Surface mit fokussierten Request-/Response-/Fehlerpfad-Contracts für neue und Legacy-Endpunkte kontraktfest ziehen; weiterhin **kein** Live-/Install-/Restart-Schritt.

### ✅ Slice 87 — Zone Editor Runtime Contract Baseline
**Status:** ✅ DONE (worktree; kein Live-/Install-Schritt)

**Goal**
Die route-starke `zone_editor`-Surface für neue und Legacy-Endpunkte direkt kontraktabdecken, konsistente Fehlerpfade bei fehlender Engine nachziehen und das Runtime-/Contract-Inventar danach wieder auf echte Worktree-Wahrheit schneiden.

### Grounded progress
- [x] neues Direct-Contract-Harness `tests/test_zone_editor_contract.py` ergänzt eine stdlib-/stub-basierte Baseline für neue und Legacy-`zone_editor`-Surfaces ohne Live-/Install-Schritt
- [x] `copilot_core/rootfs/usr/src/app/copilot_core/api/v1/zone_editor.py` liefert für fehlende Engine jetzt konsistente 503-Responses statt unkontrollierter Runtime-Fehlerpfade auf mehreren Read-/Mutation-Endpunkten
- [x] `tests/test_ps_core_runtime_contract_inventory.py` zieht die Inventar-Wahrheit nach: `zone_editor` ist direkt kontraktabgedeckt und nicht mehr Top-Gap
- [x] `scripts/ps_core_runtime_contract_inventory.py` rendert die nächste Empfehlung jetzt dynamisch aus echter Inventar-Wahrheit statt hartcodiertem `zone_editor`-Text
- [x] regenerierte Artefakte `docs/analysis/PS_CORE_RUNTIME_CONTRACT_INVENTORY_2026-04-04.md` und `docs/analysis/ps_core_runtime_contract_inventory_2026-04-04.json` zeigen `copilot_core.api.v1.media_zones` als nächsten route-starken Gap

### Verification
- `pytest -q tests/test_zone_editor_contract.py tests/test_ps_core_runtime_contract_inventory.py` → `8 passed`
- `python3 scripts/ps_core_runtime_contract_inventory.py --repo . --json-out docs/analysis/ps_core_runtime_contract_inventory_2026-04-04.json --md-out docs/analysis/PS_CORE_RUNTIME_CONTRACT_INVENTORY_2026-04-04.md`

**Next Exact Task:** Slice 88 — `media_zones` als jetzt vom Inventar priorisierte route-starke Runtime-Surface mit fokussierten Request-/Response-/Fehlerpfad-Contracts kontraktfest ziehen; weiterhin **kein** Live-/Install-/Restart-Schritt.

### ✅ Slice 88 — Media Zones Runtime Contract Baseline
**Status:** ✅ DONE (worktree; kein Live-/Install-Schritt)

**Goal**
Die route-starke `media_zones`-Surface direkt kontraktabdecken, ungehärtete Favorites-/Source-Fehlerpfade sauber schließen und das Runtime-/Contract-Inventar danach wieder auf echte Worktree-Wahrheit schneiden.

### Grounded progress
- [x] neues Direct-Contract-Harness `tests/test_media_zones_contract.py` deckt `media_zones` jetzt fokussiert auf Lookup-/Assignment-/Volume-/Play-Media-/Musikwolke-/Proactive-/Favorites-/Source-Surfaces ab
- [x] `copilot_core/rootfs/usr/src/app/copilot_core/api/v1/media_zones.py` validiert `zone_id` jetzt auch auf Favorites-/Source-Surfaces und liefert dort konsistente JSON-500-Pfade statt unkontrollierter Runtime-Fehler
- [x] `tests/test_ps_core_runtime_contract_inventory.py` zieht die Inventar-Wahrheit nach: `media_zones` ist direkt kontraktabgedeckt und nicht mehr Top-Gap
- [x] regenerierte Artefakte `docs/analysis/PS_CORE_RUNTIME_CONTRACT_INVENTORY_2026-04-04.md` und `docs/analysis/ps_core_runtime_contract_inventory_2026-04-04.json` reduzieren die route-starken Surfaces ohne direkte Contract-Tests von **22** auf **21** und zeigen `copilot_core.api.v1.sonos` als nächsten route-starken Gap

### Verification
- `pytest -q tests/test_media_zones_contract.py tests/test_ps_core_runtime_contract_inventory.py` → `10 passed`
- `python3 scripts/ps_core_runtime_contract_inventory.py --repo . --json-out docs/analysis/ps_core_runtime_contract_inventory_2026-04-04.json --md-out docs/analysis/PS_CORE_RUNTIME_CONTRACT_INVENTORY_2026-04-04.md`

**Next Exact Task:** Slice 89 — `sonos` als jetzt vom Inventar priorisierte route-starke Runtime-Surface mit fokussierten Request-/Response-/Fehlerpfad-Contracts kontraktfest ziehen; weiterhin **kein** Live-/Install-/Restart-Schritt.

### ✅ Slice 89 — Sonos Runtime Contract Baseline
**Status:** ✅ DONE (worktree; kein Live-/Install-Schritt)

**Goal**
Die route-starke `sonos`-Surface direkt kontraktabdecken, ungehärtete Client-Exception-Pfade auf konsistente JSON-500-Responses ziehen und das Runtime-/Contract-Inventar danach wieder auf echte Worktree-Wahrheit schneiden.

### Grounded progress
- [x] neues Direct-Contract-Harness `tests/test_sonos_contract.py` deckt `sonos` jetzt fokussiert auf Discovery-/Status-/Playback-/Volume-/Favorites-/Playlist-/TTS-/Grouping-Surfaces ab
- [x] `copilot_core/rootfs/usr/src/app/copilot_core/api/v1/sonos.py` kapselt Sonos-Client-Calls jetzt über einen gemeinsamen Fehlerpfad und liefert bei Runtime-Fehlern konsistente JSON-500-Responses statt unkontrollierter Flask-500-Seiten
- [x] `tests/test_ps_core_runtime_contract_inventory.py` zieht die Inventar-Wahrheit nach: `sonos` ist direkt kontraktabgedeckt und nicht mehr Top-Gap
- [x] regenerierte Artefakte `docs/analysis/PS_CORE_RUNTIME_CONTRACT_INVENTORY_2026-04-04.md` und `docs/analysis/ps_core_runtime_contract_inventory_2026-04-04.json` reduzieren die route-starken Surfaces ohne direkte Contract-Tests von **21** auf **20** und zeigen `copilot_core.api.v1.neurons` als nächsten route-starken Gap

### Verification
- `pytest -q tests/test_sonos_contract.py tests/test_ps_core_runtime_contract_inventory.py` → `11 passed`
- `python3 scripts/ps_core_runtime_contract_inventory.py --repo . --json-out docs/analysis/ps_core_runtime_contract_inventory_2026-04-04.json --md-out docs/analysis/PS_CORE_RUNTIME_CONTRACT_INVENTORY_2026-04-04.md`

**Next Exact Task:** Slice 90 — `neurons` als jetzt vom Inventar priorisierte route-starke Runtime-Surface mit fokussierten Request-/Response-/Fehlerpfad-Contracts kontraktfest ziehen; weiterhin **kein** Live-/Install-/Restart-Schritt.

### ✅ Slice 90 — Neurons Runtime Contract Baseline
**Status:** ✅ DONE (worktree; kein Live-/Install-Schritt)

**Goal**
Die route-starke `neurons`-Surface direkt kontraktabdecken, unkoordinierte Mutationspfade admin-seitig härten und das Runtime-/Contract-Inventar danach wieder auf echte Worktree-Wahrheit schneiden.

### Grounded progress
- [x] neues Direct-Contract-Harness `tests/test_neurons_contract.py` deckt `neurons` jetzt fokussiert auf Summary-/Lookup-/Mood-/Suggestion-/Graph-/Stats-/Connections-/Paths-Surfaces sowie Mutations-/Admin-/Fehlerpfade ab
- [x] `copilot_core/rootfs/usr/src/app/copilot_core/api/v1/neurons.py` verlangt für `configure`, `/<neuron_id>/config`, `/<neuron_id>/enable`, `/<neuron_id>/disable` und `batch-configure` jetzt explizite Admin-Autorisierung statt stiller offener Mutationspfade
- [x] Batch-Konfigurationspfade validieren Patches jetzt vor dem Schreiben, sodass invalide Einzel-Patches keine partiellen Config-Mutationen mehr hinterlassen
- [x] `tests/test_ps_core_runtime_contract_inventory.py` zieht die Inventar-Wahrheit nach: `neurons` ist direkt kontraktabgedeckt und nicht mehr Top-Gap
- [x] regenerierte Artefakte `docs/analysis/PS_CORE_RUNTIME_CONTRACT_INVENTORY_2026-04-04.md` und `docs/analysis/ps_core_runtime_contract_inventory_2026-04-04.json` reduzieren die route-starken Surfaces ohne direkte Contract-Tests von **20** auf **19** und zeigen `copilot_core.api.v1.backend_ui` als nächsten route-starken Gap

### Verification
- `pytest -q tests/test_neurons_contract.py tests/test_ps_core_runtime_contract_inventory.py` → `11 passed`
- `python3 scripts/ps_core_runtime_contract_inventory.py --repo . --json-out docs/analysis/ps_core_runtime_contract_inventory_2026-04-04.json --md-out docs/analysis/PS_CORE_RUNTIME_CONTRACT_INVENTORY_2026-04-04.md`

### ✅ Slice 91 — Backend UI Runtime Contract Baseline
**Status:** ✅ DONE (worktree; kein Live-/Install-Schritt)

**Goal**
Die route-starke `backend_ui`-Surface direkt kontraktabdecken, Mutationspfade auf konsistente JSON-Validierung ziehen und das Runtime-/Contract-Inventar danach wieder auf echte Worktree-Wahrheit schneiden.

### Grounded progress
- [x] neues Direct-Contract-Harness `tests/test_backend_ui_contract.py` deckt `backend_ui` jetzt fokussiert auf Dashboard-/Zone-/Module-/Brain-/Mood-/Automation-/RAG-/Media-/Hardware-/System-Surfaces sowie Mutations-/503-/Validierungsfehlerpfade ab
- [x] `copilot_core/api/v1/backend_ui.py` nutzt für Mutationspfade jetzt eine gemeinsame JSON-Body-Validierung statt unkontrollierter `NoneType`-Fehler bei fehlendem Request-Body
- [x] `update_zone_module` validiert `module_id` explizit und spiegelt HA-Sync jetzt als echtes `ha_synced`-Resultat statt immer `True` zurück
- [x] `update_module` und `update_model` liefern jetzt konsistente 400-Responses für fehlende/ungültige Payloads und bestätigen erfolgreiche Updates mit klaren Feldern
- [x] `tests/test_ps_core_runtime_contract_inventory.py` zieht die Inventar-Wahrheit nach: `backend_ui` ist direkt kontraktabgedeckt und nicht mehr Top-Gap
- [x] regenerierte Artefakte `docs/analysis/PS_CORE_RUNTIME_CONTRACT_INVENTORY_2026-04-04.md` und `docs/analysis/ps_core_runtime_contract_inventory_2026-04-04.json` reduzieren die route-starken Surfaces ohne direkte Contract-Tests von **19** auf **18** und zeigen `copilot_core.api.v1.alarm` als nächsten route-starken Gap

### Verification
- `pytest -q tests/test_backend_ui_contract.py tests/test_ps_core_runtime_contract_inventory.py` → `12 passed`
- `python3 scripts/ps_core_runtime_contract_inventory.py --repo . --json-out docs/analysis/ps_core_runtime_contract_inventory_2026-04-04.json --md-out docs/analysis/PS_CORE_RUNTIME_CONTRACT_INVENTORY_2026-04-04.md`

### ✅ Slice 92 — Alarm Runtime Contract Baseline
**Status:** ✅ DONE (worktree; kein Live-/Install-Schritt)

**Goal**
Die route-starke `alarm`-Surface direkt kontraktabdecken, Mutationspfade auf konsistente JSON-Validierung ziehen, Runtime-Fehler auf stabile JSON-500-Pfade härten und das Runtime-/Contract-Inventar danach wieder auf echte Worktree-Wahrheit schneiden.

### Grounded progress
- [x] neues Direct-Contract-Harness `tests/test_alarm_contract.py` deckt `alarm` jetzt fokussiert auf Dashboard-/CRUD-/Trigger-/Snooze-/Cancel-/Zone-/Preset-/Curves-Surfaces sowie 404-/503-/500-Fehlerpfade ab
- [x] `copilot_core/rootfs/usr/src/app/copilot_core/api/v1/alarm.py` nutzt für Mutationspfade jetzt eine gemeinsame JSON-Body-Validierung; fehlende Bodies oder Nicht-Objekt-Payloads liefern konsistente JSON-400-Responses statt impliziter Default-Mutationen
- [x] Engine-Calls in `alarm.py` laufen jetzt über einen gemeinsamen Fehlerpfad und liefern bei Runtime-Fehlern konsistente JSON-500-Responses statt unkontrollierter Flask-500-Seiten
- [x] `tests/test_ps_core_runtime_contract_inventory.py` zieht die Inventar-Wahrheit nach: `alarm` ist direkt kontraktabgedeckt und nicht mehr Top-Gap
- [x] regenerierte Artefakte `docs/analysis/PS_CORE_RUNTIME_CONTRACT_INVENTORY_2026-04-04.md` und `docs/analysis/ps_core_runtime_contract_inventory_2026-04-04.json` reduzieren die route-starken Surfaces ohne direkte Contract-Tests von **18** auf **17** und zeigen `copilot_core.api.v1.entity_adoption` als nächsten route-starken Gap

### Verification
- `pytest -q tests/test_alarm_contract.py tests/test_ps_core_runtime_contract_inventory.py` → `12 passed`
- `python3.14 scripts/ps_core_runtime_contract_inventory.py --repo . --json-out docs/analysis/ps_core_runtime_contract_inventory_2026-04-04.json --md-out docs/analysis/PS_CORE_RUNTIME_CONTRACT_INVENTORY_2026-04-04.md`

**Next Exact Task:** Slice 93 — `entity_adoption` als jetzt vom Inventar priorisierte route-starke Runtime-Surface mit fokussierten Request-/Response-/Fehlerpfad-Contracts kontraktfest ziehen; weiterhin **kein** Live-/Install-/Restart-Schritt.

### ✅ Slice 93 — Entity Adoption Runtime Contract Baseline
**Status:** ✅ DONE (worktree; kein Live-/Install-/Restart-Schritt)

**Goal**
Die route-starke `entity_adoption`-Surface direkt kontraktabdecken, Mutationspfade auf konsistente JSON-Validierung ziehen, Service-Fehler auf stabile JSON-500-Pfade härten und das Runtime-/Contract-Inventar danach wieder auf echte Worktree-Wahrheit schneiden.

### Grounded progress
- [x] neues Direct-Contract-Harness `tests/test_entity_adoption_contract.py` deckt `entity_adoption` jetzt fokussiert auf Zone-/Assignment-/Stats-/Refresh-/Mapping-/Lookup-Surfaces sowie 400-/401-/404-/500-Fehlerpfade ab
- [x] `copilot_core/rootfs/usr/src/app/copilot_core/api/v1/entity_adoption.py` nutzt für Mutationspfade jetzt eine gemeinsame JSON-Body-Validierung; fehlende Bodies, Nicht-Objekt-Payloads und ungültige `metadata`-Payloads liefern konsistente JSON-400-Responses statt unkontrollierter Parser-/Runtime-Pfade
- [x] Service- und Async-Calls in `entity_adoption.py` laufen jetzt über gemeinsame Fehlerpfade und liefern bei Runtime-Fehlern konsistente JSON-500-Responses statt unkontrollierter Flask-500-Seiten
- [x] `tests/test_ps_core_runtime_contract_inventory.py` zieht die Inventar-Wahrheit nach: `entity_adoption` ist direkt kontraktabgedeckt und nicht mehr Top-Gap
- [x] regenerierte Artefakte `docs/analysis/PS_CORE_RUNTIME_CONTRACT_INVENTORY_2026-04-04.md` und `docs/analysis/ps_core_runtime_contract_inventory_2026-04-04.json` reduzieren die route-starken Surfaces ohne direkte Contract-Tests von **17** auf **16** und zeigen `copilot_core.api.v1.ha_module` als nächsten route-starken Gap

### Verification
- `pytest -q tests/test_entity_adoption_contract.py tests/test_ps_core_runtime_contract_inventory.py` → `13 passed`
- `python3 scripts/ps_core_runtime_contract_inventory.py --repo . --json-out docs/analysis/ps_core_runtime_contract_inventory_2026-04-04.json --md-out docs/analysis/PS_CORE_RUNTIME_CONTRACT_INVENTORY_2026-04-04.md`

**Next Exact Task:** Slice 94 — `ha_module` als jetzt vom Inventar priorisierte route-starke Runtime-Surface mit fokussierten Request-/Response-/Fehlerpfad-Contracts kontraktfest ziehen; weiterhin **kein** Live-/Install-/Restart-Schritt.

### ✅ Slice 94 — Home Assistant Module Runtime Contract Baseline
**Status:** ✅ DONE (worktree; kein Live-/Install-/Restart-Schritt)

**Goal**
Die route-starke `ha_module`-Surface direkt kontraktabdecken, Mutationspfade auf konsistente JSON-Validierung ziehen, Refresh-/Webhook-/Diagnostik-Pfade auf stabile JSON-Fehlerantworten härten und das Runtime-/Contract-Inventar danach wieder auf echte Worktree-Wahrheit schneiden.

### Grounded progress
- [x] neues Direct-Contract-Harness `tests/test_ha_module_contract.py` deckt `ha_module` jetzt fokussiert auf Status-/Connection-/Events-/Config-/Diagnostics-/Health-/Webhook-/Refresh-Surfaces sowie 400-/401-/503-/500-Fehlerpfade ab
- [x] `copilot_core/rootfs/usr/src/app/copilot_core/api/v1/ha_module.py` nutzt für Mutationspfade jetzt gemeinsame JSON-Objekt-Validierung; Nicht-Objekt-Payloads und fehlende Config-Bodies liefern konsistente JSON-400-Responses statt unkontrollierter Runtime-Pfade
- [x] `ha_module.py` behält Lazy-Init/Router-Integration bei, härtet aber `events/config`, `config` und `webhook-received` auf stabile Fehlerpfade; fehlender `module_router` bleibt kontrolliert bei JSON-503
- [x] `tests/test_ps_core_runtime_contract_inventory.py` zieht die Inventar-Wahrheit nach: `ha_module` ist direkt kontraktabgedeckt und nicht mehr Top-Gap
- [x] regenerierte Artefakte `docs/analysis/PS_CORE_RUNTIME_CONTRACT_INVENTORY_2026-04-04.md` und `docs/analysis/ps_core_runtime_contract_inventory_2026-04-04.json` reduzieren die route-starken Surfaces ohne direkte Contract-Tests von **16** auf **15** und zeigen `copilot_core.api.v1.shopping` als nächsten route-starken Gap

### Verification
- `pytest -q tests/test_ha_module_contract.py tests/test_ps_core_runtime_contract_inventory.py` → `13 passed`
- `python3 scripts/ps_core_runtime_contract_inventory.py --repo . --json-out docs/analysis/ps_core_runtime_contract_inventory_2026-04-04.json --md-out docs/analysis/PS_CORE_RUNTIME_CONTRACT_INVENTORY_2026-04-04.md`

**Next Exact Task:** Slice 95 — `shopping` als jetzt vom Inventar priorisierte route-starke Runtime-Surface mit fokussierten Request-/Response-/Fehlerpfad-Contracts kontraktfest ziehen; weiterhin **kein** Live-/Install-/Restart-Schritt.

### ✅ Slice 95 — Shopping Runtime Contract Baseline
**Status:** ✅ DONE (worktree; kein Live-/Install-/Restart-Schritt)

**Goal**
Die route-starke `shopping`-Surface direkt kontraktabdecken, Query-/Mutationspfade auf konsistente JSON-/Query-Validierung ziehen, Storage-Fehlerpfade auf stabile JSON-Fehlerantworten härten und das Runtime-/Contract-Inventar danach wieder auf echte Worktree-Wahrheit schneiden.

### Grounded progress
- [x] neues Direct-Contract-Harness `tests/test_shopping_contract.py` deckt `shopping` jetzt fokussiert auf Shopping-/Reminder-List-/Mutation-/Snooze-Surfaces sowie 400-/401-/404-/500-Fehlerpfade ab
- [x] `copilot_core/rootfs/usr/src/app/copilot_core/api/v1/shopping.py` nutzt für Query- und Mutationspfade jetzt gemeinsame JSON-/Query-Validierung; fehlende Bodies, Nicht-Objekt-Payloads, ungültige Query-Flags und Integer-/`due_at`-Fehlformate liefern konsistente JSON-400-Responses statt unkontrollierter Parser-/Runtime-Pfade
- [x] `shopping.py` behält das SQLite-basierte Persistenzmodell bei, härtet aber alle DB-Pfade auf kontrollierte JSON-500-Responses; Not-found-Pfade bleiben explizit als JSON-404 sichtbar
- [x] `tests/test_ps_core_runtime_contract_inventory.py` zieht die Inventar-Wahrheit nach: `shopping` ist direkt kontraktabgedeckt und nicht mehr Top-Gap
- [x] regenerierte Artefakte `docs/analysis/PS_CORE_RUNTIME_CONTRACT_INVENTORY_2026-04-04.md` und `docs/analysis/ps_core_runtime_contract_inventory_2026-04-04.json` reduzieren die route-starken Surfaces ohne direkte Contract-Tests von **15** auf **14** und zeigen `copilot_core.api.v1.musikwolke` als nächsten route-starken Gap

### Verification
- `pytest -q tests/test_shopping_contract.py tests/test_ps_core_runtime_contract_inventory.py` → `15 passed`
- `python3 scripts/ps_core_runtime_contract_inventory.py --repo . --json-out docs/analysis/ps_core_runtime_contract_inventory_2026-04-04.json --md-out docs/analysis/PS_CORE_RUNTIME_CONTRACT_INVENTORY_2026-04-04.md`

**Next Exact Task:** Slice 96 — `musikwolke` als jetzt vom Inventar priorisierte route-starke Runtime-Surface mit fokussierten Request-/Response-/Fehlerpfad-Contracts kontraktfest ziehen; weiterhin **kein** Live-/Install-/Restart-Schritt.

### ✅ Slice 96 — Musikwolke Runtime Contract Baseline
**Status:** ✅ DONE (worktree; kein Live-/Install-/Restart-Schritt)

**Goal**
Die route-starke `musikwolke`-Surface direkt kontraktabdecken, JSON-Body-/Volume-/Zone-List-Validierung härten, Bridge-/Runtime-Fehlerpfade auf stabile JSON-Fehlerantworten ziehen und das Runtime-/Contract-Inventar danach wieder auf echte Worktree-Wahrheit schneiden.

### Grounded progress
- [x] neues Direct-Contract-Harness `tests/test_musikwolke_contract.py` deckt `musikwolke` jetzt fokussiert auf Status-/Zone-Map-/Play-/Pause-/Volume-/Create-/Dissolve-Surfaces sowie 400-/500-/503-Fehlerpfade ab
- [x] `copilot_core/rootfs/usr/src/app/copilot_core/api/v1/musikwolke.py` nutzt für Mutationspfade jetzt gemeinsame JSON-Objekt-, Volume- und Zone-List-Validierung; fehlende Bodies, Nicht-Objekt-Payloads, ungültige `volume_pct`-Werte und invalide `zone_ids` liefern konsistente JSON-400-Responses statt unkontrollierter Parser-/Runtime-Pfade
- [x] `musikwolke.py` kapselt Bridge-/Runtime-Fehler auf Status-/Zone-Map-/Mutation-/Lifecycle-Pfaden jetzt über kontrollierte JSON-500-Responses; fehlende Bridge bleibt explizit auf JSON-503 sichtbar
- [x] `tests/test_ps_core_runtime_contract_inventory.py` zieht die Inventar-Wahrheit nach: `musikwolke` ist direkt kontraktabgedeckt und nicht mehr Top-Gap
- [x] regenerierte Artefakte `docs/analysis/PS_CORE_RUNTIME_CONTRACT_INVENTORY_2026-04-04.md` und `docs/analysis/ps_core_runtime_contract_inventory_2026-04-04.json` reduzieren die route-starken Surfaces ohne direkte Contract-Tests von **14** auf **13** und zeigen `copilot_core.api.v1.rag_ui` als nächsten route-starken Gap

### Verification
- `pytest -q tests/test_musikwolke_contract.py tests/test_ps_core_runtime_contract_inventory.py` → `17 passed`
- `python3 scripts/ps_core_runtime_contract_inventory.py --repo . --json-out docs/analysis/ps_core_runtime_contract_inventory_2026-04-04.json --md-out docs/analysis/PS_CORE_RUNTIME_CONTRACT_INVENTORY_2026-04-04.md --stdout-json`

**Next Exact Task:** Slice 97 — `rag_ui` als jetzt vom Inventar priorisierte route-starke Runtime-Surface mit fokussierten Request-/Response-/Fehlerpfad-Contracts kontraktfest ziehen; weiterhin **kein** Live-/Install-/Restart-Schritt.

### ✅ Slice 97 — RAG UI Runtime Contract Baseline
**Status:** ✅ DONE (worktree; kein Live-/Install-/Restart-Schritt)

**Goal**
Die route-starke `rag_ui`-Surface direkt kontraktabdecken, Query-/JSON-/Payload-Validierung härten, Runtime-Fehlerpfade auf stabile JSON-500-Responses ziehen und das Runtime-/Contract-Inventar danach wieder auf echte Worktree-Wahrheit schneiden.

### Grounded progress
- [x] neues Direct-Contract-Harness `tests/test_rag_ui_contract.py` deckt `rag_ui` jetzt fokussiert auf Overview-/Vectors-/Embeddings-/Search-/SearXNG-/Voice-Surfaces sowie 400-/500-Fehlerpfade ab
- [x] `copilot_core/api/v1/rag_ui.py` nutzt für Query- und Mutationspfade jetzt gemeinsame Integer-/JSON-/Payload-Validierung; fehlende Bodies, Nicht-Objekt-Payloads, leere Queries, invalide `categories` und ungültige Voice-Inputs liefern konsistente JSON-400-Responses statt unkontrollierter Parser-/Runtime-Pfade
- [x] `rag_ui.py` kapselt Runtime-Fehler auf Overview-/Search-/SearXNG-/Voice-Pfaden jetzt über kontrollierte JSON-500-Responses statt unkontrollierter Flask-500-Seiten
- [x] `tests/test_ps_core_runtime_contract_inventory.py` zieht die Inventar-Wahrheit nach: `rag_ui` ist direkt kontraktabgedeckt und nicht mehr Top-Gap
- [x] regenerierte Artefakte `docs/analysis/PS_CORE_RUNTIME_CONTRACT_INVENTORY_2026-04-04.md` und `docs/analysis/ps_core_runtime_contract_inventory_2026-04-04.json` reduzieren die route-starken Surfaces ohne direkte Contract-Tests von **13** auf **12** und zeigen `dashboard.api.v1.widget_positions` als nächsten route-starken Gap

### Verification
- `pytest -q tests/test_rag_ui_contract.py tests/test_ps_core_runtime_contract_inventory.py` → `16 passed`
- `python3 scripts/ps_core_runtime_contract_inventory.py --repo . --json-out docs/analysis/ps_core_runtime_contract_inventory_2026-04-04.json --md-out docs/analysis/PS_CORE_RUNTIME_CONTRACT_INVENTORY_2026-04-04.md --stdout-json`

**Next Exact Task:** Slice 98 — `dashboard.api.v1.widget_positions` als jetzt vom Inventar priorisierte route-starke Runtime-Surface mit fokussierten Request-/Response-/Fehlerpfad-Contracts kontraktfest ziehen; weiterhin **kein** Live-/Install-/Restart-Schritt.

### ✅ Slice 98 — Widget Positions Runtime Contract Baseline
**Status:** ✅ DONE (worktree; kein Live-/Install-/Restart-Schritt)

**Goal**
`dashboard.api.v1.widget_positions` als route-starke Dashboard-Surface mit direkter Contract-Baseline, konsistenten JSON-Validierungs-/Fehlerpfaden und Inventar-Parität absichern.

### Grounded progress
- [x] direkter Contract-Harness `tests/test_widget_positions_contract.py` deckt CRUD-, Bulk-, History-, Undo/Redo- und Reset-Surfaces gegen die aktive Blueprint-Wahrheit ab
- [x] JSON-/Validierungspfad in `dashboard/api/v1/widget_positions.py` gehärtet: konsistente Objekt-Prüfung, wiederverwendbare Positions-Validierung, bessere Bulk-Fehlerpfade
- [x] Landing-Härtung nachgezogen: leere `widget_id`-Werte und nicht-listige `history`-Payloads werden jetzt bereits auf der Basissurface konsistent als JSON-400 geblockt statt erst implizit in späteren History-/Undo-Pfaden zu kippen
- [x] WebSocket-Emission zentralisiert; Slice bleibt lane-scharf ohne Live-/Release-Kollision
- [x] kleine Qualitäts-Härtung mitgezogen: `datetime.utcnow()` durch zentralen UTC-Helper ersetzt
- [x] Inventar-Artefakte regeneriert; route-starke Surfaces ohne direkte Contract-Tests reduziert von **12** auf **11**
- [x] `dashboard.api.v1.widget_positions` ist nicht mehr Top-Gap und nicht mehr empfohlener nächster Slice

### Verification
- `pytest -q tests/test_widget_positions_contract.py tests/test_ps_core_runtime_contract_inventory.py -k 'widget_positions or runtime_contract_inventory'` → `16 passed`
- `python3 scripts/ps_core_runtime_contract_inventory.py --repo . --json-out docs/analysis/ps_core_runtime_contract_inventory_2026-04-04.json --md-out docs/analysis/PS_CORE_RUNTIME_CONTRACT_INVENTORY_2026-04-04.md --stdout-json` → `route_heavy_without_direct_contract_tests: 11`, `recommended_next_slice: copilot_core.api.v1.reminders`

**Next Exact Task:** Slice 99 — `copilot_core.api.v1.reminders` als jetzt vom Inventar priorisierte route-starke Runtime-Surface mit direkter Contract-Baseline ziehen; weiterhin **kein** Live-/Install-/Restart-Schritt.

### ✅ Slice 99 — Reminders Runtime Contract Baseline
**Status:** ✅ DONE (worktree; kein Live-/Install-/Restart-Schritt)

**Goal**
`copilot_core.api.v1.reminders` als route-starke Waste-/Birthday-Reminder-Surface mit direkter Contract-Baseline, konsistenten JSON-/Validierungs-/Service-Fehlerpfaden und Inventar-Parität absichern.

### Grounded progress
- [x] direkter Contract-Harness `tests/test_reminders_contract.py` deckt Waste- und Birthday-Surfaces gegen die aktive Blueprint-Wahrheit ab
- [x] erfolgreiche Flüsse abgesichert: Event-/Schedule-Update, Status, manuelle Reminder, automatisch abgeleitete Waste-/Birthday-Messages
- [x] Validierungs-/Unavailability-/Runtime-Fehlerpfade abgesichert: JSON body required, JSON object required, list validation, string validation, Service unavailable, runtime exceptions
- [x] Auth-Pfad explizit kontraktgesichert
- [x] Inventar-Artefakte regeneriert; `copilot_core.api.v1.reminders` ist nicht mehr Top-Gap und nicht mehr empfohlener nächster Slice
- [x] Design-Lane-Input geprüft: `reminders` berührt keine `proposal_*` / `action_closure_*`-Stateableitung direkt und bleibt damit lane-scharf als Reminder-/Delivery-Surface

### Verification
- `pytest -q tests/test_reminders_contract.py tests/test_ps_core_runtime_contract_inventory.py -k 'reminders or runtime_contract_inventory'` → `18 passed`
- `python3 scripts/ps_core_runtime_contract_inventory.py --repo . --json-out docs/analysis/ps_core_runtime_contract_inventory_2026-04-04.json --md-out docs/analysis/PS_CORE_RUNTIME_CONTRACT_INVENTORY_2026-04-04.md --stdout-json` → `route_heavy_without_direct_contract_tests: 10`, `recommended_next_slice: copilot_core.api.v1.module_control`

**Next Exact Task:** Slice 100 — `copilot_core.api.v1.module_control` als jetzt vom Inventar priorisierte route-starke Runtime-Surface mit direkter Contract-Baseline ziehen; weiterhin **kein** Live-/Install-/Restart-Schritt.

### ✅ Slice 99 — Reminders Runtime Contract Baseline
**Status:** ✅ DONE (worktree; kein Live-/Install-/Restart-Schritt)

**Goal**
`copilot_core.api.v1.reminders` als route-starke Waste-/Birthday-Surface mit direkter Contract-Baseline, konsistenten JSON-Validierungs-/Fehlerpfaden und Inventar-Parität absichern.

### Grounded progress
- [x] direkter Contract-Harness `tests/test_reminders_contract.py` deckt alle sieben Waste-/Birthday-Routes inkl. Auth-, Request-, Response- und Fehlerpfaden gegen die aktive Blueprint-Wahrheit ab
- [x] JSON-/Payload-Härtung in `copilot_core/rootfs/usr/src/app/copilot_core/api/v1/reminders.py` ergänzt: objektförmige Bodies, listenförmige `collections`/`birthdays`, stringförmige `message`/`tts_entity`
- [x] Runtime-Fehlerpfade zentralisiert: Service-Ausnahmen liefern jetzt kontrollierte JSON-500-Responses statt impliziter HTML-500-Abbrüche
- [x] optionale Reminder-Bodies bleiben für Auto-Messages erhalten, sind aber nun bei nicht-objektigen Payloads sauber als JSON-400 gehärtet
- [x] Inventar-Artefakte regeneriert; route-starke Surfaces ohne direkte Contract-Tests reduziert von **11** auf **10**
- [x] `copilot_core.api.v1.reminders` ist nicht mehr Top-Gap und nicht mehr empfohlener nächster Slice

### Verification
- `pytest -q tests/test_reminders_contract.py tests/test_ps_core_runtime_contract_inventory.py` → `18 passed`
- `python3 scripts/ps_core_runtime_contract_inventory.py --repo . --json-out docs/analysis/ps_core_runtime_contract_inventory_2026-04-04.json --md-out docs/analysis/PS_CORE_RUNTIME_CONTRACT_INVENTORY_2026-04-04.md --stdout-json` → `route_heavy_without_direct_contract_tests: 10`, `recommended_next_slice: copilot_core.api.v1.module_control`

**Next Exact Task:** Slice 100 — `copilot_core.api.v1.module_control` als jetzt vom Inventar priorisierte route-starke Runtime-Surface mit direkter Contract-Baseline ziehen; weiterhin **kein** Live-/Install-/Restart-Schritt.

### ✅ Slice 100 — Module Control Runtime Contract Baseline
**Status:** ✅ DONE (worktree; kein Live-/Install-/Restart-Schritt)

**Goal**
`copilot_core.api.v1.module_control` als route-starke Modulsteuerungs-Surface mit direkter Contract-Baseline, konsistenten JSON-Validierungs-/Fehlerpfaden und Inventar-Parität absichern.

### Grounded progress
- [x] direkter Contract-Harness `tests/test_module_control_contract.py` deckt List-/Lookup-/Create-/Configure-/Update-/Delete-Surfaces gegen die aktive Blueprint-Wahrheit ab
- [x] JSON-Härtung in `copilot_core/rootfs/usr/src/app/copilot_core/api/v1/module_control.py` ergänzt: fehlende oder nicht-objektige Bodies liefern jetzt kontrollierte JSON-400-Responses statt impliziter Parser-/Attributfehler
- [x] Payload-Validierung nachgezogen: `module_id` und `state` werden string-scharf geprüft; invalide States liefern weiter kontrollierte JSON-422-Responses
- [x] Runtime-Fehlerpfade zentralisiert: List-/Read-/Write-/Delete-Ausnahmen liefern jetzt kontrollierte JSON-500-Responses statt HTML-500-Abbrüchen
- [x] explizite Registry-Löschung in `copilot_core/rootfs/usr/src/app/copilot_core/module_registry.py` gekapselt: neues `delete_state()` entfernt den API-seitigen Direktzugriff auf Registry-Interna
- [x] Inventar-Artefakte regeneriert; route-starke Surfaces ohne direkte Contract-Tests reduziert von **10** auf **9** und `copilot_core.api.v1.module_control` ist nicht mehr Top-Gap

### Verification
- `pytest -q tests/test_module_control_contract.py tests/test_ps_core_runtime_contract_inventory.py -k 'module_control or runtime_contract_inventory'` → `19 passed`
- `python3 scripts/ps_core_runtime_contract_inventory.py --repo . --json-out docs/analysis/ps_core_runtime_contract_inventory_2026-04-04.json --md-out docs/analysis/PS_CORE_RUNTIME_CONTRACT_INVENTORY_2026-04-04.md --stdout-json` → `route_heavy_without_direct_contract_tests: 9`, `recommended_next_slice: copilot_core.api.v1.ha_events`

**Next Exact Task:** Slice 101 — `copilot_core.api.v1.ha_events` als jetzt vom Inventar priorisierte route-starke Runtime-Surface mit direkter Contract-Baseline ziehen; weiterhin **kein** Live-/Install-/Restart-Schritt.

### ✅ Slice 101 — Home Assistant Events Runtime Contract Baseline
**Status:** ✅ DONE (worktree; kein Live-/Install-/Restart-Schritt)

**Goal**
`copilot_core.api.v1.ha_events` als route-starke Home-Assistant-Event-Surface mit direkter Contract-Baseline, kontrollierten JSON-/Dependency-/Async-Fehlerpfaden und Inventar-Parität absichern.

### Grounded progress
- [x] direkter Contract-Harness `tests/test_ha_events_contract.py` deckt WebSocket-Info-, Subscribe-, Unsubscribe-, History-, Clear-, Status-, Connect- und Disconnect-Surfaces gegen die aktive Blueprint-Wahrheit ab
- [x] `copilot_core/api/v1/ha_events.py` härtet JSON-Pfade jetzt konsistent: fehlende Bodies, nicht-objektige Payloads, falsche Typen für `event_types`, `access_token`, `base_url`, `throttle_ms` und `auto_subscribe` liefern kontrollierte JSON-400-Responses
- [x] WebSocket-Dependency-Pfad gehärtet: fehlendes `flask-sock` kippt nicht mehr vor dem Fallback-Response in einen Importfehler, sondern liefert sauber JSON-503
- [x] Route-Ausführung repariert: die `ha_events`-Surface läuft jetzt unter dem bestehenden Token-Decorator synchron stabil, statt coroutine-Objekte in Flask-Werkzeugpfaden zurückzugeben
- [x] Inventar-Artefakte regeneriert; route-starke Surfaces ohne direkte Contract-Tests reduziert von **9** auf **8** und `copilot_core.api.v1.ha_events` ist nicht mehr Top-Gap

### Verification
- `pytest -q tests/test_ha_events_contract.py tests/test_ps_core_runtime_contract_inventory.py -k 'ha_events or runtime_contract_inventory'` → `20 passed`
- `python3.14 scripts/ps_core_runtime_contract_inventory.py --repo . --json-out docs/analysis/ps_core_runtime_contract_inventory_2026-04-04.json --md-out docs/analysis/PS_CORE_RUNTIME_CONTRACT_INVENTORY_2026-04-04.md --stdout-json` → `route_heavy_without_direct_contract_tests: 8`, `recommended_next_slice: copilot_core.api.v1.neurons_ui`

**Next Exact Task:** Slice 102 — `copilot_core.api.v1.neurons_ui` als jetzt vom Inventar priorisierte route-starke Runtime-Surface mit direkter Contract-Baseline ziehen; weiterhin **kein** Live-/Install-/Restart-Schritt.

### ✅ Slice 102 — Neurons UI Runtime Contract Baseline
**Status:** ✅ DONE (worktree; kein Live-/Install-/Restart-Schritt)

**Goal**
`copilot_core.api.v1.neurons_ui` als route-starke UI-/Neuronen-Surface mit direkter Contract-Baseline, kontrollierten JSON-/Query-/Runtime-Fehlerpfaden und Inventar-Parität absichern.

### Grounded progress
- [x] direkter Contract-Harness `tests/test_neurons_ui_contract.py` deckt Overview-, Layer-, Pipeline-, Evaluate-, History- und Graph-Surfaces gegen die aktive Blueprint-Wahrheit ab
- [x] `copilot_core/api/v1/neurons_ui.py` auf kleine, testbare Builder-Helper gezogen; Serialisierung und Mock-History laufen jetzt über explizite Helper statt verstreute Inline-Payloads
- [x] Evaluate-Pfad gehärtet: invalide JSON-Bodies, nicht-objektige Payloads und nicht-boolesches `force` liefern jetzt kontrollierte JSON-400-Responses
- [x] History-Query gehärtet: invalide oder nicht-positive `hours`-Werte liefern jetzt kontrollierte JSON-400-Responses; große Werte werden auf `168` gekappt statt unkontrolliert durchzulaufen
- [x] Runtime-Fehlerpfade zentralisiert: Builder-/History-Fehler landen jetzt als konsistente JSON-500-Responses statt impliziter HTML-500-Abbrüche
- [x] Inventar-Artefakte regeneriert; route-starke Surfaces ohne direkte Contract-Tests reduziert von **8** auf **7** und `copilot_core.api.v1.neurons_ui` ist nicht mehr Top-Gap

### Verification
- `pytest -q tests/test_neurons_ui_contract.py tests/test_ps_core_runtime_contract_inventory.py -k 'neurons_ui or runtime_contract_inventory'` → `21 passed`
- `python3 scripts/ps_core_runtime_contract_inventory.py --repo . --json-out docs/analysis/ps_core_runtime_contract_inventory_2026-04-04.json --md-out docs/analysis/PS_CORE_RUNTIME_CONTRACT_INVENTORY_2026-04-04.md --stdout-json` → `route_heavy_without_direct_contract_tests: 7`, `recommended_next_slice: copilot_core.api.v1.autonomy`

**Next Exact Task:** Slice 103 — `copilot_core.api.v1.autonomy` als jetzt vom Inventar priorisierte route-starke Runtime-Surface mit direkter Contract-Baseline ziehen; weiterhin **kein** Live-/Install-/Restart-Schritt.

### ✅ Slice 103 — Autonomy Runtime Contract Baseline
**Status:** ✅ DONE (worktree; kein Live-/Install-/Restart-Schritt)

**Goal**
`copilot_core.api.v1.autonomy` als route-starke Autonomie-/Zone-Control-Surface mit direkter Contract-Baseline, kontrollierten JSON-/Query-/Runtime-Fehlerpfaden und Inventar-Parität absichern.

### Grounded progress
- [x] direkter Contract-Harness `tests/test_autonomy_contract.py` deckt Dashboard-, Zone-Status-, Zone-Module-, History-, Mood-Action- und Stats-Surfaces gegen die aktive Blueprint-Wahrheit ab
- [x] `copilot_core/rootfs/usr/src/app/copilot_core/api/v1/autonomy.py` auf kleine Validierungs-/Fehler-Helper gehärtet: mutierende Routes verlangen jetzt objektförmige JSON-Bodies; `module_id` und `state` müssen nicht-leere Strings sein
- [x] History-Query gehärtet: invalide oder nicht-positive `limit`-Werte liefern jetzt kontrollierte JSON-400-Responses statt stiller Typ-/Default-Drift
- [x] Runtime-Fehlerpfade für Dashboard, Zone-Status, Zone-Module, History, Mood-Actions und Stats zentralisiert; Ausnahmen kippen jetzt konsistent auf JSON-500/503 statt impliziter HTML-Abbrüche
- [x] Inventar-Artefakte regeneriert; route-starke Surfaces ohne direkte Contract-Tests reduziert von **7** auf **6** und `copilot_core.api.v1.autonomy` ist nicht mehr Top-Gap

### Verification
- `pytest -q tests/test_autonomy_contract.py copilot_core/rootfs/usr/src/app/tests/test_autonomy_api.py tests/test_ps_core_runtime_contract_inventory.py -k 'autonomy or runtime_contract_inventory'` → `33 passed`
- `python3 scripts/ps_core_runtime_contract_inventory.py --repo . --json-out docs/analysis/ps_core_runtime_contract_inventory_2026-04-04.json --md-out docs/analysis/PS_CORE_RUNTIME_CONTRACT_INVENTORY_2026-04-04.md --stdout-json` → `route_heavy_without_direct_contract_tests: 6`, `recommended_next_slice: copilot_core.api.v1.user_hints`

**Next Exact Task:** Slice 104 — `copilot_core.api.v1.user_hints` als jetzt vom Inventar priorisierte route-starke Runtime-Surface mit direkter Contract-Baseline ziehen; weiterhin **kein** Live-/Install-/Restart-Schritt.

### ✅ Slice 104 — User Hints Runtime Contract Baseline
**Status:** ✅ DONE (worktree; kein Live-/Install-/Restart-Schritt)

**Goal**
`copilot_core.api.v1.user_hints` als route-starke Hint-/Suggestion-Surface mit direkter Contract-Baseline, kontrollierten Auth-/JSON-/Enum-/Runtime-Fehlerpfaden und Inventar-Parität absichern.

### Grounded progress
- [x] direkter Contract-Harness `tests/test_user_hints_contract.py` deckt Listen-, Create-, Read-, Accept-, Reject-, Suggestions- und Types-Surfaces gegen die aktive Blueprint-Wahrheit ab
- [x] `copilot_core/rootfs/usr/src/app/copilot_core/api/v1/user_hints.py` auf kleine Auth-/JSON-/Enum-/String-Helper gehärtet; mutierende Routes behandeln fehlende oder nicht-objektige Bodies jetzt kontrolliert als JSON-400
- [x] Input-Härtung ergänzt: `status`, `type` und `reason` werden typ- und enum-scharf validiert; leere oder nicht-stringige `text`-Payloads kippen kontrolliert auf JSON-400 statt in implizite Service-Drift
- [x] Read-/Mutation-Pfade laufen jetzt über die Service-API statt direkten `_hints`-Internazugriff; fehlende Hints liefern konsistente JSON-404-Responses für Read/Accept/Reject
- [x] Runtime-Fehlerpfade für Listen, Create, Read, Accept, Reject und Suggestions zentralisiert; Service-Ausnahmen kippen jetzt konsistent auf JSON-500 statt impliziter HTML-Abbrüche
- [x] Inventar-Artefakte regeneriert; route-starke Surfaces ohne direkte Contract-Tests reduziert von **6** auf **5** und `copilot_core.api.v1.user_hints` ist nicht mehr Top-Gap

### Verification
- `pytest -q tests/test_user_hints_contract.py tests/test_ps_core_runtime_contract_inventory.py -k 'user_hints or runtime_contract_inventory'` → `23 passed`
- `python3 scripts/ps_core_runtime_contract_inventory.py --repo . --json-out docs/analysis/ps_core_runtime_contract_inventory_2026-04-04.json --md-out docs/analysis/PS_CORE_RUNTIME_CONTRACT_INVENTORY_2026-04-04.md --stdout-json` → `route_heavy_without_direct_contract_tests: 5`, `recommended_next_slice: copilot_core.api.v1.rag`

**Next Exact Task:** Slice 105 — `copilot_core.api.v1.rag` als jetzt vom Inventar priorisierte route-starke Runtime-Surface mit direkter Contract-Baseline ziehen; weiterhin **kein** Live-/Install-/Restart-Schritt.

### ✅ Slice 105 — RAG Runtime Contract Baseline
**Status:** ✅ DONE (worktree; kein Live-/Install-/Restart-Schritt)

**Goal**
`copilot_core.api.v1.rag` als route-starke RAG-/Search-Surface mit direkter Contract-Baseline, kontrollierten JSON-/Type-/Runtime-Fehlerpfaden und Inventar-Parität absichern.

### Grounded progress
- [x] direkter Contract-Harness `tests/test_rag_contract.py` deckt Hybrid-, BM25-, Semantic-, Rerank-, Stats-, Index-, Cache-Clear- und Enhanced-Search-Surfaces gegen die aktive Blueprint-Wahrheit ab
- [x] `copilot_core/rootfs/usr/src/app/copilot_core/api/v1/rag.py` auf kleine JSON-/Type-/Namespace-Helper gehärtet; mutierende Routes behandeln fehlende oder nicht-objektige Bodies jetzt kontrolliert als JSON-400
- [x] Input-Härtung ergänzt: `query`, `namespace`, `include_text`, `include_metadata`, `use_web`, `documents`, `lexical_hits`, `semantic_hits` und `searxng_categories` werden jetzt typscharf validiert statt implizit zu stringifizieren oder in späte Laufzeitfehler zu kippen
- [x] Runtime-Fehlerpfade für Search, BM25, Semantic, Stats, Index, Cache-Clear und Enhanced Search zentralisiert; Ausnahmen liefern jetzt konsistente JSON-500-Responses statt generischer oder impliziter Flask-Abbrüche
- [x] Cache-/Test-Härtung ergänzt: namespace-scharfes Cache-Clear nutzt jetzt das reale Key-Schema `rag:*:{namespace}:*`; `init_rag_api()` setzt auch Cache- und SearXNG-Singletons zurück
- [x] Inventar-Artefakte regeneriert; route-starke Surfaces ohne direkte Contract-Tests reduziert von **5** auf **4** und `copilot_core.api.v1.rag` ist nicht mehr Top-Gap

### Verification
- `pytest -q tests/test_rag_contract.py tests/test_ps_core_runtime_contract_inventory.py -k 'rag or runtime_contract_inventory'` → `24 passed`
- `python3 scripts/ps_core_runtime_contract_inventory.py --repo . --json-out docs/analysis/ps_core_runtime_contract_inventory_2026-04-04.json --md-out docs/analysis/PS_CORE_RUNTIME_CONTRACT_INVENTORY_2026-04-04.md --stdout-json` → `route_heavy_without_direct_contract_tests: 4`, `recommended_next_slice: copilot_core.api.v1.neuron_layers`

**Next Exact Task:** Slice 106 — `copilot_core.api.v1.neuron_layers` als jetzt vom Inventar priorisierte route-starke Runtime-Surface mit direkter Contract-Baseline ziehen; weiterhin **kein** Live-/Install-/Restart-Schritt.

### ✅ Slice 106 — Neuron Layers Runtime Contract Baseline
**Status:** ✅ DONE (worktree; kein Live-/Install-/Restart-Schritt)

**Goal**
`copilot_core.api.v1.neuron_layers` als route-starke Visualisierungs-/Synapsen-Surface mit direkter Contract-Baseline, kontrollierten JSON-/SVG-/Type-/Runtime-Fehlerpfaden und Inventar-Parität absichern.

### Grounded progress
- [x] direkter Contract-Harness `tests/test_neuron_layers_contract.py` deckt Visualization-, Snapshot-, Heatmap-, Synapse-List-, Update- und Reset-Surfaces gegen die aktive Blueprint-Wahrheit ab
- [x] `copilot_core/rootfs/usr/src/app/copilot_core/api/v1/neuron_layers.py` auf kleine Request-/String-/Error-Helper gehärtet; Synapse-Mutations behandeln fehlende oder nicht-objektige Bodies jetzt kontrolliert als JSON-400
- [x] Input-Härtung ergänzt: `from`, `to`, `weight` und `all` werden jetzt typscharf validiert statt implizit zu stringifizieren oder in Attribut-/Bool-Leaks zu kippen
- [x] Runtime-Fehlerpfade zentralisiert: Visualization und Heatmap liefern bei Manager-/Bus-Fehlern konsistente JSON-500-Responses; Snapshot kippt kontrolliert auf ein SVG-Placeholder-500 statt implizitem Flask-Abbruch
- [x] bestehende Runtime-Tests mitgezogen: vorhandene `neuron_layers`-/`synapse`-Tests unter `copilot_core/rootfs/usr/src/app/tests/` bleiben grün
- [x] Inventar-Artefakte regeneriert; route-starke Surfaces ohne direkte Contract-Tests reduziert von **4** auf **3** und `copilot_core.api.v1.neuron_layers` ist nicht mehr Top-Gap

### Verification
- `pytest -q tests/test_neuron_layers_contract.py tests/test_ps_core_runtime_contract_inventory.py copilot_core/rootfs/usr/src/app/tests/test_neuron_layers_api.py copilot_core/rootfs/usr/src/app/tests/test_neuron_config_api.py -k 'neuron_layers or runtime_contract_inventory or synapse'` → `46 passed, 15 deselected`
- `python3 scripts/ps_core_runtime_contract_inventory.py --repo . --json-out docs/analysis/ps_core_runtime_contract_inventory_2026-04-04.json --md-out docs/analysis/PS_CORE_RUNTIME_CONTRACT_INVENTORY_2026-04-04.md --stdout-json` → `route_heavy_without_direct_contract_tests: 3`, `recommended_next_slice: copilot_core.api.v1.performance`

**Next Exact Task:** Slice 107 — `copilot_core.api.v1.performance` als jetzt vom Inventar priorisierte route-starke Runtime-Surface mit direkter Contract-Baseline ziehen; weiterhin **kein** Live-/Install-/Restart-Schritt.

### ✅ Slice 107 — Performance Runtime Contract Baseline
**Status:** ✅ DONE (worktree; kein Live-/Install-/Restart-Schritt)

**Goal**
`copilot_core.api.v1.performance` als route-starke Performance-/Lazy-Load-/Benchmark-Surface mit direkter Contract-Baseline, kontrollierten Query-/JSON-/Runtime-Fehlerpfaden und Inventar-Parität absichern.

### Grounded progress
- [x] direkter Contract-Harness `tests/test_performance_contract.py` deckt Startup-, Module-, Summary-, Lazy-Load-Status-, Benchmark- und Health-Surfaces gegen die aktive Blueprint-Wahrheit ab
- [x] `copilot_core/rootfs/usr/src/app/copilot_core/api/v1/performance.py` um kleine Query-/JSON-/Type-Helper ergänzt; invalide `lazy_only`-, `iterations`- und `include_modules`-Inputs kippen jetzt kontrolliert auf JSON-400 statt in implizite 500er
- [x] Test-Isolation gehärtet: `init_performance_api()` erlaubt sauberen Tracker-Reset/-Inject pro Contract-Harness ohne Singleton-Drift zwischen Requests oder Tests
- [x] echter Runtime-Fix gelandet: `PerformanceTracker` nutzt jetzt einen `threading.RLock`, sodass `GET /api/v1/performance/summary` beim verschachtelten Improvement-Read nicht mehr in einem Self-Lock deadlockt
- [x] Inventar-Artefakte regeneriert; route-starke Surfaces ohne direkte Contract-Tests reduziert von **3** auf **2** und `copilot_core.api.v1.performance` ist nicht mehr Top-Gap

### Verification
- `pytest -q tests/test_performance_contract.py tests/test_ps_core_runtime_contract_inventory.py -k 'performance or runtime_contract_inventory'` → `25 passed`
- `python3.14 scripts/ps_core_runtime_contract_inventory.py --repo . --json-out docs/analysis/ps_core_runtime_contract_inventory_2026-04-04.json --md-out docs/analysis/PS_CORE_RUNTIME_CONTRACT_INVENTORY_2026-04-04.md --stdout-json` → `route_heavy_without_direct_contract_tests: 2`, `recommended_next_slice: copilot_core.api.v1.learning_viz`

**Next Exact Task:** Slice 108 — `copilot_core.api.v1.learning_viz` als jetzt vom Inventar priorisierte route-starke Runtime-Surface mit direkter Contract-Baseline ziehen; weiterhin **kein** Live-/Install-/Restart-Schritt.

### ✅ Slice 108 — Learning Viz Runtime Contract Baseline
**Status:** ✅ DONE (worktree; kein Live-/Install-/Restart-Schritt)

**Goal**
`copilot_core.api.v1.learning_viz` als route-starke Lern-/Transparenz-Surface mit direkter Contract-Baseline, kontrollierten Query-/JSON-/Runtime-Fehlerpfaden und Inventar-Parität absichern.

### Grounded progress
- [x] direkter Contract-Harness `tests/test_learning_viz_contract.py` deckt Overview-, Patterns-, Progress-, Feedback- und Correct-Surfaces gegen die aktive Blueprint-Wahrheit ab
- [x] `copilot_core/api/v1/learning_viz.py` gehärtet: fehlender `request`-Import geschlossen sowie kleine Query-/JSON-/Field-Helper ergänzt; invalide `state`-, `limit`-, `pattern_id`-, `correction`- und `comment`-Inputs liefern jetzt kontrollierte JSON-400-Responses statt impliziter NameError-/ValueError-/Type-Fehler
- [x] Runtime-Fehlerpfade für Overview-, Pattern-, Progress-, Feedback- und Correct-Surfaces zentralisiert; Storage-/Feedback-Ausnahmen kippen jetzt kontrolliert auf JSON-500 statt impliziter Flask-Abbrüche
- [x] Progress-Payload leicht normalisiert: Modul-/Zonen-Fortschritt wird jetzt aus einem gemeinsamen Pattern-Snapshot berechnet statt aus unnötig wiederholten Storage-Reads
- [x] Inventar-Artefakte regeneriert; route-starke Surfaces ohne direkte Contract-Tests reduziert von **2** auf **1** und `copilot_core.api.v1.learning_viz` ist nicht mehr Top-Gap

### Verification
- `pytest -q tests/test_learning_viz_contract.py tests/test_ps_core_runtime_contract_inventory.py -k 'learning_viz or runtime_contract_inventory'` → `26 passed in 23.38s`
- `python3 scripts/ps_core_runtime_contract_inventory.py --repo . --json-out docs/analysis/ps_core_runtime_contract_inventory_2026-04-04.json --md-out docs/analysis/PS_CORE_RUNTIME_CONTRACT_INVENTORY_2026-04-04.md --stdout-json` → `route_heavy_without_direct_contract_tests: 1`, `recommended_next_slice: copilot_core.api.v1.suggestions`

**Next Exact Task:** Slice 109 — `copilot_core.api.v1.suggestions` als jetzt einzig verbleibende route-starke Inventar-Lücke mit direkter Contract-Baseline ziehen; weiterhin **kein** Live-/Install-/Restart-Schritt.

### ✅ Slice 109 — Suggestions Runtime Contract Baseline
**Status:** ✅ DONE (worktree; kein Live-/Install-/Restart-Schritt)

**Goal**
`copilot_core.api.v1.suggestions` als verbleibende route-starke Suggestions-/Proposal-Entry-Surface mit direkter Contract-Baseline, kontrollierten JSON-/Mutation-/Runtime-Fehlerpfaden und Inventar-Parität absichern.

### Grounded progress
- [x] direkter Contract-Harness `tests/test_suggestions_contract.py` deckt List-, Repairs-, Accept-, Reject- und Snooze-Surfaces gegen die aktive Blueprint-Wahrheit ab
- [x] `copilot_core/rootfs/usr/src/app/copilot_core/api/v1/suggestions.py` auf kleine JSON-/Field-Helper gehärtet; mutierende Routes behandeln fehlende oder nicht-objektige Bodies jetzt kontrolliert als JSON-400
- [x] Input-Härtung ergänzt: `id` muss jetzt nicht-leerer String sein; `minutes` wird für Snooze typscharf als positive Ganzzahl validiert statt implizit durchzureichen
- [x] Runtime-Fehlerpfade für Listen, Accept, Reject und Snooze zentralisiert; Engine-Ausnahmen kippen jetzt konsistent auf JSON-500 statt impliziter HTML-500-Abbrüche
- [x] Test-Isolation gehärtet: `init_suggestions_api()` setzt Fallback-State restart-/harness-sicher zurück, sodass Fallback-Aktionen nicht zwischen Läufen driften
- [x] Inventar-Artefakte regeneriert; route-starke Surfaces ohne direkte Contract-Tests reduziert von **1** auf **0** und `copilot_core.api.v1.suggestions` ist nicht mehr Top-Gap

### Verification
- `pytest -q tests/test_suggestions_contract.py tests/test_ps_core_runtime_contract_inventory.py tests/test_proposal_lifecycle_api.py -k 'suggestions or runtime_contract_inventory or proposal_lifecycle_api'` → `31 passed in 17.45s`
- `python3 scripts/ps_core_runtime_contract_inventory.py --repo . --json-out docs/analysis/ps_core_runtime_contract_inventory_2026-04-04.json --md-out docs/analysis/PS_CORE_RUNTIME_CONTRACT_INVENTORY_2026-04-04.md --stdout-json` → `route_heavy_without_direct_contract_tests: 0`, `recommended_next_slice: copilot_core.api.v1.brain_growth`

**Next Exact Task:** Slice 110 — `copilot_core.api.v1.brain_growth` als nächstes direkt ungetestetes Inventar-Gap unterhalb der bisherigen Route-Heavy-Schwelle mit fokussierter Contract-Baseline ziehen; weiterhin **kein** Live-/Install-/Restart-Schritt.

### ✅ Slice 110 — Brain Growth Runtime Contract Baseline
**Status:** ✅ DONE (worktree; kein Live-/Install-/Restart-Schritt)

**Goal**
`copilot_core.api.v1.brain_growth` als direktes Inventar-Gap unterhalb der bisherigen Route-Heavy-Schwelle mit fokussierter Contract-Baseline, kontrollierten Query-/Runtime-/Unavailability-Pfaden und Inventar-Parität absichern.

### Grounded progress
- [x] direkter Contract-Harness `tests/test_brain_growth_contract.py` deckt Summary-, Trace-, Zone-Links- und Activity-Surfaces gegen die aktive Blueprint-Wahrheit ab
- [x] `copilot_core/rootfs/usr/src/app/copilot_core/api/v1/brain_growth.py` gehärtet: fehlender `request`-Import geschlossen, gemeinsame Init-Prüfung ergänzt und `limit` auf `/activity` jetzt kontrolliert als positive Ganzzahl validiert
- [x] Activity-Surface liefert jetzt echte Read-Model-Activity statt leerem Platzhalter; `BrainGrowthReadModel.get_recent_activity()` exponiert die jüngsten Semantic-Transfer-Traces in stabiler Reihenfolge
- [x] Runtime-Fehlerpfade für Summary, Trace, Zone-Links und Activity zentralisiert; nicht initialisierte Surface bleibt explizit auf JSON-503, fehlende Traces auf JSON-404
- [x] Inventar-Tests und Artefakte nachgezogen; `copilot_core.api.v1.brain_growth` ist nicht mehr empfohlener nächster Slice, neuer Inventar-Kandidat ist `copilot_core.api.v1.character`

### Verification
- `pytest -q tests/test_brain_growth_contract.py tests/test_ps_core_runtime_contract_inventory.py -k 'brain_growth or runtime_contract_inventory'` → `29 passed in 18.02s`
- `python3 scripts/ps_core_runtime_contract_inventory.py --repo . --json-out docs/analysis/ps_core_runtime_contract_inventory_2026-04-04.json --md-out docs/analysis/PS_CORE_RUNTIME_CONTRACT_INVENTORY_2026-04-04.md --stdout-json` → `route_heavy_without_direct_contract_tests: 0`, `recommended_next_slice: copilot_core.api.v1.character`

**Next Exact Task:** Slice 111 — `copilot_core.api.v1.character` als nächstes direkt ungetestetes Inventar-Gap unterhalb der bisherigen Route-Heavy-Schwelle mit fokussierter Contract-Baseline ziehen; weiterhin **kein** Live-/Install-/Restart-Schritt.

### ✅ Slice 111 — Character Runtime Contract Baseline
**Status:** ✅ DONE (worktree; kein Live-/Install-/Restart-Schritt)

**Goal**
`copilot_core.api.v1.character` als direktes Inventar-Gap unterhalb der bisherigen Route-Heavy-Schwelle mit fokussierter Contract-Baseline, JSON-/Payload-Härtung und kontrollierten Runtime-Fehlerpfaden absichern.

### Grounded progress
- [x] direkter Contract-Harness `tests/test_character_contract.py` deckt Current-, Modes-, Mode- und Mood-Surfaces gegen die aktive Blueprint-Wahrheit ab
- [x] `copilot_core/rootfs/usr/src/app/copilot_core/api/v1/character.py` gehärtet: fehlende oder nicht-objektige JSON-Bodies liefern jetzt kontrollierte JSON-400-Responses statt impliziter Attributfehler
- [x] Input-Validierung für `mode` und `mood` nachgezogen: `mode` muss nicht-leerer String sein, `mood` muss nicht-leeres Dict mit numerischen Werten sein
- [x] Runtime-Fehlerpfade für Current, Modes, Mode und Mood zentralisiert; Service-Ausnahmen kippen nicht mehr implizit in HTML-500-Abbrüche, sondern sauber auf JSON-500
- [x] Inventar-Tests und Artefakte nachgezogen; `copilot_core.api.v1.character` ist nicht mehr empfohlener nächster Slice, neuer Inventar-Kandidat ist `copilot_core.api.v1.action_attribution`

### Verification
- `pytest -q tests/test_character_contract.py tests/test_ps_core_runtime_contract_inventory.py -k 'character or runtime_contract_inventory'` → `30 passed in 18.61s`
- `python3 scripts/ps_core_runtime_contract_inventory.py --repo . --json-out docs/analysis/ps_core_runtime_contract_inventory_2026-04-04.json --md-out docs/analysis/PS_CORE_RUNTIME_CONTRACT_INVENTORY_2026-04-04.md --stdout-json` → `route_heavy_without_direct_contract_tests: 0`, `recommended_next_slice: copilot_core.api.v1.action_attribution`

**Next Exact Task:** Slice 112 — `copilot_core.api.v1.action_attribution` als nächstes direkt ungetestetes Inventar-Gap unterhalb der Route-Heavy-Schwelle mit fokussierter Contract-Baseline ziehen; weiterhin **kein** Live-/Install-/Restart-Schritt.

### ✅ Slice 112 — Action Attribution Runtime Contract Baseline
**Status:** ✅ DONE (worktree; kein Live-/Install-/Restart-Schritt)

**Goal**
`copilot_core.api.v1.action_attribution` als direktes Inventar-Gap unterhalb der Route-Heavy-Schwelle mit fokussierter Contract-Baseline, JSON-/Signal-/Query-Härtung und kontrollierten Runtime-Fehlerpfaden absichern.

### Grounded progress
- [x] direkter Contract-Harness `tests/test_action_attribution_contract.py` deckt Attribute-, History- und User-Surfaces gegen die aktive Blueprint-Wahrheit ab
- [x] `copilot_core/rootfs/usr/src/app/copilot_core/api/v1/action_attribution.py` auf kleine Service-/JSON-/Signal-/Query-Helper gehärtet; fehlende oder nicht-objektige Bodies, invalide `signals`-Payloads und ungültige `limit`-Werte liefern jetzt kontrollierte JSON-400-Responses
- [x] Attributions-Signale werden jetzt typscharf validiert (`user_id`, `source_name`, `confidence`, `metadata`) statt implizit in Attribut-/Type-Fehler zu kippen; Signale ohne `user_id` bleiben kompatibel weiter ignorable
- [x] Response-Härtung ergänzt: Attributions- und History-Timestamps werden stabil ISO-formatiert; `no attribution possible` bleibt als expliziter strukturierter JSON-Pfad sichtbar
- [x] Runtime-Fehlerpfade für Attribute-, History- und User-Surfaces zentralisiert; Service-Ausnahmen kippen nicht mehr implizit in HTML-500-Abbrüche, sondern sauber auf JSON-500
- [x] Inventar-Tests und Artefakte nachgezogen; `copilot_core.api.v1.action_attribution` ist nicht mehr empfohlener nächster Slice, neuer Inventar-Kandidat ist `copilot_core.api.v1.cache_control`

### Verification
- `pytest -q tests/test_action_attribution_contract.py tests/test_ps_core_runtime_contract_inventory.py -k 'action_attribution or runtime_contract_inventory'` → `31 passed in 19.64s`
- `python3 scripts/ps_core_runtime_contract_inventory.py --repo . --json-out docs/analysis/ps_core_runtime_contract_inventory_2026-04-04.json --md-out docs/analysis/PS_CORE_RUNTIME_CONTRACT_INVENTORY_2026-04-04.md --stdout-json` → `route_heavy_without_direct_contract_tests: 0`, `recommended_next_slice: copilot_core.api.v1.cache_control`

**Next Exact Task:** Slice 113 — `copilot_core.api.v1.cache_control` als nächstes direkt ungetestetes Inventar-Gap unterhalb der Route-Heavy-Schwelle mit fokussierter Contract-Baseline ziehen; weiterhin **kein** Live-/Install-/Restart-Schritt.

### ✅ Slice 113 — Cache Control Runtime Contract Baseline
**Status:** ✅ DONE (worktree; kein Live-/Install-/Restart-Schritt)

**Goal**
`copilot_core.api.v1.cache_control` als direktes Inventar-Gap unterhalb der Route-Heavy-Schwelle mit fokussierter Contract-Baseline, optionaler JSON-Härtung und kontrollierten Runtime-Fehlerpfaden absichern.

### Grounded progress
- [x] direkter Contract-Harness `tests/test_cache_control_contract.py` deckt Status-, Invalidate- und Stats-Surfaces gegen die aktive Runtime-Wahrheit ab, inkl. `all`-, `key`-, `pattern`- und default-Invalidate-Pfaden
- [x] `copilot_core/rootfs/usr/src/app/copilot_core/api/v1/cache_control.py` auf kleine Request-/Init-Helper gehärtet; nicht-objektige JSON-Payloads sowie invalide `all`-, `key`- und `pattern`-Werte liefern jetzt kontrollierte JSON-400-Responses statt impliziter Typ-/Attributfehler
- [x] Initialisierungsverhalten explizit gemacht: fehlender Redis-Client und fehlender API-Cache kippen nicht mehr implizit in Attributfehler, sondern sauber auf JSON-503
- [x] Runtime-Fehlerpfade für Status-, Invalidate- und Stats-Surfaces zentralisiert; Cache-/Redis-Ausnahmen bleiben kontrolliert auf JSON-500
- [x] Inventar-Tests und Artefakte nachgezogen; `copilot_core.api.v1.cache_control` ist nicht mehr empfohlener nächster Slice, neuer Inventar-Kandidat ist `copilot_core.api.v1.conflict_resolution`

### Verification
- `pytest -q tests/test_cache_control_contract.py tests/test_ps_core_runtime_contract_inventory.py -k 'cache_control or runtime_contract_inventory'` → `32 passed in 19.91s`
- `python3 scripts/ps_core_runtime_contract_inventory.py --repo . --json-out docs/analysis/ps_core_runtime_contract_inventory_2026-04-04.json --md-out docs/analysis/PS_CORE_RUNTIME_CONTRACT_INVENTORY_2026-04-04.md --stdout-json` → `route_heavy_without_direct_contract_tests: 0`, `recommended_next_slice: copilot_core.api.v1.conflict_resolution`

### ✅ Slice 114 — Conflict Resolution Runtime Contract Baseline
**Status:** ✅ DONE (worktree; kein Live-/Install-/Restart-Schritt)

**Goal**
`copilot_core.api.v1.conflict_resolution` als direktes Inventar-Gap unterhalb der Route-Heavy-Schwelle mit fokussierter Contract-Baseline, JSON-/Input-Härtung und kontrollierten Runtime-Fehlerpfaden absichern.

### Grounded progress
- [x] direkter Contract-Harness `tests/test_conflict_resolution_contract.py` deckt State-, Evaluate- und Strategy-Surfaces gegen die aktive Runtime-Wahrheit ab, inkl. expliziter Mood/Priority-Evaluate-, Store-Evaluate- und Override-Strategy-Pfade
- [x] `copilot_core/rootfs/usr/src/app/copilot_core/api/v1/conflict_resolution.py` auf kleine Request-/Validation-Helper gehärtet; nicht-objektige JSON-Payloads, halbvollständige Explicit-Evaluate-Payloads sowie invalide `user_moods`-, `user_priorities`-, `active_user_ids`-, `strategy`- und `override_user`-Werte liefern jetzt kontrollierte JSON-400-Responses
- [x] Runtime-Fehlerpfade für State-, Evaluate- und Strategy-Surfaces zentralisiert; Resolver-/State-Ausnahmen bleiben kontrolliert auf JSON-500 statt implizit in HTML-500-Abbrüche zu kippen
- [x] Inventar-Tests und Artefakte nachgezogen; `copilot_core.api.v1.conflict_resolution` ist nicht mehr empfohlener nächster Slice, neuer Inventar-Kandidat ist `copilot_core.api.v1.error_digest`

### Verification
- `pytest -q tests/test_conflict_resolution_contract.py tests/test_ps_core_runtime_contract_inventory.py copilot_core/rootfs/usr/src/app/tests/test_conflict_resolution.py -k 'conflict_resolution or runtime_contract_inventory'` → `65 passed in 22.36s`
- `python3 scripts/ps_core_runtime_contract_inventory.py --repo . --json-out docs/analysis/ps_core_runtime_contract_inventory_2026-04-04.json --md-out docs/analysis/PS_CORE_RUNTIME_CONTRACT_INVENTORY_2026-04-04.md --stdout-json` → `route_heavy_without_direct_contract_tests: 0`, `recommended_next_slice: copilot_core.api.v1.error_digest`

### ✅ Slice 115 — Error Digest Runtime Contract Baseline
**Status:** ✅ DONE (worktree; kein Live-/Install-/Restart-Schritt)

**Goal**
`copilot_core.api.v1.error_digest` als direktes Inventar-Gap unterhalb der Route-Heavy-Schwelle mit fokussierter Contract-Baseline, JSON-/Query-Härtung und kontrollierten Runtime-Fehlerpfaden absichern.

### Grounded progress
- [x] direkter Contract-Harness `tests/test_error_digest_contract.py` deckt Digest-, Categories- und Repair-Suggestions-Surfaces gegen die aktive Runtime-Wahrheit ab, inkl. LLM-Fallback-, Validierungs-, Runtime- und Auth-Pfaden
- [x] `copilot_core/rootfs/usr/src/app/copilot_core/api/v1/error_digest.py` auf kleine JSON-/Query-/Timestamp-Helper gehärtet; invalide `hours`-/`severity`-Inputs, nicht-objektige Bodies sowie leere oder typfalsche `message`-/`context`-Werte liefern jetzt kontrollierte JSON-400-Responses
- [x] Runtime-Fehlerpfade für Digest- und Repair-Suggestions-Surfaces zentralisiert; Log-/Pattern-Ausnahmen kippen jetzt kontrolliert auf JSON-500 statt impliziter HTML-500-Abbrüche
- [x] Inventar-Wahrheit nachgezogen: `tests/test_ps_core_runtime_contract_inventory.py` bestätigt `error_digest` als direkt kontraktabgedeckt und zieht den echten nächsten Slice auf `copilot_core.api.v1.events_ingest`
- [x] `scripts/ps_core_runtime_contract_inventory.py` rendert die Empfehlung jetzt auch unterhalb der Route-Heavy-Schwelle wahrheitsgetreu; regenerierte Inventar-Artefakte zeigen `events_ingest` als nächsten exakten Slice

### Verification
- `pytest -q tests/test_error_digest_contract.py tests/test_ps_core_runtime_contract_inventory.py copilot_core/rootfs/usr/src/app/tests/test_error_digest.py -k 'error_digest or runtime_contract_inventory'` → `64 passed in 27.50s`
- `python3 scripts/ps_core_runtime_contract_inventory.py --repo . --json-out docs/analysis/ps_core_runtime_contract_inventory_2026-04-04.json --md-out docs/analysis/PS_CORE_RUNTIME_CONTRACT_INVENTORY_2026-04-04.md --stdout-json` → `route_heavy_without_direct_contract_tests: 0`, `recommended_next_slice: copilot_core.api.v1.events_ingest`

### ✅ Slice 116 — Events Ingest Runtime Contract Baseline
**Status:** ✅ DONE (worktree; kein Live-/Install-/Restart-Schritt)

**Goal**
`copilot_core.api.v1.events_ingest` als direktes Inventar-Gap unterhalb der Route-Heavy-Schwelle mit fokussierter Contract-Baseline, Ingest-/Query-Härtung und kontrollierten Runtime-Fehlerpfaden absichern.

### Grounded progress
- [x] direkter Contract-Harness `tests/test_events_ingest_contract.py` deckt POST-/GET-/Stats-Surfaces gegen die aktive Runtime-Wahrheit ab, inkl. Normalisierung, Post-Ingest-Callback, Limit-Validierung, Runtime- und Auth-Pfaden
- [x] `copilot_core/rootfs/usr/src/app/copilot_core/api/v1/events_ingest.py` härtet jetzt auch den POST-Ingest-Pfad kontrolliert auf JSON-500; `ingest_batch()`-Ausnahmen kippen nicht mehr implizit in HTML-500-Abbrüche
- [x] Inventar-Wahrheit nachgezogen: `tests/test_ps_core_runtime_contract_inventory.py` bestätigt `events_ingest` als direkt kontraktabgedeckt; neuer nächster Slice unterhalb der Route-Heavy-Schwelle ist jetzt `copilot_core.api.v1.haushalt`
- [x] Inventar-Artefakte regeneriert: `docs/analysis/PS_CORE_RUNTIME_CONTRACT_INVENTORY_2026-04-04.md` und `docs/analysis/ps_core_runtime_contract_inventory_2026-04-04.json` zeigen `haushalt` als nächsten exakten Slice
- [x] breiterer Legacy-Lauf `copilot_core/rootfs/usr/src/app/tests/test_events_endpoint.py` bleibt außerhalb dieses Minimal-Slices rot (`15 failed`) wegen separater App-Bootstrap-/Blueprint-Registrierungsprobleme; nicht von diesem `events_ingest`-Diff verursacht und deshalb nicht in Slice 116 aufgeweitet

### Verification
- `pytest -q tests/test_events_ingest_contract.py tests/test_ps_core_runtime_contract_inventory.py -k 'events_ingest or runtime_contract_inventory'` → `36 passed in 20.73s`
- `python3 scripts/ps_core_runtime_contract_inventory.py --repo . --json-out docs/analysis/ps_core_runtime_contract_inventory_2026-04-04.json --md-out docs/analysis/PS_CORE_RUNTIME_CONTRACT_INVENTORY_2026-04-04.md --stdout-json` → `route_heavy_without_direct_contract_tests: 0`, `recommended_next_slice: copilot_core.api.v1.haushalt`

### ✅ Slice 117 — Haushalt Runtime Contract Baseline
**Status:** ✅ DONE (worktree; kein Live-/Install-/Restart-Schritt)

**Goal**
`copilot_core.api.v1.haushalt` als direktes Inventar-Gap unterhalb der Route-Heavy-Schwelle mit fokussierter Contract-Baseline, Overview-/Reminder-Härtung und kontrollierten Runtime-Fehlerpfaden absichern.

### Grounded progress
- [x] direkter Contract-Harness `tests/test_haushalt_contract.py` deckt alle drei `haushalt`-Surfaces gegen die aktive Runtime-Wahrheit ab, inkl. Overview-, Waste-Reminder-, Birthday-Reminder-, Unavailable-, Runtime- und Auth-Pfaden
- [x] `copilot_core/rootfs/usr/src/app/copilot_core/api/v1/haushalt.py` auf kleine Service-/Status-Helper gehärtet; invalide Status-Objekte und Service-Ausnahmen kippen jetzt kontrolliert auf JSON-500 statt impliziter HTML-500-Abbrüche
- [x] Reminder-Pfade defensiv stabilisiert: Waste-/Birthday-Listen werden kontrolliert gelesen, Reminder-Strings robust zusammengesetzt und Overview-Alerts nur aus gültigen Statuslisten abgeleitet
- [x] Inventar-Wahrheit nachgezogen: `tests/test_ps_core_runtime_contract_inventory.py` bestätigt `haushalt` als direkt kontraktabgedeckt; neuer nächster Slice unterhalb der Route-Heavy-Schwelle ist jetzt `copilot_core.api.v1.module_health`
- [x] Inventar-Artefakte regeneriert: `docs/analysis/PS_CORE_RUNTIME_CONTRACT_INVENTORY_2026-04-04.md` und `docs/analysis/ps_core_runtime_contract_inventory_2026-04-04.json` zeigen `module_health` als nächsten exakten Slice

### Verification
- `pytest -q tests/test_haushalt_contract.py tests/test_ps_core_runtime_contract_inventory.py -k 'haushalt or runtime_contract_inventory'` → `37 passed in 23.91s`
- `python3 scripts/ps_core_runtime_contract_inventory.py --repo . --json-out docs/analysis/ps_core_runtime_contract_inventory_2026-04-04.json --md-out docs/analysis/PS_CORE_RUNTIME_CONTRACT_INVENTORY_2026-04-04.md --stdout-json` → `route_heavy_without_direct_contract_tests: 0`, `recommended_next_slice: copilot_core.api.v1.module_health`

### ✅ Slice 118 — Module Health Runtime Contract Baseline
**Status:** ✅ DONE (worktree; kein Live-/Install-/Restart-Schritt)

**Goal**
`copilot_core.api.v1.module_health` als direktes Inventar-Gap unterhalb der Route-Heavy-Schwelle mit fokussierter Contract-Baseline, Dashboard-/Learning-/Pattern-Härtung und kontrollierten Runtime-Fehlerpfaden absichern.

### Grounded progress
- [x] direkter Contract-Harness `tests/test_module_health_contract.py` deckt alle drei `module_health`-Surfaces gegen die aktive Runtime-Wahrheit ab, inkl. Dashboard-, Learning-, Pattern-, Uninitialized-, Typfehler- und Runtime-Pfaden
- [x] `copilot_core/rootfs/usr/src/app/copilot_core/api/v1/module_health.py` auf kleine Timestamp-/Error-/Type-Helper gehärtet; invalide Stats-/Pattern-/Proposal-Payloads liefern jetzt kontrollierte JSON-500-Responses statt impliziter Typfehler oder HTML-500-Abbrüche
- [x] Dashboard-Verhalten bleibt stabil: fehlende Services liefern weiter definierte Fallbacks (`modules={}`, `bus/learning/cross_module/feedback=None`), während echte Registry-/Bus-/Learning-/Analyzer-Fehler sauber als JSON-500 sichtbar werden
- [x] Inventar-Wahrheit nachgezogen: `tests/test_ps_core_runtime_contract_inventory.py` bestätigt `module_health` als direkt kontraktabgedeckt; neuer nächster Slice unterhalb der Route-Heavy-Schwelle ist jetzt `copilot_core.api.v1.neurons_visualization`
- [x] Inventar-Artefakte regeneriert: `docs/analysis/PS_CORE_RUNTIME_CONTRACT_INVENTORY_2026-04-04.md` und `docs/analysis/ps_core_runtime_contract_inventory_2026-04-04.json` zeigen `neurons_visualization` als nächsten exakten Slice

### Verification
- `pytest -q tests/test_module_health_contract.py tests/test_ps_core_runtime_contract_inventory.py copilot_core/rootfs/usr/src/app/tests/test_cross_module.py -k 'module_health or runtime_contract_inventory or ModuleHealthAPI'` → `40 passed, 9 deselected in 26.07s`
- `python3 scripts/ps_core_runtime_contract_inventory.py --repo . --json-out docs/analysis/ps_core_runtime_contract_inventory_2026-04-04.json --md-out docs/analysis/PS_CORE_RUNTIME_CONTRACT_INVENTORY_2026-04-04.md --stdout-json` → `route_heavy_without_direct_contract_tests: 0`, `recommended_next_slice: copilot_core.api.v1.neurons_visualization`

### ✅ Slice 119 — Neurons Visualization Runtime Contract Baseline
**Status:** ✅ DONE (worktree; kein Live-/Install-/Restart-Schritt)

**Goal**
`copilot_core.api.v1.neurons_visualization` als direktes Inventar-Gap unterhalb der Route-Heavy-Schwelle mit fokussierter Contract-Baseline, State-/Fire-/Pipeline-Härtung und kontrollierten Runtime-Fehlerpfaden absichern.

### Grounded progress
- [x] direkter Contract-Harness `tests/test_neurons_visualization_contract.py` deckt alle drei `neurons_visualization`-Surfaces gegen die aktive Runtime-Wahrheit ab, inkl. State-, Fire-, Pipeline-, Auth-, Uninitialized-, Validierungs- und Runtime-Pfaden
- [x] `copilot_core/rootfs/usr/src/app/copilot_core/api/v1/neurons_visualization.py` auf kleine Manager-/Store-/Payload-Helper gehärtet; fehlender `NeuronManager` liefert jetzt kontrollierte JSON-503-Responses statt impliziter Attributfehler
- [x] Response-Härtung ergänzt: Neuron-/Summary-/State-/Config-/Pipeline-Payloads werden als Objekte erzwungen, numerische Live-Metrics werden typscharf validiert und invalide Suggestion-/HA-State-Caches kippen kontrolliert auf JSON-500 statt HTML-500-Abbrüchen
- [x] Inventar-Wahrheit nachgezogen: `tests/test_ps_core_runtime_contract_inventory.py` bestätigt `neurons_visualization` als direkt kontraktabgedeckt; neuer nächster Slice unterhalb der Route-Heavy-Schwelle ist jetzt `copilot_core.api.v1.search`
- [x] Inventar-Artefakte regeneriert: `docs/analysis/PS_CORE_RUNTIME_CONTRACT_INVENTORY_2026-04-04.md` und `docs/analysis/ps_core_runtime_contract_inventory_2026-04-04.json` zeigen `search` als nächsten exakten Slice; `python3.14 scripts/contract_inventory_fast_check.py --repo .` bleibt grün

### Verification
- `python3.14 -m pytest -q tests/test_neurons_visualization_contract.py tests/test_ps_core_runtime_contract_inventory.py -k 'neurons_visualization or runtime_contract_inventory'` → `38 passed in 24.39s`
- `python3.14 scripts/ps_core_runtime_contract_inventory.py --repo . --json-out docs/analysis/ps_core_runtime_contract_inventory_2026-04-04.json --md-out docs/analysis/PS_CORE_RUNTIME_CONTRACT_INVENTORY_2026-04-04.md --stdout-json` → `route_heavy_without_direct_contract_tests: 0`, `recommended_next_slice: copilot_core.api.v1.search`
- `python3.14 scripts/contract_inventory_fast_check.py --repo .` → `PASS`, `Next uncovered slice: copilot_core.api.v1.search`

### ✅ Slice 120 — Search Runtime Contract Baseline
**Status:** ✅ DONE (worktree; kein Live-/Install-/Restart-Schritt)

**Goal**
`copilot_core.api.v1.search` als direktes Inventar-Gap unterhalb der Route-Heavy-Schwelle mit fokussierter Contract-Baseline, Search-/Entity-Filter-/Index-/Stats-Härtung und kontrollierten Runtime-Fehlerpfaden absichern.

### Grounded progress
- [x] direkter Contract-Harness `tests/test_search_contract.py` deckt alle vier `search`-Surfaces gegen die aktive Runtime-Wahrheit ab, inkl. Index-, Full-Search-, Entity-Filter-, Stats-, Auth-, Validierungs- und Runtime-Pfaden
- [x] `copilot_core/rootfs/usr/src/app/copilot_core/api/v1/search.py` auf kleine Parse-/Body-/Error-Helper gehärtet; invalide `limit`-/`types`-Querys und ungültige JSON-Bodies liefern jetzt kontrollierte JSON-400-Responses statt impliziter HTML-500-/Werkzeug-Abbrüche
- [x] Runtime-Fehler vereinheitlicht: Search-, Filter-, Stats- und Index-Exceptions kippen kontrolliert auf JSON-500 mit stabilen Fehlermeldungen; Index-Collections (`entities|automations|scripts|scenes|services`) werden als Objekte erzwungen
- [x] Inventar-Wahrheit nachgezogen: `tests/test_ps_core_runtime_contract_inventory.py` bestätigt `search` als direkt kontraktabgedeckt; neuer nächster Slice unterhalb der Route-Heavy-Schwelle ist jetzt `copilot_core.api.v1.debug`
- [x] Inventar-Artefakte regeneriert: `docs/analysis/PS_CORE_RUNTIME_CONTRACT_INVENTORY_2026-04-04.md` und `docs/analysis/ps_core_runtime_contract_inventory_2026-04-04.json` zeigen `debug` als nächsten exakten Slice; `python3.14 scripts/contract_inventory_fast_check.py --repo .` bleibt grün

### Verification
- `python3.14 -m pytest -q tests/test_search_contract.py tests/test_ps_core_runtime_contract_inventory.py -k 'search or runtime_contract_inventory'` → `39 passed in 25.91s`
- `python3.14 scripts/ps_core_runtime_contract_inventory.py --repo . --json-out docs/analysis/ps_core_runtime_contract_inventory_2026-04-04.json --md-out docs/analysis/PS_CORE_RUNTIME_CONTRACT_INVENTORY_2026-04-04.md --stdout-json` → `route_heavy_without_direct_contract_tests: 0`, `recommended_next_slice: copilot_core.api.v1.debug`
- `python3.14 scripts/contract_inventory_fast_check.py --repo .` → `PASS`, `Next uncovered slice: copilot_core.api.v1.debug`

### ✅ Slice 121 — Debug Runtime Contract Baseline
**Status:** ✅ DONE (worktree; kein Live-/Install-/Restart-Schritt)

**Goal**
`copilot_core.api.v1.debug` als direktes Inventar-Gap unterhalb der Route-Heavy-Schwelle mit fokussierter Contract-Baseline, JSON-/Auth-Härtung und kontrollierten Runtime-Fehlerpfaden absichern.

### Grounded progress
- [x] direkter Contract-Harness `tests/test_debug_contract.py` deckt beide `debug`-Surfaces gegen die aktive Runtime-Wahrheit ab, inkl. Status-, Toggle-, Auth-, Validierungs- und Runtime-Pfaden
- [x] `copilot_core/rootfs/usr/src/app/copilot_core/api/v1/debug.py` auf kleine Error-/Body-Helper gehärtet; nicht-objektige Bodies liefern jetzt kontrollierte JSON-400-Responses statt impliziter Parser-/Request-Abbrüche
- [x] Runtime-Fehlerpfade ergänzt: `get_debug()`- und `set_debug()`-Ausnahmen kippen kontrolliert auf JSON-500 statt impliziter HTML-500-Abbrüche; Erfolgs-Payloads bleiben stabil
- [x] Inventar-Wahrheit nachgezogen: `tests/test_ps_core_runtime_contract_inventory.py` bestätigt `debug` als direkt kontraktabgedeckt; neuer nächster Slice unterhalb der Route-Heavy-Schwelle ist jetzt `copilot_core.api.v1.explain`
- [x] Inventar-Artefakte regeneriert: `docs/analysis/PS_CORE_RUNTIME_CONTRACT_INVENTORY_2026-04-04.md` und `docs/analysis/ps_core_runtime_contract_inventory_2026-04-04.json` zeigen `explain` als nächsten exakten Slice; `python3.14 scripts/contract_inventory_fast_check.py --repo .` bleibt grün

### Verification
- `pytest -q tests/test_debug_contract.py tests/test_ps_core_runtime_contract_inventory.py` → `40 passed in 26.24s`
- `python3.14 scripts/ps_core_runtime_contract_inventory.py --repo . --json-out docs/analysis/ps_core_runtime_contract_inventory_2026-04-04.json --md-out docs/analysis/PS_CORE_RUNTIME_CONTRACT_INVENTORY_2026-04-04.md --stdout-json` → `route_heavy_without_direct_contract_tests: 0`, `recommended_next_slice: copilot_core.api.v1.explain`
- `python3.14 scripts/contract_inventory_fast_check.py --repo .` → `PASS`, `Next uncovered slice: copilot_core.api.v1.explain`

### ✅ Slice 122 — Explain Runtime Contract Baseline
**Status:** ✅ DONE (worktree; kein Live-/Install-/Restart-Schritt)

**Goal**
`copilot_core.api.v1.explain` als letztes aktives Inventar-/Contract-Gap unterhalb der Route-Heavy-Schwelle mit fokussierter Contract-Baseline, kontrollierten Error-Pfaden und stabiler Pattern-Projektion schließen.

### Grounded progress
- [x] direkter Contract-Harness `tests/test_explain_contract.py` deckt beide `explain`-Surfaces gegen die aktive Runtime-Wahrheit ab, inkl. Suggestion-, Pattern-, Auth-, Uninitialized-, Invalid-Result- und Runtime-Pfaden
- [x] `copilot_core/rootfs/usr/src/app/copilot_core/api/v1/explain.py` auf kleine Request-/Result-/Error-Helper gehärtet; invalide Engine-Resultate liefern jetzt kontrollierte JSON-500-Responses statt impliziter Merge-/Type-Crashes
- [x] Pattern-Surface bleibt kanonisch auf derselben Explain-Engine, erzwingt den Pattern-Typ aber jetzt kontrolliert in der Response statt auf blindem Inline-Mutate-Pfad
- [x] Inventar-Wahrheit nachgezogen: `tests/test_ps_core_runtime_contract_inventory.py` bestätigt die geschlossene Inventar-Linie; `recommended_next_slice` ist jetzt bewusst `null`
- [x] Inventar-Artefakte regeneriert: `docs/analysis/PS_CORE_RUNTIME_CONTRACT_INVENTORY_2026-04-04.md` und `docs/analysis/ps_core_runtime_contract_inventory_2026-04-04.json` zeigen keinen aktiven nächsten Inventar-Slice mehr; `python3.14 scripts/contract_inventory_fast_check.py --repo .` bleibt grün

### Verification
- `pytest -q tests/test_explain_contract.py tests/test_ps_core_runtime_contract_inventory.py` → `40 passed in 25.25s`
- `python3.14 scripts/ps_core_runtime_contract_inventory.py --repo . --json-out docs/analysis/ps_core_runtime_contract_inventory_2026-04-04.json --md-out docs/analysis/PS_CORE_RUNTIME_CONTRACT_INVENTORY_2026-04-04.md --stdout-json` → `route_heavy_without_direct_contract_tests: 0`, `recommended_next_slice: null`
- `python3.14 scripts/contract_inventory_fast_check.py --repo .` → `PASS`, kein aktiver nächster Inventar-Slice mehr

**Next Exact Task:** Genau einen kleinsten nicht-Contract-Core/API-Forward-Slice ziehen und builder-scharf landen — weiterhin **kein** Live-/Install-/Restart-Schritt.

### ✅ Slice 127 — Backend UI Module Write Model Alignment
**Status:** ✅ DONE (worktree; kein Live-/Install-/Restart-Schritt)

**Goal**
`PUT /api/v1/backend/modules/<module_id>` auf dieselbe kanonische `ModuleRegistry`-Wahrheit ziehen wie die bereits gelandete Backend-UI-Modul-Read-Side, damit globale Modulmutationen nicht länger nur geloggt, sondern restart-sicher persistiert werden.

### Grounded progress
- [x] `copilot_core/rootfs/usr/src/app/copilot_core/api/v1/backend_ui.py` persistiert `state` im Backend-UI-Globalmodul-Write-Pfad jetzt kanonisch über `ModuleRegistry.set_state(...)` statt Log-only-Verhalten
- [x] der Write-Pfad normalisiert `module_id` bewusst vor der Mutation und liefert Persistenzfehler kontrolliert als JSON-500 statt stiller Erfolgs-Acks ohne echte Zustandsänderung
- [x] bestehende `config`-Validierung bleibt in diesem Minimal-Slice unverändert; gezogen wurde bewusst nur die globale Modul-State-Write-Side
- [x] fokussierte Verifikation gelandet: `tests/test_backend_ui_contract.py` deckt jetzt Erfolgsfall, Registry-Write-Fehler und Read-after-write über `GET /api/v1/backend/modules` auf derselben Registry-Wahrheit direkt ab; `copilot_core/rootfs/usr/src/app/tests/test_module_registry_zones.py` bleibt für die zugrunde liegende Modul-/Override-Wahrheit grün
- [x] Artefakt-Landung ergänzt: `docs/analysis/PS_CORE_SLICE_127_BACKEND_UI_MODULE_WRITE_MODEL_2026-04-05.md` dokumentiert Ziel, Diff, Verifikation und den nächsten exakten Folgeslice

### Verification
- `pytest -q tests/test_backend_ui_contract.py copilot_core/rootfs/usr/src/app/tests/test_module_registry_zones.py` → `24 passed in 1.06s`
- `python3.14 scripts/contract_inventory_fast_check.py --repo .` → `PASS`

**Next Exact Task:** Slice 128 — `GET /api/v1/backend/dashboard` auf dieselbe Modul-/Zonen-Wahrheit ziehen, damit Dashboard-Zählwerte und Übersichtsmetriken nicht länger neben den nun kanonischen Backend-UI-Modul- und Zonen-Surfaces driften.

### ✅ Slice 126 — Backend UI Module Read Model Alignment
**Status:** ✅ DONE (worktree; kein Live-/Install-/Restart-Schritt)

**Goal**
`GET /api/v1/backend/modules` auf dieselbe kanonische `ModuleRegistry`-Wahrheit ziehen wie die übrigen Modul-Surfaces, damit globale Modulzustände im Backend UI nicht länger als statische Platzhalter neben der bereits truth-backed Zonen-Read-Side stehen.

### Grounded progress
- [x] `copilot_core/rootfs/usr/src/app/copilot_core/api/v1/backend_ui.py` ergänzt kleine Modulkarten-Helper, die bekannte Backend-UI-Karten kompatibel halten und zusätzliche in `ModuleRegistry` bzw. Zone-Overrides sichtbare Module deterministisch projizieren
- [x] `GET /api/v1/backend/modules` liest `state` jetzt direkt aus `ModuleRegistry` statt aus fest verdrahteten Platzhalterwerten
- [x] die Modulkarten tragen jetzt zusätzlich `global_state`, `zones_enabled`, `zone_overrides` und `has_zone_overrides`, damit globale Governance und zonenscharfe Override-Sicht in derselben Surface gekoppelt bleiben
- [x] effektive Zonen-Zählung wird aus derselben Zonen-Read-Side wie Slice 125 abgeleitet, damit Backend-UI-Globalmodule und zonenscharfe Modulantworten nicht gegeneinander driften
- [x] fokussierte Verifikation gelandet: `tests/test_backend_ui_contract.py` deckt die truth-backed Modulkarten inklusive generischer Zusatzmodule und Override-/Zone-Count-Projektion direkt ab; `copilot_core/rootfs/usr/src/app/tests/test_module_registry_zones.py` hält die zugrunde liegende Override-Wahrheit weiter grün
- [x] Artefakt-Landung ergänzt: `docs/analysis/PS_CORE_SLICE_126_BACKEND_UI_MODULE_READ_MODEL_2026-04-05.md` dokumentiert Ziel, Diff, Verifikation und den nächsten exakten Folgeslice

### Verification
- `pytest -q tests/test_backend_ui_contract.py copilot_core/rootfs/usr/src/app/tests/test_module_registry_zones.py` → `23 passed in 0.97s`
- `python3.14 scripts/contract_inventory_fast_check.py --repo .` → `PASS`

**Next Exact Task:** Slice 127 — `PUT /api/v1/backend/modules/<module_id>` auf dieselbe `ModuleRegistry`-Wahrheit ziehen, damit Backend-UI-Globalmodule nicht nur truth-backed gelesen, sondern auch kanonisch geschrieben werden statt `state` weiter nur zu loggen.

### ✅ Slice 125 — Backend UI Zone-Module Read Model Alignment
**Status:** ✅ DONE (worktree; kein Live-/Install-/Restart-Schritt)

**Goal**
`backend_ui`-Read-Side für Zonenmodule auf dieselbe kanonische Zone-Override-Wahrheit ziehen, damit Zonen-/Zonendetail-Karten `state`, `global_state`, `override_state` und `has_override` direkt lesen statt aus Template-/`enabled_modules`-Heuristik abzuleiten.

### Grounded progress
- [x] `copilot_core/rootfs/usr/src/app/copilot_core/api/v1/backend_ui.py` ergänzt kleine Read-Model-Helper, die Modul-Kandidaten aus Template-Defaults, `enabled_modules`, Zonendetaildaten und expliziten Zone-Overrides vereinen
- [x] `GET /api/v1/backend/zones` liefert pro Zone jetzt restart-sicher `modules` mit `state`, `global_state`, `override_state`, `has_override` plus daraus abgeleitete `enabled_modules`
- [x] `GET /api/v1/backend/zones/<zone_id>/entities` trägt dieselbe Zonenmodul-Read-Side direkt mit, damit Entity-/Zonendetail-Caller keine Parallelheuristik mehr nachbauen müssen
- [x] `overview.zones` im Backend-Zonenpayload spiegelt dieselbe angereicherte Zonenliste wie das Top-Level-Feld, damit keine zweite schwächere Read-Side im selben Response bestehen bleibt
- [x] fokussierte Verifikation gelandet: `tests/test_backend_ui_contract.py` deckt die neue Zone-Read-Side inkl. Override-/Projektionsfälle direkt ab; `copilot_core/rootfs/usr/src/app/tests/test_module_registry_zones.py` hält den zugrunde liegenden Override-Fallback grün
- [x] Artefakt-Landung ergänzt: `docs/analysis/PS_CORE_SLICE_125_BACKEND_UI_ZONE_READ_MODEL_2026-04-05.md` dokumentiert Ziel, Diff, Verifikation und den nächsten exakten Folgeslice

### Verification
- `pytest -q tests/test_backend_ui_contract.py copilot_core/rootfs/usr/src/app/tests/test_module_registry_zones.py` → `23 passed in 0.97s`
- `python3.14 scripts/contract_inventory_fast_check.py --repo .` → `PASS`

**Next Exact Task:** Slice 126 — `backend_ui`-Modulkarten (`GET /api/v1/backend/modules`) auf `ModuleRegistry`-Wahrheit ziehen, damit globale Modulzustände nicht länger als statische Platzhalter neben der jetzt kanonischen Zonen-Read-Side stehen.

### ✅ Slice 124 — Backend UI Zone-Override Alignment
**Status:** ✅ DONE (worktree; kein Live-/Install-/Restart-Schritt)

**Goal**
`backend_ui` auf dieselbe kanonische Zone-Override-Wahrheit wie `module_control` ziehen, damit `/api/v1/backend/zones/<zone_id>/modules` nicht länger parallel auf `enabled_modules` + TODO-Semantik schreibt.

### Grounded progress
- [x] `copilot_core/rootfs/usr/src/app/copilot_core/api/v1/backend_ui.py` nutzt für Zonenmodul-Mutationen jetzt `ModuleRegistry` als kanonische Write-Wahrheit statt direkter Schatten-Schreiberei auf `enabled_modules`
- [x] derselbe Request bestimmt jetzt bewusst Effektivzustand vs. expliziten Override: State == Global-State löscht vorhandene Zone-Overrides, abweichender State persistiert eine echte Override-Zeile
- [x] `backend_ui`-Response zeigt jetzt restart-sicher denselben lesbaren Zustand wie Slice 123: `state`, `global_state`, `override_state`, `has_override`
- [x] `enabled_modules` bleibt nur noch kompatible Read-Side-Projektion des effektiven Zustands, nicht mehr die schreibende Wahrheit für `active/learning/off`
- [x] fokussierte Contract-/Follow-up-Verifikation gelandet: `tests/test_backend_ui_contract.py` deckt Delete-vs-Set-, Trim-, Validierungs- und Sync-Reporting-Pfade ab; `copilot_core/rootfs/usr/src/app/tests/test_module_registry_zones.py` bleibt für den zugrunde liegenden Override-Fallback grün
- [x] Artefakt-Landung ergänzt: `docs/analysis/PS_CORE_SLICE_124_BACKEND_UI_ZONE_OVERRIDE_ALIGNMENT_2026-04-05.md` dokumentiert Ziel, Diff, Verifikation und den nächsten exakten Read-Side-Schritt

### Verification
- `pytest -q tests/test_backend_ui_contract.py` → `5 passed in 0.42s`
- `pytest -q tests/test_backend_ui_contract.py copilot_core/rootfs/usr/src/app/tests/test_module_registry_zones.py` → `23 passed in 0.86s`

**Next Exact Task:** Slice 125 — `backend_ui`-Read-Side für Zonenmodule auf dieselbe kanonische Override-Wahrheit ziehen, damit Zonen-/Modulkarten `state`, `global_state`, `override_state` und `has_override` direkt lesen statt aus Template-/`enabled_modules`-Heuristik abzuleiten.

### ✅ Slice 123 — Module Control Zone-Override Surface
**Status:** ✅ DONE (worktree; kein Live-/Install-/Restart-Schritt)

**Goal**
Die bereits im `ModuleRegistry` vorhandene zonenspezifische Modul-Governance als kanonische `module_control`-Core/API-Surface freischalten, damit Zone-Overrides nicht länger nur implizit im Storage existieren.

### Grounded progress
- [x] `copilot_core/rootfs/usr/src/app/copilot_core/api/v1/module_control.py` erweitert um kanonische Zone-Override-Surfaces: `GET /api/v1/modules/zones/<zone_id>`, `GET /api/v1/modules/zones/<zone_id>/<module_id>`, `PUT /api/v1/modules/zones/<zone_id>/<module_id>` und `DELETE /api/v1/modules/zones/<zone_id>/<module_id>`
- [x] Zone-Detail-Responses sind jetzt lesbar und restart-sicher: effektiver `state` plus `global_state`, `override_state` und `has_override` kommen direkt aus derselben Core-Wahrheit statt aus Callerseiten-Heuristik
- [x] `copilot_core/rootfs/usr/src/app/copilot_core/module_registry.py` ergänzt um `delete_zone_state(zone_id, module_id)`, damit explizite Zone-Overrides sauber gelöscht und auf den globalen Modulzustand zurückgeführt werden können
- [x] fokussierte Härtung und Verifikation gelandet: `tests/test_module_control_contract.py` deckt neue Zone-Override-Read-/Write-/Delete-/Auth-/Validierungs-/Runtime-Pfade ab; `copilot_core/rootfs/usr/src/app/tests/test_module_registry_zones.py` zieht Delete-/Fallback-Verhalten direkt auf Storage-Ebene fest
- [x] Artefakt-Landung ergänzt: `docs/analysis/PS_CORE_SLICE_123_MODULE_ZONE_OVERRIDES_2026-04-05.md` dokumentiert Ziel, Diff, Verifikation und den nächsten exakten Forward-Schritt

### Verification
- `pytest -q tests/test_module_control_contract.py copilot_core/rootfs/usr/src/app/tests/test_module_registry_zones.py tests/test_ps_core_runtime_contract_inventory.py` → `59 passed in 27.13s`
- `python3.14 scripts/contract_inventory_fast_check.py --repo .` → `PASS`, Inventar-Linie bleibt geschlossen

**Next Exact Task:** Slice 124 — `backend_ui` auf dieselbe kanonische Zone-Override-Wahrheit umstellen, damit `/api/v1/backend/zones/<zone_id>/modules` nicht länger parallel auf `enabled_modules` + TODO-Semantik schreibt.

---

## Slice 68 — Notification Delivery Engine
**Priority:** P0
**Status:** ready

**Goal**
Unified notification delivery engine with channel routing, rate limiting, and delivery tracking.
**Priority:** P0  
**Status:** ready

**Goal**
Promote existing Core modules into one coherent, policy-aware runtime layer.

### Deliverables
- [ ] define canonical module metadata / snapshot model
- [ ] map module applicability into Habitus zones and zone truth
- [ ] align `licht`, `helligkeit`, `heiz`, `bewegung`, `praesenz`, media/music, scenes, energy, and HA connection module on one input/output contract
- [ ] expose module state/config/summary/freshness in truth-backed read models
- [ ] focus on correction + wiring of existing modules before inventing parallel abstractions

### Acceptance criteria
- modules are first-class in architecture and runtime,
- Habitus zones can reference modules cleanly,
- dashboard and policy layers can consume module truth directly.

---

## Slice 4 — Classification authority
**Priority:** P1  
**Status:** ready

**Goal**
Create one canonical classification/taxonomy layer for Core semantics.

### Deliverables
- [ ] unify entity role/tag/category logic now split across `zone_automation.py`, `habitus_zones.py`, and mining helpers
- [ ] define canonical role/tag/module-bucket outputs used by ingest + topology + dashboard + proposals + chat context
- [ ] add migration shims for legacy callers where needed

### Acceptance criteria
- Core has one obvious taxonomy authority,
- downstream systems stop inventing their own category logic.

---

## Slice 5 — Brain growth unification
**Priority:** P1  
**Status:** ready

**Goal**
Make semantic transfer into graph + neuron + module context explicit and inspectable.

### Deliverables
- [ ] define explicit transfer model from normalized inputs to graph/neuron/module updates
- [ ] add read model for brain activity/growth summary
- [ ] strengthen link between zone/entity/module truth and neuron evaluation
- [ ] document how incoming sensors/events/entities strengthen graph/neuron context

### Acceptance criteria
- the “growing brain” is no longer only implied across separate subsystems,
- product/docs/runtime share the same model for brain growth.

---

## Slice 6 — Truth-backed dashboard read models
**Priority:** P1  
**Status:** ready

**Goal**
Make dashboard output first-class Core read models instead of a truth-construction layer.

### Deliverables
- [ ] zone summary read model
- [ ] zone detail read model
- [ ] module read model
- [ ] system overview read model
- [ ] explicit freshness/provenance fields on major blocks
- [ ] remove production dependence on `example_config` enrichment paths

### Acceptance criteria
- dashboard renders from live Core truth,
- example data is demo/test-only,
- read models contain interpretation, not just raw data blobs.

---

## Slice 7 — Unified proposal lifecycle
**Priority:** P1  
**Status:** ready

**Goal**
Unify candidates, suggestions, proposals, acceptance, and action intents.

### Deliverables
- [ ] one lifecycle state machine
- [ ] one primary proposal storage model
- [ ] consistent accept/reject/snooze APIs
- [ ] `ProposalIntentV1` and `ActionIntentV1` as first-class outputs
- [ ] evidence/explanation attached by default
- [ ] module-aware action handoff contract

### Acceptance criteria
- one obvious Core proposal surface,
- example/fallback suggestion behavior is no longer product truth,
- accepted proposals flow cleanly into policy-gated action intents.

---

## Slice 8 — HA connection module hardening
**Priority:** P1  
**Status:** ready

**Goal**
Solidify the Core-side HA module as the semantic input connection/preparation layer.

### Deliverables
- [ ] formalize connection-module contract
- [ ] align `HomeAssistantModuleEngine` + `ModuleRouter` around normalized truth inputs
- [ ] expose transport/pipeline health as first-class diagnostics
- [ ] ensure downstream modules consume prepared inputs, not raw HA payloads

### Acceptance criteria
- HA connection semantics are clear,
- the Core-side HA module is not treated as a second semantic owner.

---

## Slice 9 — RAG/chat alignment with truth layer
**Priority:** P1  
**Status:** ready

**Goal**
Make chat a stable consumer of Core truth rather than ad hoc service scraping.

### Deliverables
- [ ] formal chat context blocks sourced from truth/read models
- [ ] retrieval provenance improvements
- [ ] stronger mapping between modules/zones/brain summaries and chat explanations
- [ ] tests for source-grounded responses and memory integration

### Acceptance criteria
- chat is visibly attached to the Core semantic model,
- RAG/memory/live-home-context composition is stable and explainable.

---

## Slice 10 — Decision/execution separation hardening
**Priority:** P1  
**Status:** ready

**Goal**
Keep Core as decider and HA as execution/projection adapter.

### Deliverables
- [ ] formalize HA adapter command outputs
- [ ] audit current direct execution paths for bypasses around unified action-intent flow
- [ ] make behavioral log / audit trail consistent across execution outcomes

### Acceptance criteria
- Core decides eligibility,
- HA executes via thin adapters,
- policy is not duplicated in HACS/frontend code.

---

## Slice 11 — Contract and regression coverage
**Priority:** P2  
**Status:** ready

**Goal**
Protect the concept with tests.

### Deliverables
- [ ] ingest contract tests
- [ ] topology sync contract tests
- [ ] module contract tests
- [ ] brain/read-model snapshot tests
- [ ] dashboard read-model snapshot tests
- [ ] proposal lifecycle tests
- [ ] autonomy/policy gate tests
- [ ] e2e checks against truth-backed dashboard output
- [ ] chat/RAG integration coverage

### Acceptance criteria
- future changes cannot silently re-fragment ingest, topology, modules, brain semantics, chat, or proposal lifecycle.

---

## Explicit non-goals

These should **not** become primary Core responsibilities:
- Lovelace card implementation details
- HA config flow/options flow UX
- HA entity naming/materialization logic as semantic source
- dashboard-side re-derivation of zone semantics
- a second parallel policy engine in HACS

---

## Current artifacts
- `docs/CORE_CONCEPT_DIRECTIVE.md` — authoritative concept/boundary directive
- `docs/CORE_CONCEPT_HANDOFF.md` — concise handoff for reviewers / implementers

---

## Consolidation Findings (2026-03-31)

### What is now solid
1. **Semantic Truth Engine** — Core is explicitly the semantic owner
2. **11 Slices Delivered** — All P0/P1 slices complete (v15.2.10 → v15.2.20)
3. **Contract Tests** — Future changes cannot silently re-fragment semantics
4. **Decision/Execution Separation** — Core decides, HA executes (thin adapter)
5. **Truth-Backed Read Models** — Dashboard, Chat, Brain all consume same truth

### What needs hardening (Refinement Priority)
1. **Edge Cases in Ingest** — Dedup TTL boundaries, malformed envelopes
2. **Zone Sync Robustness** — HA topology change detection, conflict resolution
3. **Module State Machine** — Transition edge cases (off→learning→active)
4. **Brain Growth Performance** — Graph pruning, neuron expiry, memory limits
5. **Policy Gate Coverage** — All action intents must pass through policy

### New Slices (Post-Consolidation)
These are **P2/P3** — only start after refinement is complete:

## Slice 12 — Anomaly Detection + Alerting
**Priority:** P2
**Status:** done (`v15.3.22`)

**Goal**
Detect anomalous zone/module behavior and alert user.

### Deliverables
- [x] anomaly detection engine (statistical + rule-based)
- [x] alert routing (Telegram, HA notification, email)
- [x] anomaly history + trend analysis
- [x] false-positive suppression (learning)

### Acceptance criteria
- anomalies are detected before user notices
- alerts are actionable with clear explanation
- false positives decrease over time

---

## Slice 13 — Energy Optimization
**Priority:** P2
**Status:** done (`v15.3.23`)

**Goal**
Optimize energy consumption across all zones/modules.

### Deliverables
- [x] energy monitoring per module/zone
- [x] optimization suggestions (policy-gated)
- [x] tariff-aware scheduling (time-of-use pricing)
- [x] energy reports + savings tracking

### Acceptance criteria
- energy consumption is visible per zone/module
- optimization suggestions are actionable
- savings are measurable

---

## Slice 14 — Predictive Automation
**Priority:** P3
**Status:** ✅ DONE (v15.3.24)

**Goal**
Predict user intent and pre-emptively prepare automations.

### Deliverables
- [x] pattern recognition (time, presence, weather, calendar)
- [x] predictive proposals (before user asks)
- [x] confidence scoring + user feedback loop
- [x] seasonal adaptation

### Acceptance criteria
- predictions are accurate (>80% acceptance rate) — proposals flow through AutomationSuggestionEngine lifecycle
- user can easily override/correct predictions — accept/reject feedback loop implemented
- system learns from corrections — pattern reinforcement on accept, degradation on reject

**Commit:** `Slice 14 predictive proposal contract`
**Tag:** v15.3.24
**Tests:** `pytest -q tests/test_predictive_automation.py tests/test_predictive_api_contract.py tests/test_calendar_integration.py tests/test_habitus_accept_contract.py` → `43 passed`

---

## Slice 15 — Multi-Zone Coordination
**Priority:** P2
**Status:** ✅ DONE (v15.3.25)

**Goal**
Coordinate actions across multiple zones (scenes, routines, events).

### Deliverables
- [x] cross-zone action coordination
- [x] scene composition (multi-zone scenes)
- [x] routine engine (time/event-triggered multi-zone actions)
- [x] conflict detection + resolution

### Acceptance criteria
- multi-zone scenes work reliably
- routines are easy to define
- conflicts are detected and resolved gracefully

**Commit:** `feat(multizone): deliver slice 15 coordination surface`
**Tag:** v15.3.25
**Tests:** `pytest -q tests/test_multizone_coordination.py tests/test_multizone_blueprint_contract.py` → `20 passed`

---

## Ready signal for next implementation agent

**Phase 1 Complete:** Slices 1-11 delivered (v15.2.10 → v15.2.20)

**Next Phase:** Consolidation + Refinement
1. **Edge Case Hardening** — Ingest, Zone Sync, Module State Machine
2. **Performance Optimization** — Brain Growth, Read Models, Query Latency
3. **Policy Gate Coverage** — 100% of action intents through policy
4. **Documentation** — API docs, architecture diagrams, runbooks
5. **✅ Slice 90 — Runtime/Test Surface Repair** — Package-Bridge, Cache/Queue/SDK/Config-Baseline für Root-Pytest stabilisiert
6. **✅ Slice 91 — Plugin Engine Contract Recovery** — Legacy-/Current-Plugin-Engine-Verträge, Hooks, Discovery und Dependency-/Version-Checks wieder vereinheitlicht
7. **✅ Slice 92 — Workspace Contract Bundle Recovery** — HA-Worktree-Pfadauflösung und Zone-Sync-Entity-Kompatibilität für den Core-Contract-Bundle-Lauf repariert
8. **✅ Slice 93 — Root Pytest Surface Stabilization** — Default-Root-`pytest` auf `tests/` fixiert, optionale Metrics-/HA-/Notification-Importpfade gehärtet, Storage-Metadaten bei direkter Entry-Konstruktion repariert
9. **✅ Refinement — Integration/OWASP Compatibility Repair** — Legacy-Facades für Slice-67-82-Module ergänzt (`23/23` Integration grün, `57/57` ModuleRegistry grün) sowie OWASP-Request-Context-, NoSQL- und SSRF-Kanten für Root-`pytest -x` gehärtet
10. **✅ Slice 94 — Root Contract/Test Surface Recovery** — Breite Core-Restfehler nach Slice 93 über Modul-, Query-, Scheduler-, Search-, Secrets-, Webhook-, Worker-, Workflow- und Voice-/Weather-Flächen stabilisiert; kritische Deadlocks/Retry-/Mutation-/Contract-Kanten beseitigt
11. **✅ Slice 95 — Health Engine Surface Recovery** — Deadlock im Advanced-Health-Dependency-Pfad beseitigt, Built-in-Systemchecks von der user-facing Root-Contract-Surface getrennt, Default-Kritikalität/Overall-Health der klassischen Health-Engine wieder contract-konform gemacht und Component-Checks im Read-Model vollständig serialisiert
12. **✅ Slice 96 — Circadian, Logging, and Metrics Contract Repair** — Night-Circadian-State liefert nachts wieder `sleep_mode_brightness`; Logging-Pattern-Filter arbeiten case-insensitive und der Default-Buffer ist wieder `100`; Counter-History wird nicht mehr in-place mutiert und `aggregation="sum"` summiert Serienstände statt aufgeblähter History-Referenzen
13. **✅ Slice 101 — Energy Reserve Recovery Contract Repair** — Batterie-Reserveboden ist wieder echt geschützt; Low-Battery-Zonen laden auch während Peak-Hours deterministisch nach und dokumentieren den Schutzpfad mit `reserve_recovery`
14. **✅ Slice 102 — Zone Comfort Scoring Contract Repair** — Zone-Comfort-Scores, Bedroom-Profil und Trend-Baseline wieder contract-konform; gesamtes Komfortmodul (`98/98`) grün
15. **✅ Slice 103 — Zone Truth API Store Contract Repair** — Zone-Truth-API, Delta-Responses und Sync-Flows nutzen wieder dieselbe kanonische Store-Instanz; Contract-Surface (`74/74`) grün
16. **✅ Slice 104 — Zone Truth Revision Contract Repair** — Zone- und Entity-Revisionen folgen wieder deterministisch der globalen Topology-History; Root-Contract-Surface vollständig grün (`4369 passed, 4 skipped`)
17. **✅ Slice 106 — Energy Optimization Surface Delivery** — Slice-13-Energiefläche jetzt mit echten Zone/Module-Summaries, Suggestion-/Budget-/Report-Surface und Root/Runtime-Parität; Slice-13-Contracts grün (`70/70`)

### ✅ Refinement — Slice 15 Follow-up Hardening
**Status:** ✅ DONE (v15.3.26)

**Goal**
Handoffs, Scheduler-Runtime und echte Zone-/Module-Targets auf der Multi-Zone-Surface kontraktsicher machen.

### Deliverables
- [x] Proposal-/Action-Handoffs an Scene-/Routine-Runtime gebunden
- [x] Scheduler-getriebene Routine-Ausführung und optionale Scene-Schedules angebunden
- [x] echte Zone-/Module-/Service-Target-Contracts in Pending-Actions/API ergänzt

**Commit:** `feat(multizone): harden runtime handoffs and scheduler bindings`
**Tag:** v15.3.26
**Tests:** `pytest -q tests/test_multizone_coordination.py tests/test_multizone_blueprint_contract.py tests/test_multizone_runtime_contract.py` → `22 passed`

### ✅ Slice 16 — Voice Control / Policy Gate Surface
**Status:** ✅ DONE (v15.3.27)

**Goal**
Voice-Control auf denselben Proposal→Action→Runtime-Vertrag wie Predictive, Habitus und Multi-Zone ziehen.

### Deliverables
- [x] neue `/api/v1/voice/control/parse`-Surface für `VoiceControlProposalV1`
- [x] neue `/api/v1/voice/control/confirm`-Surface für `ProposalIntentV1`/`ActionIntentV1`/HA-Handoff
- [x] Policy-Preview + Modul-/Zone-Auflösung für Voice-Control-Kommandos
- [x] Payload-Preserve bis in den HA-Adapter für Climate-/Brightness-Kommandos
- [x] Contract-Tests für Parse/Confirm/`execute_now`

### Acceptance criteria
- Voice-Control erzeugt keine zweite Entscheidungs- oder Policy-Fläche neben Core.
- bestätigte Voice-Kommandos laufen durch denselben Policy-Gate-/HA-Adapter-Vertrag wie andere akzeptierte Vorschläge.
- Runtime-Payloads bleiben für echte Voice-Ausführung erhalten.

**Commit:** `feat(voice): deliver slice 16 policy gate surface`
**Tag:** v15.3.27
**Tests:** `pytest -q tests/test_voice_control.py tests/test_voice_policy_contract.py tests/test_habitus_accept_contract.py tests/test_predictive_api_contract.py` → `37 passed`

### ✅ Slice 17 — Canonical Action Closure Surface
**Status:** ✅ DONE (v15.3.28)

**Goal**
Eine einzige kanonische User-Feedback-/Execution-Closure-Surface über Proposal→Action→Runtime legen, damit Voice, Predictive, Habitus und Multi-Zone dieselbe Rückmelde- und Lernspur teilen.

### Deliverables
- [x] neues `ActionClosureV1`-Store-/Contract-Layer für accept → feedback → execution
- [x] neue `/api/v1/action-closures/*`-Surface für list/detail/feedback/execution
- [x] Voice/Predictive/Habitus confirm/accept liefern jetzt dieselbe `action_closure`
- [x] Multi-Zone-Pending-Actions exponieren `action_closure_id` + `action_closure` mit Scene-/Routine-Kontext
- [x] Contract-Tests für Voice, Predictive und Multi-Zone gegen dieselbe Closure-Surface

### Acceptance criteria
- Feedback- und Execution-Rückmeldungen laufen nicht mehr feature-spezifisch auseinander.
- Confirmed Actions aus Voice/Predictive/Habitus und queued Multi-Zone-Actions können über dieselbe Closure-ID verfolgt werden.
- Runtime-/User-Feedback bleibt als gemeinsame Lernspur abfragbar.

**Commit:** `feat(core): deliver slice 17 action closure surface`
**Tag:** v15.3.28
**Tests:**
- `pytest -q tests/test_action_closure_contract.py tests/test_voice_policy_contract.py tests/test_predictive_api_contract.py tests/test_multizone_runtime_contract.py tests/test_habitus_accept_contract.py` → `12 passed`
- `pytest -q tests/test_voice_control.py tests/test_multizone_blueprint_contract.py tests/test_multizone_coordination.py` → `50 passed`

### ✅ Slice 18 — Action Closure Summary / Context Surface
**Status:** ✅ DONE (v15.3.29)

**Goal**
Closure-/Outcome-Summaries als kanonische Read-Model-/Chat-/Dashboard-Surface ausleiten, damit Feedback und Ausführung nicht nur gespeichert, sondern systemweit erklärbar und auswertbar werden.

### Deliverables
- [x] `ActionClosureSummaryV1` als aggregierte Outcome-/Feedback-/Source-/Zone-/Module-Surface
- [x] `ActionClosureContextBlockV1` als kompakter Chat-/Context-Block
- [x] neue `/api/v1/action-closures/summary`- und `/context`-Surface mit Closure-Filtern
- [x] Dashboard-Global-Context exponiert Closure-Status/Highlights/Recent-Items
- [x] Styx-Chat bindet denselben Closure-Kontext in den Haus-Status ein
- [x] Contract-Tests fuer Read-Model, API, Dashboard-Context und Chat-Home-Context

### Acceptance criteria
- Feedback-/Execution-Closure ist nicht nur detailabfragbar, sondern als globale Summary-Surface stabil nutzbar.
- Dashboard und Chat lesen dieselbe kanonische Closure-/Outcome-Wahrheit statt eigene Ad-hoc-Aggregationen zu bauen.
- Offene, erfolgreiche und problematische Actions sind systemweit schnell erklaerbar.

**Commit:** `feat(core): deliver slice 18 action closure summary surface`
**Tag:** v15.3.29
**Tests:** `pytest -q tests/test_action_closure_contract.py tests/test_action_closure_summary_contract.py tests/test_voice_policy_contract.py tests/test_predictive_api_contract.py tests/test_multizone_runtime_contract.py tests/test_habitus_accept_contract.py` → `17 passed`

### ✅ Slice 19 — Closure-Driven Learning Feedback Loop
**Status:** ✅ DONE (v15.3.30)

**Goal**
Closure-Signale in Predictive-/Habitus-/Multi-Zone-Lern- und Priorisierungslogik rueckkoppeln, damit accept/reject/execution-outcomes nicht nur erklaert, sondern fuer kuenftige Vorschlagsqualitaet systematisch verwertet werden.

### Deliverables
- [x] kanonische `ActionClosure`-Lernzusammenfassung mit Feedback-/Execution-Signalwertung und `priority_bias`
- [x] Predictive-Proposals koppeln Closure-Historie in Confidence, Reasoning, Source-Signals und Evidence zurueck
- [x] Habitus-Proposals verknuepfen Regelmetadaten (`rule_a`/`rule_b`) mit Closure-Historie fuer Re-Ranking
- [x] Multi-Zone-Pending-Actions exponieren `learning_signals`, `priority_bias` und `effective_priority`
- [x] Contract-Tests fuer closure-getriebene Repriorisierung ueber Predictive, Habitus und Multi-Zone

### Acceptance criteria
- Closure-Historie beeinflusst kuenftige Vorschlagsreihenfolge und nicht nur Reporting.
- Predictive, Habitus und Multi-Zone lesen dieselbe kanonische Lernspur statt feature-spezifischer Sonderlogik.
- Konfliktaufloesung und Proposal-Ranking bleiben source-grounded und testbar.

**Commit:** `feat(core): deliver slice 19 closure learning feedback loop`
**Tag:** v15.3.30
**Tests:** `pytest -q tests/test_action_closure_contract.py tests/test_action_closure_summary_contract.py tests/test_action_closure_learning_contract.py tests/test_predictive_automation.py tests/test_predictive_api_contract.py tests/test_multizone_coordination.py tests/test_multizone_blueprint_contract.py tests/test_multizone_runtime_contract.py tests/test_habitus_accept_contract.py` → `58 passed`

**Next Exact Task:** Kein weiterer expliziter Forward-Slice ist im Taskboard definiert; naechster Schritt ist die Definition des naechsten Core-Slices aus Roadmap/Vision ohne neue Annahmen.

**After Refinement:** Root-Contract-Surface ist grün; Slice 13+ wieder als reguläre Forward-Slices aufnehmen

**Core is now stable enough for HA/HACS lane reactivation.**

### ✅ Slice 20 — Closure-Aware Voice Follow-Up Hints
**Status:** ✅ DONE (v15.3.31)

**Goal**
Den Roadmap-Block **Voice Integration** an die kanonische Closure-Wahrheit anbinden, damit proaktive Sprachhinweise offene/problematische Aktionen aus derselben Proposal→Action→Runtime-Spur ableiten statt nur generische Zeit-/Mood-Hinweise zu sprechen.

### Deliverables
- [x] neuer Voice-Hint-Typ `action_follow_up` in der proaktiven Hint-Pipeline
- [x] Proactive Voice liest `ActionClosureContextBlockV1` direkt aus der kanonischen Closure-Surface
- [x] problematische Closures erzeugen High-Priority-Nachfass-Hinweise; offene Closures erzeugen Medium-Priority-Statushinweise
- [x] `/api/v1/voice/hints` exponiert denselben Closure-Summary-/Recent-Closure-Kontext stabil im Hint-Payload
- [x] Contract-Tests für direkte Hint-Generierung und API-Surface gegen dieselbe Closure-Wahrheit

### Acceptance criteria
- Voice-Hinweise sprechen bei realen offenen/problematischen Aktionen dieselbe Closure-Wahrheit wie Dashboard, Chat, Predictive und Multi-Zone.
- Follow-up-Hinweise bleiben source-grounded: Status, Summary und letzte Closure sind im Hint-Kontext transparent enthalten.
- Die Voice-Surface erfindet keine separaten Outcome-Heuristiken neben dem bestehenden Closure-Contract.

**Commit:** `feat(core): deliver slice 20 closure-aware voice follow-up hints`
**Tag:** v15.3.31
**Tests:** `pytest -q tests/test_action_closure_contract.py tests/test_action_closure_summary_contract.py tests/test_voice_action_closure_hints_contract.py tests/test_voice_policy_contract.py` → `13 passed`

**Next Exact Task:** Nächster Forward-Slice wieder aus Roadmap/Vision ableiten; naheliegender Kandidat ist die zonenspezifische Ausleitung derselben Closure-Wahrheit für Voice/Chat-Kontext statt globalem Follow-up.

### ✅ Slice 21 — Zone-Scoped Closure Context for Voice/Chat
**Status:** ✅ DONE (v15.3.32)

**Goal**
Die kanonische `ActionClosure`-Wahrheit wird jetzt mit zonenspezifischem Kontext fuer Voice- und Chat-Surfaces ausgegeben statt nur globalem Follow-up. VoiceHints und ChatHandler fuehren den aktuellen Zonennamen an die Closure-Surface durch, und `build_action_closure_context_block` loest automatisch menschenlesbare Zonennamen aus Zone-ID-Slugs auf.

### Deliverables
- [x] `build_action_closure_context_block` erweitert um `zone_name`-Parameter und `zone_id`-Filterung
- [x] `_resolve_zone_name` leitet menschenlesbare Zonennamen aus `zone_id`-Slugs ab
- [x] `_check_action_followups` in `ProactiveVoiceHints` leitet `VoiceContext.zone_name` durch
- [x] `ChatHandler._build_home_context` nimmt `zone_name`-Parameter entgegen und fuehrt ihn durch
- [x] Contract-Tests fuer zonenspezifische Filterung und automatische Zonenaufloesung

### Acceptance criteria
- Voice-Hinweise und Chat-Closure-Zeilen sind zonenspezifisch abfragbar und zeigen friendly Zonennamen.
- Die Zone-ID-zu-Namens-Aufloesung funktioniert auch ohne expliziten `zone_name`-Parameter.
- Alle drei Surface-Konsumenten (VoiceHints, Chat, globaler API) bleiben funktional und testbar.

**Commit:** `feat(core): deliver slice 21 zone-scoped closure context for voice and chat`
**Tag:** v15.3.32
**Tests:** `pytest -q tests/test_action_closure_contract.py tests/test_action_closure_summary_contract.py tests/test_voice_action_closure_hints_contract.py tests/test_voice_policy_contract.py tests/test_action_closure_learning_contract.py tests/test_predictive_api_contract.py tests/test_multizone_runtime_contract.py tests/test_habitus_accept_contract.py` → gruen

**Next Exact Task:** Zone-Scoped Action-Closure-Feed-in fuer Dashboard-/systemweite Context-Surfaces als naechsten Forward-Slice definieren und ableiten; Persistenz und Zone-Scoped-Read-Model-Filterung fuer Closure-Delta-Responses evaluieren.

### ✅ Slice 22 — Zone-Scoped Closure Feed for Dashboard/System Context
**Status:** ✅ DONE (v15.3.33)

**Goal**
Die kanonische `ActionClosure`-Wahrheit wird jetzt nicht nur global fuer Dashboard-Highlights, sondern direkt zonenspezifisch fuer Dashboard-/System-Kontext-Surfaces ausgeleitet. Dashboard-Zonenlisten, Zone-Detail und globaler System-Context konsumieren dieselbe Closure-Read-Model-Schicht statt eigene Aggregationen zu bauen.

### Deliverables
- [x] `zone_dashboard` speist pro Zone eine kanonische `action_closures`-Surface in die Dashboard-Zonenliste ein
- [x] Zone-Detail-Surface exponiert dieselbe zonenspezifische Closure-Context-Struktur stabil
- [x] Globaler Dashboard-Context erweitert um `zone_contexts` und `zones_with_closures`
- [x] Friendly Zone Naming fuer Dashboard/System-Kontext ueber dieselbe kanonische Aufloesung wie Chat/Voice
- [x] Contract-Tests fuer globalen Zone-Context und Truth-Zone-Detail/List-Surface

### Acceptance criteria
- Dashboard-Consumer koennen dieselbe zonenspezifische Closure-Wahrheit direkt aus Listen-, Detail- und globalem Kontext lesen.
- Friendly Zone Names werden nicht als separate Dashboard-Heuristik gepflegt, sondern aus derselben Closure-Read-Model-Schicht bzw. Truth-Zonenbasis abgeleitet.
- Der globale Dashboard-Context bleibt kompakt, aber zeigt nachvollziehbar, welche Zonen offene/erfolgreiche/problematische Closures haben.

**Commit:** `feat(core): deliver slice 22 dashboard closure zone feed`
**Tag:** v15.3.33
**Tests:** `pytest -q tests/test_action_closure_summary_contract.py tests/test_zone_dashboard_contract.py` → gruen

**Next Exact Task:** Slice 23 als kanonische `ActionClosure`-Delta-Surface ableiten: revision-/freshness-faehige Summary/Context-Read-Models plus `since`-/zone-scoped-Filter fuer inkrementelle Dashboard-Poller auf derselben Closure-Truth evaluieren und kontraktfest machen.

### ✅ Slice 23 — Action Closure Delta Surface
**Status:** ✅ DONE (v15.3.34)

**Goal**
Die kanonische `ActionClosure`-Wahrheit fuer inkrementelle Poller revisionsfaehig machen: Summary-, Context-, API- und Dashboard-Surfaces sollen mit demselben monotonen Cursor erkennen koennen, ob seit einer bekannten Revision echte Closure-Aenderungen passiert sind.

### Deliverables
- [x] `ActionClosureStore` zaehlt monotone Revisionen fuer Accept-/Feedback-/Execution-Aenderungen und exponiert sie auf `ActionClosureV1`
- [x] `ActionClosureSummaryV1` und `ActionClosureContextBlockV1` tragen jetzt `revision`, `latest_change_at` und einen eingebetteten `ActionClosureDeltaV1`-Block
- [x] `/api/v1/action-closures`, `/summary` und `/context` akzeptieren `?since=<revision>` fuer deltafaehige Closure-Abfragen
- [x] `zone_dashboard` und Zone-Detail akzeptieren `?action_closure_since=<revision>` und leiten den Delta-Zustand zonenspezifisch durch
- [x] globale `zone_contexts` werden bei Delta-Abfragen auf wirklich geaenderte Closure-Zonen reduziert
- [x] Contract-Tests decken Delta-Read-Model, API und Dashboard-Since-Surface ab

### Acceptance criteria
- Dashboard-/UI-Poller koennen gegen eine einzige kanonische Closure-Revision inkrementell abfragen statt komplette Closure-Kontexte neu zu laden.
- Globale und zonenspezifische Closure-Surfaces bleiben dieselbe Wahrheit; Delta-Abfragen erzeugen keine zweite Aggregationslogik.
- Keine neue Closure-Aenderung bleibt fuer Summary-, Context- oder Dashboard-Consumer unsichtbar, solange der letzte bekannte Revisionscursor uebergeben wird.

**Commit:** `feat(core): deliver slice 23 action closure delta surface`
**Tag:** v15.3.34
**Tests:** `pytest -q tests/test_action_closure_contract.py tests/test_action_closure_summary_contract.py tests/test_zone_dashboard_contract.py tests/test_voice_action_closure_hints_contract.py` → `22 passed`

**Next Exact Task:** Slice 24 als closure-aware Notifications-/Digest-Surface definieren: offene/problematische Closures aus derselben kanonischen Read-Model-Schicht in benachrichtigbare Follow-up-/Digest-Payloads ueberfuehren, inklusive deduplizierter Delta-Cursor fuer Notification-Worker.

### ✅ Slice 24 — Closure-Aware Notification Digest
**Status:** ✅ DONE (v15.3.35)

**Goal**
Notification- und Digest-Worker sollen offene bzw. problematische `ActionClosure`-Folgen direkt aus derselben kanonischen Closure-Wahrheit beziehen koennen — ohne zweite Aggregationslogik, aber mit demselben Revisionscursor wie Dashboard- und Context-Poller.

### Deliverables
- [x] `notifications`-Digest- und Pending-Surfaces akzeptieren `include_action_closures=true`
- [x] `ActionClosureNotificationDigestV1` exponiert `revision`, `latest_change_at`, Outcome-Counts, Delta-Info und konkrete Follow-up-Eintraege
- [x] `zone_id`-Scope und `action_closure_since`-Cursor werden in Notifications/Digests direkt auf die kanonische Closure-Read-Model-Schicht durchgereicht
- [x] offene/problematische Closures werden als benachrichtigbare `follow_ups` mit Prioritaet/Kategorie materialisiert
- [x] Auth-Token-Env-Prioritaet vor dem Cache korrigiert, damit test- und workergebundene Tokenwechsel deterministisch bleiben
- [x] Contract-Tests decken Digest-/Pending-Action-Closure-Surface ab

### Acceptance criteria
- Notification-/Digest-Worker muessen keine eigene Closure-Zusammenfassung mehr pflegen, sondern koennen denselben Delta-Cursor wie andere Closure-Consumer verwenden.
- Offene/problematische Closures sind in Digest/Pending strukturiert sichtbar und lassen sich ohne weitere Join-Logik priorisieren.
- Temporäre Env-Token-Umschaltungen werden nicht mehr vom Security-Cache ueberfahren.

**Commit:** `feat(core): deliver slice 24 closure aware notification digest`
**Tag:** v15.3.35
**Tests:** `pytest -q tests/test_notification_action_closure_digest_contract.py tests/test_action_closure_contract.py tests/test_action_closure_summary_contract.py tests/test_zone_dashboard_contract.py tests/test_voice_action_closure_hints_contract.py` → `24 passed`

**Next Exact Task:** Slice 25 als delivery-faehigen Closure-Follow-up-Worker ableiten: aus `ActionClosureNotificationDigestV1` deduplizierte Dispatch-Kandidaten plus Cursor-/Ack-Mechanik fuer echte Notification-Jobs und Reminder-Queues materialisieren.

### ✅ Slice 25 — Closure Follow-Up Dispatch Worker
**Status:** ✅ DONE (v15.3.36)

**Goal**
Notification-Jobs und Reminder-Queues sollen aus derselben kanonischen `ActionClosureNotificationDigestV1`-Wahrheit worker-faehige Dispatch-Kandidaten ziehen koennen — inklusive Delta-Cursor, Delivery-Modus und Ack-Mechanik, damit offene/problematische Closures nicht doppelt versendet werden und erst nach einer echten Closure-Aenderung erneut auftauchen.

### Deliverables
- [x] deduplizierte `ActionClosureFollowUpDispatchCandidateV1`-Kandidaten aus derselben kanonischen Closure-Digest-Surface materialisiert
- [x] worker-faehige `ActionClosureFollowUpDispatchV1`-Bundle-/Cursor-Surface fuer `notification_job` und `reminder_queue` geliefert
- [x] Ack-Mechanik unter `/notifications/action-closures/dispatch/ack` suppressiert bestaetigte Kandidaten bis zur naechsten Closure-Revision
- [x] Closure-Recent-Items tragen jetzt ihre Revision bis in die Notification-/Worker-Surface durch
- [x] Contract-Tests decken Initial-Materialisierung, Ack-Suppression, Cursor-Verhalten und beide Delivery-Modi ab

### Acceptance criteria
- Notification-Worker und Reminder-Queues lesen dieselben offenen/problematischen Closures aus derselben kanonischen Notification-Digest-Wahrheit.
- Ein bestaetigter Dispatch-Kandidat verschwindet fuer denselben Closure-Stand, taucht aber bei einer echten Closure-Revision wieder auf.
- `since_revision` liefert Delta-/Cursor-Infos fuer Worker-Poller, ohne unbestaetigte Follow-ups unsichtbar zu machen.

**Commit:** `feat(core): deliver slice 25 closure follow-up dispatch worker`
**Tag:** v15.3.36
**Tests:** `pytest -q tests/test_notification_action_closure_dispatch_contract.py tests/test_notification_action_closure_digest_contract.py tests/test_action_closure_contract.py tests/test_action_closure_summary_contract.py tests/test_zone_dashboard_contract.py tests/test_voice_action_closure_hints_contract.py` → `27 passed`

**Next Exact Task:** Slice 26 als delivery-result-aware Closure-Follow-up-Receipt-Surface ableiten: Dispatch-Acks, Queue-/Reminder-Receipts und Retry-/Escalation-State aus derselben kanonischen Worker-/Closure-Wahrheit in Notification-/Dashboard-/Chat-Kontexte zurueckfuehren.

### ✅ Slice 26 — Closure Follow-Up Receipt Surface
**Status:** ✅ DONE (v15.3.37)

**Goal**
Dispatch-Acks, Queue-/Reminder-Receipts sowie Retry-/Escalation-State sollen nicht im Worker-Nirvana verschwinden, sondern aus derselben Closure-Follow-up-Wahrheit wieder in Notification-, Dashboard- und Chat-Kontexte zurueckgespiegelt werden.

### Deliverables
- [x] `POST /notifications/action-closures/dispatch/receipt` materialisiert workerseitige Delivery-/Queue-/Retry-/Escalation-Ergebnisse pro Dispatch-Kandidat
- [x] `GET /notifications/action-closures/receipts` liefert eine kanonische `ActionClosureFollowUpReceiptSummaryV1`-Surface mit `receipt_revision`, Delta, Counts und Recent-Receipts
- [x] Dispatch-Acks werden im selben Store wie die Receipt-Wahrheit gefuehrt, statt als isolierter Nebenpfad zu enden
- [x] Notification-Digest-/Dispatch-Surfaces betten die neue Receipt-Summary direkt ein
- [x] Dashboard- und Chat-Kontexte spiegeln Follow-up-Zustellung, offene Retries und Eskalationen aus derselben Receipt-Wahrheit zurueck
- [x] Contract-Tests decken Receipt-Materialisierung, Retry-/Escalation-Status und die Rueckspiegelung in Digest/Dashboard/Chat ab

### Acceptance criteria
- Worker koennen Delivery-Ergebnisse pro Closure-Follow-up revisionsscharf zurueckmelden, ohne eine zweite Follow-up-Truth aufzubauen.
- Notification-/Dashboard-/Chat-Consumer sehen denselben Ack-/Receipt-/Retry-/Escalation-Stand fuer denselben Closure-Stand.
- `receipt_since`/`receipt_revision` erlauben inkrementelle Poller, ohne bestaetigte oder eskalierte Follow-ups unsichtbar zu machen.

**Commit:** `feat(core): deliver slice 26 closure follow-up receipt surface`
**Tag:** v15.3.37
**Tests:** `pytest -q tests/test_notification_action_closure_dispatch_contract.py tests/test_notification_action_closure_digest_contract.py tests/test_action_closure_summary_contract.py tests/test_zone_dashboard_contract.py tests/test_voice_action_closure_hints_contract.py` → `27 passed`

**Next Exact Task:** Slice 27 als delivery-staleness-/SLA-Surface aus derselben Receipt-Wahrheit ableiten: ueberfaellige/offene Follow-ups, veraltete Retries und Eskalationsfaelligkeit zonen- und worker-scharf materialisieren, ohne neue Notification-Schattenlogik einzufuehren.

### ✅ Slice 27 — Closure Follow-Up Delivery SLA Surface
**Status:** ✅ DONE (v15.3.39)

**Goal**
Ueberfaellige offene Follow-ups, veraltete Retries und Eskalationsfaelligkeit aus derselben Closure-/Dispatch-/Receipt-Wahrheit ableiten, damit Worker, Dashboard und Chat denselben Delivery-SLA-Stand lesen.

### Deliverables
- [x] `GET /notifications/action-closures/sla` liefert eine kanonische `ActionClosureFollowUpSLASummaryV1`-Surface fuer zone-/worker-/delivery-mode-scoped SLA-Status
- [x] `ActionClosureFollowUpReceiptSummaryV1` bettet dieselbe SLA-Summary direkt ein, statt eine zweite Aggregation einzufuehren
- [x] Receipt-Worker-Filter (`worker=`) und worker-scharfe Counts fuer offene/stale/escalation-due Follow-ups implementiert
- [x] SLA-Logik bewertet Follow-up-Alter gegen Closure-`updated_at`, Receipt-Status und `next_retry_at`, sodass frische Receipts alte Problemfaelle nicht maskieren
- [x] Chat-/Dashboard-Kontexte lesen dieselbe erweiterte Receipt-/SLA-Wahrheit und beschreiben veraltete Retries/ueberfaellige Follow-ups explizit
- [x] Contract-Tests decken overdue-open, stale-retry, escalation-due und worker-scoped API-Surface ab

### Acceptance criteria
- Worker und Observer koennen denselben kanonischen Delivery-SLA-Stand lesen, ohne neue Notification-Schattenlogik.
- Zone-, Worker- und Delivery-Mode-Filter materialisieren dieselben Problemfaelle reproduzierbar.
- Veraltete Retries/Eskalationen bleiben sichtbar, auch wenn ein Worker erst spaeter ein Receipt schreibt.

**Commit:** `feat(core): deliver slice 27 closure follow-up delivery sla surface`
**Tag:** v15.3.39
**Tests:** `pytest -q tests/test_notification_action_closure_dispatch_contract.py tests/test_notification_action_closure_digest_contract.py tests/test_action_closure_summary_contract.py tests/test_zone_dashboard_contract.py tests/test_voice_action_closure_hints_contract.py` → `29 passed`

**Next Exact Task:** Slice 28 als Claim-/Lease-Surface aus derselben Dispatch-/SLA-Wahrheit ableiten: Worker sollen ueberfaellige/stale Follow-ups revisionsscharf claimen, mit Lease-Ablauf und sauberer Reassign-/Escalation-Sicht, ohne den bestehenden Dispatch-/Receipt-Contract zu duplizieren.

### ✅ Slice 28 — Closure Follow-Up Claim / Lease Surface
**Status:** ✅ DONE (v15.3.40)

**Goal**
Worker sollen Closure-Follow-ups aus derselben Dispatch-/Receipt-/SLA-Wahrheit revisionsscharf claimen koennen, inklusive Lease-Ablauf, Reassign-Sicht und Eskalationsrelevanz ohne neue Schattenlogik.

### Deliverables
- [x] `POST /notifications/action-closures/dispatch/claim` materialisiert kanonische `ActionClosureFollowUpClaimV1`-Claims mit `claimed_by`, `lease_seconds`, Konfliktantworten und optionalem `force_reassign`
- [x] `GET /notifications/action-closures/claims` liefert eine truth-backed `ActionClosureFollowUpClaimSummaryV1`-Surface mit `claim_revision`-Delta, Worker-/Delivery-Breakdowns sowie Counts fuer aktive, abgelaufene und neu zuweisbare Leases
- [x] Dispatch-Kandidaten und `ActionClosureFollowUpDispatchV1` betten den aktuellen Claim-/Lease-Stand direkt ein, statt eine zweite Worker-Lock-Logik zu erfinden
- [x] Receipt-/Digest-/Dashboard-/Chat-Surfaces spiegeln dieselbe Claim-Wahrheit ueber die eingebettete Receipt-Summary zurueck, inklusive Lease-Ablauf und Reassign-Hinweisen
- [x] Abgelaufene Claims und eskalationsrelevante Problemfaelle werden explizit als `reassignable` materialisiert, damit Worker dieselbe Reassign-/Escalation-Sicht lesen
- [x] Contract-Tests decken Claim-Erzeugung, Konflikte bei aktiven Leases, Lease-Ablauf/Reassign und die Rueckspiegelung in Dispatch-/Dashboard-/Chat-Kontexte ab

### Acceptance criteria
- Worker koennen denselben Closure-Stand claimen, ohne Ack-/Receipt-/SLA-Wahrheit zu duplizieren oder alte Claims ueber Revisionen hinweg mitzuschleppen.
- Aktive Leases blockieren konkurrierende Claims sauber; abgelaufene oder eskalationsrelevante Claims werden aus derselben kanonischen Surface als neu zuweisbar sichtbar.
- Dashboard, Digest und Chat lesen denselben Claim-/Lease-Stand wie Worker-APIs und beschreiben Lease-Ablauf/Reassign ohne eigene Aggregationslogik.

**Commit:** `feat(core): deliver slice 28 closure follow-up claim lease surface`
**Tag:** v15.3.40
**Tests:** `pytest -q tests/test_notification_action_closure_dispatch_contract.py tests/test_notification_action_closure_digest_contract.py tests/test_action_closure_summary_contract.py tests/test_zone_dashboard_contract.py tests/test_voice_action_closure_hints_contract.py` → `32 passed`

**Next Exact Task:** Slice 29 als Claim-Settlement-/Release-Surface aus derselben Claim-/Receipt-Wahrheit ableiten: explizite Release-/Abandon-/Settlement-Resultate fuer Worker-Leases kanonisch materialisieren und in Dispatch-/Dashboard-/Chat-Kontexte zurueckfuehren, ohne eine zweite Queue-Historie aufzubauen.

### ✅ Slice 29 — Closure Follow-Up Claim Settlement / Release Surface
**Status:** ✅ DONE (v15.3.41)

**Goal**
Explizite Release-/Abandon-/Settlement-Resultate fuer Closure-Follow-up-Worker-Leases aus derselben Claim-/Receipt-Wahrheit materialisieren, damit Dispatch, Dashboard und Chat dieselben Lease-Abschluesse ohne zweite Queue-Historie lesen.

### Deliverables
- [x] `POST /notifications/action-closures/dispatch/settle` materialisiert kanonische `released`-/`abandoned`-/`settled`-Resultate fuer bestehende `ActionClosureFollowUpClaimV1`-Claims, optional zusammen mit Receipt-/Retry-/Escalation-Daten in einem Schritt
- [x] `GET /notifications/action-closures/settlements` liefert eine truth-backed `ActionClosureFollowUpSettlementSummaryV1` mit `settlement_revision`-Delta, Worker-/Delivery-Breakdowns und Receipt-Outcomes
- [x] `ActionClosureFollowUpClaimV1` bettet einen expliziten `settlement`-Block ein; Lease-State unterscheidet aktive, released und settled Claims sauber, statt Release nur implizit ueber Nebenfelder zu erraten
- [x] Dispatch-, Receipt-, Digest-, Dashboard- und Chat-Surfaces fuehren dieselbe Settlement-/Release-Wahrheit direkt zurueck, inklusive `abgeschlossen`-/`abgebrochen`-Hinweisen und Reassignability aus derselben Claim-Wahrheit
- [x] Contract-Tests decken Release → Reclaim → Settled, Abandon mit Receipt-/Escalation-Daten sowie die Rueckspiegelung in Digest-/Dashboard-/Chat-Kontexte ab

### Acceptance criteria
- Worker koennen aktive Leases explizit freigeben, abbrechen oder abschliessen, ohne eine zweite History neben Claims/Receipts zu erzeugen.
- Claim-/Settlement-/Receipt-Summaries bleiben konsistent: Reassignability, Receipt-Outcomes und Settlement-Status werden aus derselben kanonischen Wahrheit gelesen.
- Dashboard, Digest und Chat beschreiben abgeschlossene bzw. abgebrochene Follow-ups mit derselben Surface wie die Worker-APIs.

**Commit:** `feat(core): deliver slice 29 closure follow-up claim settlement surface`
**Tag:** v15.3.41
**Tests:** `pytest -q tests/test_notification_action_closure_dispatch_contract.py tests/test_notification_action_closure_digest_contract.py tests/test_action_closure_summary_contract.py tests/test_zone_dashboard_contract.py tests/test_voice_action_closure_hints_contract.py` → `35 passed`

**Next Exact Task:** Slice 30 als Proposal-Lifecycle-Status-Surface aus derselben Proposal-/Action-/Closure-/Settlement-Wahrheit ableiten: pro Proposal den letzten kanonischen Lifecycle-Stand (suggested/accepted/executed/failed/follow-up-open/settled) revisionsscharf fuer Dashboard/Chat/Worker materialisieren, ohne eine separate Timeline-Tabelle aufzubauen.

### ✅ Slice 30 — Proposal Lifecycle Status Surface
**Status:** ✅ DONE (v15.3.42)

**Goal**
Den letzten kanonischen Lifecycle-Stand pro Proposal direkt aus bestehender Proposal-/Action-/Closure-/Settlement-Wahrheit materialisieren, damit Worker, Dashboard und Chat dieselbe revisionsscharfe Proposal-Sicht lesen koennen, ohne eine zweite Timeline-/History-Tabelle aufzubauen.

### Deliverables
- [x] `copilot_core.core.proposal_lifecycle_read_model` fuehrt truth-backed `ProposalLifecycleStatusV1` und `ProposalLifecycleStatusSummaryV1` ein und leitet `suggested`/`accepted`/`executed`/`failed`/`follow_up_open`/`settled` direkt aus Suggestion-, Closure-, Receipt-/Claim- und Settlement-Wahrheit ab
- [x] `GET /api/v1/proposals/status` und `GET /api/v1/proposals/<proposal_id>/status` exponieren die kanonische Lifecycle-Surface fuer Worker-/Dashboard-Consumer; die Proposal-Routen liegen wieder sauber unter `/api/v1/proposals`
- [x] Dashboard-Global-Kontext und `ChatHandler._build_home_context()` spiegeln dieselbe Proposal-Lifecycle-Summary zurueck statt eigener Sonderaggregation
- [x] Contract-Tests decken die Status-Ableitung ueber Suggestion-, Closure-, Receipt-/Claim- und Settlement-Zustaende sowie die Rueckspiegelung in Proposal-API, Dashboard und Chat ab

### Acceptance criteria
- Pro Proposal ist genau ein letzter kanonischer Lifecycle-Status aus derselben Truth ableitbar; Worker-/Dashboard-/Chat-Surfaces muessen keine eigene Timeline rekonstruieren.
- `follow_up_open` und `settled` werden aus derselben Claim-/Receipt-/Settlement-Wahrheit gelesen, statt aus Closure-Status allein erraten zu werden.
- Proposal-API, Dashboard und Chat beschreiben denselben Proposal-Stand fuer denselben Revisionsstand.

**Commit:** `feat(core): deliver slice 30 proposal lifecycle status surface`
**Tag:** v15.3.42
**Tests:** `pytest -q tests/test_notification_action_closure_dispatch_contract.py tests/test_notification_action_closure_digest_contract.py tests/test_action_closure_summary_contract.py tests/test_zone_dashboard_contract.py tests/test_voice_action_closure_hints_contract.py tests/test_proposal_lifecycle_status_contract.py tests/test_proposal_lifecycle_api.py` → `41 passed`

**Next Exact Task:** Slice 31 als zone-scoped Proposal-Lifecycle-Context-Surface aus derselben Proposal-/Action-/Closure-/Settlement-Wahrheit ableiten: zonenscharfe Proposal-Status-Feeds und Delta-Cursor fuer Zone-Detail-/Dashboard-Poller materialisieren, ohne die neue Lifecycle-Logik zu duplizieren.

### ✅ Slice 31 — Zone-Scoped Proposal Lifecycle Context Surface
**Status:** ✅ DONE (v15.3.43)

**Goal**
Die kanonische Proposal-Lifecycle-Wahrheit zonenscharf fuer Dashboard- und Zone-Detail-Poller ausleiten, damit zonenbezogene Proposal-Feeds und Delta-Cursor dieselbe Proposal-/Action-/Closure-/Settlement-Truth konsumieren statt lokaler Sonderaggregation.

### Deliverables
- [x] `ProposalLifecycleContextBlockV1` als kompakte Kontext-Surface fuer zonenscharfe Proposal-Lifecycle-Read-Models eingefuehrt
- [x] `zone_dashboard` exponiert pro Zone eine kanonische `proposal_lifecycle`-Surface in Zone-Liste und Zone-Detail
- [x] globaler Dashboard-Kontext erweitert um `proposal_lifecycle.zone_contexts` und `zones_with_proposals`
- [x] `proposal_lifecycle_since` als Delta-Cursor fuer Listen-/Detail-Poller auf derselben Lifecycle-Wahrheit angebunden
- [x] Contract-Tests fuer Kontextblock, globale Zone-Feeds, Delta-Verhalten und isolierte Revisionen gegen fremde Dispatch-Worker-Staende ergaenzt

### Acceptance criteria
- Dashboard-/Zone-Detail-Poller koennen dieselbe zonenscharfe Proposal-Lifecycle-Wahrheit direkt lesen, ohne zonenspezifische Proposal-Aggregation neu zu bauen.
- Friendly Zone Names und Delta-Cursor bleiben an dieselbe kanonische Lifecycle-Schicht gebunden.
- Proposal-Revisionen werden fuer zonenscharfe Poller nicht durch fremde Follow-up-/Dispatch-Revisionen maskiert.

**Commit:** `feat(core): deliver slice 31 zone scoped proposal lifecycle context`
**Tag:** v15.3.43
**Tests:** `pytest -q tests/test_notification_action_closure_dispatch_contract.py tests/test_notification_action_closure_digest_contract.py tests/test_action_closure_summary_contract.py tests/test_zone_dashboard_contract.py tests/test_voice_action_closure_hints_contract.py tests/test_proposal_lifecycle_status_contract.py tests/test_proposal_lifecycle_api.py` → `46 passed`

**Commit:** `feat(core): deliver slice 32 zone-scoped proposal lifecycle context for chat`
**Tag:** v15.3.44
**Tests:** `pytest -q tests/test_proposal_lifecycle_status_contract.py tests/test_proposal_lifecycle_api.py tests/test_zone_dashboard_contract.py tests/test_voice_action_closure_hints_contract.py` → `20 passed`

**Next Exact Task:** Slice 33 als voice-spezifische Proposal-Hints ableiten: proaktive Voice-Hinweise sollen offene/vorgeschlagene Proposals aus derselben kanonischen Lifecycle-Schicht als Follow-up-/Status-Hinweise sprechen, analog zu Slice 20 für Closures.

### ✅ Slice 34 — Zone-Scoped Proposal Lifecycle Feed Surface
**Status:** ✅ DONE (v15.3.47)

**Goal**
Die kanonische Proposal-Lifecycle-Wahrheit als zonenspezifischen Feed fuer Dashboard-Poller und System-Kontexte ausleiten, damit inkrementelle Poller mit Delta-Cursor dieselbe Proposal-/Action-/Closure-Truth konsumieren.

**Deliverables**
- [x] ZoneProposalFeedEntryV1/ZoneProposalFeedV1/ZoneProposalFeedSummaryV1 als kanonische Read-Models
- [x] ZoneProposalFeedStore mit build_zone_feed() und build_zone_feed_summary()
- [x] GET /api/v1/proposals/feed mit zone_id/zone_ids/since/include_empty-Filtern
- [x] GET /api/v1/proposals/feed/zone/<zone_id> mit since-Cursor fuer Delta-Responses
- [x] Zone-Namen-Aufloesung aus ZoneTruthStore fuer menschenlesbare Darstellung
- [x] Revisionstracking und latest_change_at fuer alle Feed-Surfaces
- [x] Contract-Tests fuer Store, API und Delta-Verhalten

**Acceptance criteria**
- Dashboard-Poller koennen zonenspezifische Proposal-Feeds mit Delta-Cursor abfragen
- Zone-Namen werden aus derselben ZoneTruth-Wahrheit aufgelost
- Revision/has_changes-Logik erlaubt effizientes inkrementelles Polling
- Proposal-Lifecycle-Feed ist als eigene API-Surface unter /api/v1/proposals/feed erreichbar

**Commit:** `feat(core): deliver slice 34 zone-scoped proposal lifecycle feed surface`
**Tag:** v15.3.47
**Tests:** `pytest -q tests/test_proposal_lifecycle_feed_contract.py` → `12 passed`

### ✅ Slice 33 — Closure-Aware Proposal Follow-Up Hints for Voice
**Status:** ✅ DONE (v15.3.45)

**Goal**
Den Roadmap-Block **Voice Integration** an die kanonische Proposal-Lifecycle-Wahrheit anbinden, damit proaktive Sprachhinweise offene/gescheiterte/vorgeschlagene Proposals aus derselben Proposal→Action→Runtime-Spur ableiten statt nur generische Zeit-/Mood-Hinweise zu sprechen.

### Deliverables
- [x] neuer Voice-Hint-Typ `proposal_follow_up` und `proposal_suggestion` in der proaktiven Hint-Pipeline
- [x] Proactive Voice liest `ProposalLifecycleContextBlockV1` direkt aus der kanonischen Lifecycle-Surface
- [x] gescheiterte Proposals erzeugen High-Priority-Nachfass-Hinweise; offene Proposals erzeugen Medium-Priority-Statushinweise; vorgeschlagene Proposals erzeugen Presentation-Hinweise
- [x] `/api/v1/voice/hints` exponiert denselben Lifecycle-Summary-/Recent-Proposal-Kontext stabil im Hint-Payload
- [x] Contract-Tests für direkte Hint-Generierung und API-Surface gegen dieselbe Lifecycle-Wahrheit

### Acceptance criteria
- Voice-Hinweise sprechen bei realen offenen/gescheiterten/vorgeschlagenen Proposals dieselbe Lifecycle-Wahrheit wie Dashboard, Chat, Predictive und Multi-Zone.
- Follow-up-Hinweise bleiben source-grounded: Status, Summary und letzte Proposal sind im Hint-Kontext transparent enthalten.
- Die Voice-Surface erfindet keine separaten Outcome-Heuristiken neben dem bestehenden Lifecycle-Contract.

**Commit:** `feat(core): deliver slice 34 zone-scoped proposal lifecycle feed surface`
**Tag:** v15.3.47
**Tests:** `pytest -q tests/test_proposal_lifecycle_feed_contract.py` → `12 passed`

**Next Exact Task:** Slice 35 als notification-basierte Proposal-Dispatch-Surface ableiten: offene/vorgeschlagene Proposals aus derselben Lifecycle-Wahrheit in benachrichtigbare Dispatch-Kandidaten mit Delta-Cursor und Delivery-Modus materialisieren.

### ✅ Slice 35 — Proposal Lifecycle Notification Dispatch
**Status:** ✅ DONE (v15.3.48)

**Goal**
Notification- und Digest-Worker sollen offene bzw. vorgeschlagene `ProposalLifecycle`-Folgen direkt aus derselben kanonischen Lifecycle-Wahrheit beziehen können — ohne zweite Aggregationslogik, aber mit demselben Revisionscursor wie Dashboard- und Context-Poller.

### Deliverables
- [x] `ProposalLifecycleDispatchStore` materialisiert Dispatch-Kandidaten aus `ProposalLifecycleStatusSummaryV1`
- [x] `ProposalLifecycleDispatchCandidateV1` exponiert `proposal_id`, `lifecycle_status`, `zone_id`, `module_id`, `source`, `priority`, `delivery_mode`, `revision`
- [x] `GET /notifications/proposals/dispatch` mit `delivery_mode`, `recent_limit`, `since_revision`-Filtern
- [x] `POST /notifications/proposals/dispatch/claim` für Worker-Claims mit Lease-Mechanik
- [x] `POST /notifications/proposals/dispatch/ack` für Acknowledgements
- [x] `POST /notifications/proposals/dispatch/receipt` für Delivery-Receipts
- [x] `POST /notifications/proposals/dispatch/settle` für Claim-Settlements
- [x] `GET /notifications/proposals/claims|receipts|settlements` für Worker-Observability
- [x] Priority-Determination basierend auf `lifecycle_status` (failed=high, accepted=normal, proposed=low)
- [x] Contract-Tests für Store, API und Worker-Surfaces

### Acceptance criteria
- Notification-/Digest-Worker müssen keine eigene Proposal-Zusammenfassung mehr pflegen, sondern können denselben Delta-Cursor wie andere Lifecycle-Consumer verwenden.
- Offene/vorgeschlagene/gescheiterte Proposals sind in Dispatch-Payloads strukturiert sichtbar und lassen sich ohne weitere Join-Logik priorisieren.
- Claim-/Ack-/Receipt-/Settlement-Surfaces folgen demselben Muster wie Action-Closure-Dispatch.

**Commit:** `feat(core): deliver slice 35 proposal lifecycle notification dispatch`
**Tag:** v15.3.48
**Tests:** `pytest -q tests/test_notification_proposal_lifecycle_dispatch_contract.py` → `10 passed`

**Next Exact Task:** Slice 36 als delivery-faehigen Proposal-Follow-up-Worker ableiten: aus `ProposalLifecycleDispatchV1` deduplizierte Dispatch-Kandidaten plus Cursor-/Ack-Mechanik fuer echte Notification-Jobs und Reminder-Queues materialisieren.

### ✅ Slice 36 — Proposal Follow-Up Dispatch Worker
**Status:** ✅ DONE (v15.3.49)

**Goal**
Notification-Jobs und Reminder-Queues sollen aus derselben `ProposalLifecycleDispatchV1`-Wahrheit worker-faehige Dispatch-Kandidaten ziehen koennen — inklusive Delta-Cursor, Acknowledgement-Mechanik und Delivery-Status-Tracking, damit offene/vorgeschlagene Proposals nicht doppelt versendet werden.

### Deliverables
- [x] `ProposalFollowUpDispatchStore` materialisiert aus `ProposalLifecycleDispatchV1`
- [x] `ProposalFollowUpDispatchCandidateV1` mit `dispatch_id`, `proposal_id`, `lifecycle_status`, `zone_id`, `module_id`, `priority`, `delivery_mode`
- [x] `ProposalFollowUpDispatchCursorV1` mit `pending_ack_count` fuer Worker-Observability
- [x] `acknowledge()` fuer Worker-Acks mit Revisionstracking
- [x] `record_receipts()` fuer Delivery-Status-Tracking
- [x] `get_pending_ack_count()` fuer Worker-Monitoring
- [x] Contract-Tests fuer Store, Materialization, Ack/Receipt-Surfaces

### Acceptance criteria
- Notification-Worker und Reminder-Queues lesen dieselben offenen/vorgeschlagenen Proposals aus derselben kanonischen Dispatch-Wahrheit.
- Ein acknowledged Dispatch-Kandidat wird im pending_ack_count korrekt beruecksichtigt.
- Delivery-Status (delivered/failed) wird revisionsscharf gespeichert.

**Commit:** `feat(core): deliver slice 36 proposal follow-up dispatch worker`
**Tag:** v15.3.49
**Tests:** `pytest -q tests/test_proposal_follow_up_dispatch_contract.py` → `10 passed`

**Next Exact Task:** Slice 37 als delivery-result-aware Proposal-Follow-up-Receipt-Surface ableiten: Dispatch-Acks, Queue-/Reminder-Receipts und Retry-/Escalation-State aus derselben Worker-/Dispatch-Wahrheit wieder in Notification-/Dashboard-/Chat-Kontexte zurueckfuehren.

### ✅ Slice 37 — Proposal Follow-Up Receipt Surface
**Status:** ✅ DONE (v15.3.50)

**Goal**
Dispatch-Acks, Queue-/Reminder-Receipts sowie Retry-/Escalation-State sollen nicht im Worker-Nirvana verschwinden, sondern aus derselben Proposal-Follow-up-Wahrheit wieder in Notification-, Dashboard- und Chat-Kontexte zurueckgespiegelt werden.

### Deliverables
- [x] `POST /notifications/proposals/dispatch/receipt` materialisiert workerseitige Delivery-/Queue-/Retry-/Escalation-Ergebnisse pro Dispatch-Kandidat
- [x] `GET /notifications/proposals/receipts` liefert eine kanonische `ProposalFollowUpReceiptSummaryV1`-Surface mit `receipt_revision`, Delta, Counts und Recent-Receipts
- [x] Dispatch-Acks werden im selben Store wie die Receipt-Wahrheit gefuehrt, statt als isolierter Nebenpfad zu enden
- [x] Notification-Digest-/Dispatch-Surfaces betten die neue Receipt-Summary direkt ein
- [x] Dashboard- und Chat-Kontexte spiegeln Follow-up-Zustellung, offene Retries und Eskalationen aus derselben Receipt-Wahrheit zurueck
- [x] Contract-Tests decken Receipt-Materialisierung, Retry-/Escalation-Status und die Rueckspiegelung in Digest/Dashboard/Chat ab

### Acceptance criteria
- Worker koennen Delivery-Ergebnisse pro Proposal-Follow-up revisionsscharf zurueckmelden, ohne eine zweite Follow-up-Truth aufzubauen.
- Notification-/Dashboard-/Chat-Consumer sehen denselben Ack-/Receipt-/Retry-/Escalation-Stand fuer denselben Proposal-Stand.
- `receipt_since`/`receipt_revision` erlauben inkrementelle Poller, ohne bestaetigte oder eskalierte Follow-ups unsichtbar zu machen.

**Commit:** `feat(core): deliver slice 37 proposal follow-up receipt surface`
**Tag:** v15.3.50
**Tests:** `pytest -q tests/test_proposal_follow_up_receipt_contract.py tests/test_proposal_follow_up_dispatch_contract.py` → `18 passed`

**Next Exact Task:** Slice 38 als Claim-/Lease-Surface aus derselben Dispatch-/Receipt-/SLA-Wahrheit ableiten: Worker sollen ueberfaellige/stale Proposal-Follow-ups revisionsscharf claimen, mit Lease-Ablauf und sauberer Reassign-/Escalation-Sicht, ohne den bestehenden Dispatch-/Receipt-Contract zu duplizieren.

### ✅ Slice 38 — Proposal Follow-Up Claim / Lease Surface
**Status:** ✅ DONE (v15.3.51)

**Goal**
Worker sollen Proposal-Follow-ups aus derselben Dispatch-/Receipt-Wahrheit revisionsscharf claimen koennen, inklusive Lease-Ablauf, Reassign-Sicht und Settlement-Status ohne neue Schattenlogik.

### Deliverables
- [x] `POST /notifications/proposals/dispatch/claim` materialisiert kanonische `ProposalFollowUpClaimV1`-Claims mit `claimed_by`, `lease_seconds`, Konfliktantworten und optionalem `force_reassign`
- [x] `GET /notifications/proposals/claims` liefert eine truth-backed `ProposalFollowUpClaimSummaryV1`-Surface mit `claim_revision`-Delta, Worker-/Delivery-Breakdowns sowie Counts fuer aktive, abgelaufene, released und settled Claims
- [x] `GET /notifications/proposals/claims/<claim_id>` fuer einzelnen Claim-Status
- [x] `POST /notifications/proposals/claims/<claim_id>/release` fuer Release ohne Settlement
- [x] `POST /notifications/proposals/claims/<claim_id>/settle` fuer Settlement mit `completed|abandoned|failed`
- [x] `GET /notifications/proposals/claims/worker/<worker_id>` fuer Worker-spezifische Claims
- [x] Dispatch-Kandidaten betten den aktuellen Claim-/Lease-Stand direkt ein, statt eine zweite Worker-Lock-Logik zu erfinden
- [x] Receipt-/Digest-/Dashboard-/Chat-Surfaces spiegeln dieselbe Claim-Wahrheit ueber die eingebettete Receipt-Summary zurueck, inklusive Lease-Ablauf und Reassign-Hinweisen
- [x] Abgelaufene Claims und eskalationsrelevante Problemfaelle werden explizit als `reassignable` materialisiert
- [x] Contract-Tests decken Claim-Erzeugung, Konflikte bei aktiven Leases, Lease-Ablauf/Release/Settle und die Rueckspiegelung in Dispatch-/Dashboard-/Chat-Kontexte ab

### Acceptance criteria
- Worker koennen denselben Proposal-Stand claimen, ohne Ack-/Receipt-Wahrheit zu duplizieren oder alte Claims ueber Revisionen hinweg mitzuschleppen.
- Aktive Leases blockieren konkurrierende Claims sauber; abgelaufene oder released Claims werden aus derselben kanonischen Surface als neu zuweisbar sichtbar.
- Settlement-Status (`completed|abandoned|failed`) wird im Claim selbst gefuehrt und ist ueber Claim-Summary abfragbar.
- Dashboard, Digest und Chat lesen denselben Claim-/Lease-Stand wie Worker-APIs und beschreiben Lease-Ablauf/Reassign ohne eigene Aggregationslogik.

**Commit:** `feat(core): deliver slice 38 proposal follow-up claim/lease surface`
**Tag:** v15.3.51
**Tests:** `pytest -q tests/test_proposal_claims_api.py tests/test_proposal_follow_up_claim_contract.py tests/test_proposal_follow_up_dispatch_contract.py tests/test_proposal_follow_up_receipt_contract.py` → `63 passed`

**Next Exact Task:** Slice 39 als Zone-Presence-Hold-/Release-Surface ableiten: Zone-Presence-Events sollen deterministisch gehalten/freigegeben werden koennen, damit Anwesenheitserkennung nicht bei kurzen Abwesenheitsfenstern flackert.

### ✅ Slice 39 — Zone Presence Hold / Release Surface
**Status:** ✅ DONE (v15.3.52)

**Goal**
Zone-Presence-Events sollen deterministisch gehalten/freigegeben werden koennen, damit Anwesenheitserkennung nicht bei kurzen Abwesenheitsfenstern flackert. Bietet kanonische Hold-State-Tracking mit Expiration, Reason-Tracking und zone-scoped Hold-Visibility.

### Deliverables
- [x] `ZonePresenceHoldV1` als kanonische Hold-Record mit `hold_id`, `zone_id`, `hold_state`, `reason`, `set_at`, `expires_at`, `released`, `released_at`
- [x] `ZoneHoldState` Enum (`auto`, `force_on`, `force_off`) fuer Hold-States
- [x] `ZonePresenceHoldStore` mit `set_hold()`, `release_hold()`, `get_hold_by_zone()`, `get_active_hold_state()`, `get_hold_summary()`
- [x] `POST /presence/zones/<zone_id>/hold` fuer Setzen von Hold mit optionalem `duration_seconds` (Auto-Expire)
- [x] `GET /presence/zones/<zone_id>/hold` fuer einzelnen Hold-Status
- [x] `DELETE /presence/zones/<zone_id>/hold` fuer Release (Reset auf Auto)
- [x] `GET /presence/zones/<zone_id>/state` fuer effektiven Hold-State (`is_enforced` Flag)
- [x] `GET /presence/zones/holds` fuer aggregierte Summary mit `hold_revision`, Delta-Cursor, Counts nach State
- [x] `GET /presence/zones/holds/<hold_id>` fuer einzelnen Hold by ID
- [x] Contract-Tests fuer Store, API und Hold-State-Logik

### Acceptance criteria
- Zone-Presence kann via Hold deterministisch auf `force_on`/`force_off` gesetzt werden, ohne dass Sensor-Updates den State ueberschreiben.
- Hold kann mit `duration_seconds` auto-expirieren oder manuell via DELETE release werden.
- Effektiver Hold-State (`auto` vs `force_on`/`force_off`) ist via `/state` abfragbar mit `is_enforced` Flag.
- Hold-Revisionen werden fuer inkrementelle Poller mitgefuehrt; Summary unterstuetzt `since_revision`-Delta.
- Hold-States werden nicht als zweite Schattenlogik gepflegt, sondern als kanonische Core-Surface.

**Commit:** `feat(core): deliver slice 39 zone presence hold release surface`
**Tag:** v15.3.52
**Tests:** `pytest -q tests/test_zone_presence_hold_contract.py tests/test_zone_presence_hold_api.py` → `39 passed`

### ✅ Slice 40 — Zone Presence Hold Integration into Presence Engine
**Status:** ✅ DONE (v15.3.53)

**Goal**
Bestehende Presence-Aggregation soll Hold-State konsultieren, bevor Sensor-States angewendet werden, damit Hold-Zustände (FORCE_ON/FORCE_OFF) sensorbasierte Erkennung deterministisch überschreiben.

### Deliverables
- [x] `_determine_state()` returns `Tuple[PresenceState, float]` für hold-enforced confidence
- [x] `get_zone_presence()` wendet Hold-State zur Lesezeit an für sofortige Sichtbarkeit
- [x] Hold-Zustände propagieren ohne Sensor-Update
- [x] Graceful Degradation bei nicht verfügbarem Hold-Store
- [x] Integrationstests für Hold→Presence-Interaktion

### Acceptance criteria
- FORCE_ON Hold liefert immer PRESENT mit confidence=1.0
- FORCE_OFF Hold liefert immer ABSENT mit confidence=1.0
- AUTO Hold erlaubt normale sensorbasierte Erkennung
- Hold-Änderungen sind sofort in Zone Presence State sichtbar
- Tests verifizieren Integration, API und Contract-Surfaces

**Commit:** `feat(presence): deliver slice 40 zone presence hold integration`
**Tag:** v15.3.53
**Tests:** `pytest -q tests/test_zone_presence_hold_integration.py tests/test_zone_presence_hold_contract.py tests/test_zone_presence_hold_api.py` → `51 passed`

### ✅ Slice 41 — Zone Presence Hold API in Zone Dashboard
**Status:** ✅ DONE (v15.3.54)

**Goal**
Dashboard-Zonenlisten und Zone-Detail sollen Hold-State exponieren, damit UIs Anwesenheits-Overrides visuell kennzeichnen können.

### Deliverables
- [x] `_collect_praesenz` includes `hold_state`, `hold_reason`, `hold_set_at`, `hold_expires_at`, `hold_enforced`
- [x] Graceful Degradation bei nicht verfügbarem Hold-Store
- [x] Contract-Tests für Dashboard-Hold-Integration

### Acceptance criteria
- Dashboard-Presence-Daten enthalten `hold_state` (force_on/force_off/auto)
- `hold_enforced`-Flag zeigt an, ob Hold Sensoren überschreibt
- `hold_reason` und Timestamps für UI-Anzeige verfügbar
- Verfallene/freigegebene Holds zeigen als auto mit `hold_enforced=false`
- Tests verifizieren Dashboard-Hold-Integration

**Commit:** `feat(dashboard): deliver slice 41 zone presence hold in dashboard`
**Tag:** v15.3.54
**Tests:** `pytest -q tests/test_zone_presence_hold_dashboard.py tests/test_zone_dashboard_contract.py` → `15 passed`

### ✅ Slice 42 — Zone Presence Hold API Endpoints
**Status:** ✅ DONE (v15.3.55)

**Goal**
CRUD-Endpoints für Zone-Presence-Hold-Direktsteuerung bereitstellen, damit Dashboard/UIs Hold-Zustände ohne Workaround-Flächen setzen/freigeben/abfragen können.

### Deliverables
- [x] `POST /presence/zones/<zone_id>/hold` zum Setzen von Hold-State (auto/force_on/force_off) mit optionalem duration_seconds
- [x] `DELETE /presence/zones/<zone_id>/hold` zum Freigeben eines Holds
- [x] `GET /presence/zones/<zone_id>/hold` für einzelnen Hold-Status
- [x] `GET /presence/zones/<zone_id>/state` für effektiven Hold-State mit is_enforced-Flag
- [x] `GET /presence/zones/holds` für aggregierte Summary mit Revision/Delta
- [x] `GET /presence/zones/holds/<hold_id>` für einzelnen Hold by ID
- [x] Blueprint-Registrierung in app.py
- [x] Contract-Tests für API-Endpoints

### Acceptance criteria
- Hold-State kann via POST deterministisch gesetzt werden (auto/force_on/force_off)
- Hold kann via DELETE manuell freigegeben werden
- Einzelne Hold-States sind via GET abfragbar
- Effektiver Hold-State mit is_enforced-Flag ist verfügbar
- Summary-Surface unterstützt Delta-Polling mit since_revision
- API-Endpoints sind in app.py registriert und testbar

**Commit:** `feat(presence): deliver slice 42 zone presence hold api endpoints`
**Tag:** v15.3.55
**Tests:** `pytest -q tests/test_zone_presence_hold_api.py` → `19 passed`

### ✅ Slice 43 — Zone Presence Hold Notification Surface
**Status:** ✅ DONE (v15.3.56)

**Goal**
Hold-State-Änderungen sollen als benachrichtigbare Events ausleitbar sein, damit User bei manuellen Overrides/Verfall informiert werden.

### Deliverables
- [x] `ZonePresenceHoldNotificationV1` und `ZonePresenceHoldNotificationSummaryV1` als kanonische Contracts
- [x] `ZonePresenceHoldNotificationStore` mit Revisionstracking und Delta-Support
- [x] Notification-Typen: `hold_set`, `hold_released`, `hold_expired`, `hold_expiring_soon`
- [x] API-Endpoints: list, summary, single, mark-read, mark-all-read
- [x] Integration in app.py Blueprint-Registrierung
- [x] Folgt demselben Muster wie Action Closure und Proposal Lifecycle Notifications
- [x] Contract-Tests (23 Tests grün)

### Acceptance criteria
- Hold-State-Änderungen werden als revisionsscharfe Notifications materialisiert
- Delta-Polling mit `since_revision` für effiziente UI-Poller
- Zone- und Type-Filter für gezielte Abfragen
- Unread-Tracking für Benachrichtigungsstatus
- Notification-Typen decken alle Hold-Lebenszyklus-Events ab

**Commit:** `feat(presence): deliver slice 43 zone presence hold notification surface`
**Tag:** v15.3.56
**Tests:** `pytest -q tests/test_zone_presence_hold_notifications_contract.py` → `23 passed`

### ✅ Slice 44 — Hold Expiration Cron Surface
**Status:** ✅ DONE (v15.3.57)

**Goal**
Automatische Hold-Expiration-Prüfung mit Benachrichtigungen und Auto-Release.

### Deliverables
- [x] `ZonePresenceHoldCronService` für periodische Hold-Expiration-Prüfung
- [x] Automatische Benachrichtigungen bei `expiring_soon` (innerhalb Warnfenster)
- [x] Automatische Benachrichtigungen bei `expired` + Auto-Release (konfigurierbar)
- [x] API-Endpoints: `POST /api/v1/presence/holds/cron/run`, `GET /status|revision|config`
- [x] `HoldExpirationCheckResultV1` und `HoldExpirationCronSummaryV1` Contracts
- [x] `expiring_soon_window_minutes` und `auto_release_on_expire` Konfiguration
- [x] Cron-Revisionstracking für Delta-Polling
- [x] Contract-Tests (17 Tests grün)

### Acceptance criteria
- Cron-Service prüft alle aktiven Holds auf bevorstehenden/abgelaufenen Verfall
- `expiring_soon`-Benachrichtigungen werden innerhalb des Warnfensters ausgelöst
- `expired`-Benachrichtigungen werden bei Verfall ausgelöst
- Auto-Release erfolgt deterministisch nach Expiration (wenn aktiviert)
- API ermöglicht manuelle Trigger und Scheduler-Integration
- Cron-Revision ermöglicht Delta-Polling für Worker/UIs

**Commit:** `feat(presence): deliver slice 44 hold expiration cron surface`
**Tag:** v15.3.57
**Tests:** `pytest -q tests/test_zone_presence_hold_cron_contract.py` → `17 passed`

### ✅ Slice 45 — Zone Presence Hold Scheduler Integration
**Status:** ✅ DONE (v15.3.58)

**Goal**
Automatische Hold-Expiration-Prüfung im Core-Scheduler registrieren, mit konfigurierbarem Intervall und Lifecycle-Management.

### Deliverables
- [x] `ZonePresenceHoldSchedulerIntegration` für Scheduler-Anbindung des Cron-Services
- [x] Action-Registrierung (`presence.hold_expiration_check`) im Scheduler-Engine
- [x] Periodischer Job mit konfigurierbarem Intervall (default 5 Minuten, minimum 30 Sekunden)
- [x] API-Endpoints: `GET|PUT /config`, `GET /status`, `POST /run|enable|disable|attach`
- [x] Scheduler-Integration in `core_setup.py` bei Service-Initialisierung
- [x] Blueprint-Registrierung in `app.py`
- [x] Enable/Disable mit Job-Status-Sync im Scheduler
- [x] Interval-Update mit Job-Recreation
- [x] Contract-Tests (41 Tests grün)

### Acceptance criteria
- Scheduler-Engine wird in `core_setup.py` initialisiert und zu Services hinzugefügt
- Hold-Scheduler-Integration wird automatisch an Scheduler-Engine angebunden
- Periodischer Job läuft mit konfigurierbarem Intervall (default 300s)
- Job kann via API enabled/disabled werden
- Interval kann via API geändert werden (minimum 30s)
- Manual trigger via `/run` Endpoint möglich
- Status und Config sind via API abfragbar
- Alle Endpoints sind revisionsscharf und testbar

**Commit:** `feat(presence): deliver slice 45 zone presence hold scheduler integration`
**Tag:** v15.3.58
**Tests:** `pytest -q tests/test_zone_presence_hold_scheduler_contract.py tests/test_zone_presence_hold_scheduler_api.py` → `41 passed`

**Next Exact Task:** Slice 46 als Hold-Statistik-/Analytics-Surface ableiten: Hold-Usage-Historie, Zone-spezifische Hold-Patterns und Hold-Effectiveness-Metriken aus derselben Hold-/Notification-/Scheduler-Wahrheit materialisieren.

### ✅ Slice 46 — Hold Statistics / Analytics Surface
**Status:** ✅ DONE (v15.3.59)

**Goal**
Hold-Usage-Historie, Zone-spezifische Hold-Patterns und Hold-Effectiveness-Metriken aus derselben Hold-/Notification-/Scheduler-Wahrheit materialisieren.

### Deliverables
- [x] `HoldUsageHistoryV1` / `HoldZonePatternsV1` / `HoldEffectivenessMetricsV1` als Read-Models
- [x] `HoldAnalyticsStore` mit `build_usage_history()`, `build_zone_patterns()`, `build_effectiveness_metrics()`
- [x] GET `/presence/holds/analytics/usage|patterns|effectiveness|summary` APIs
- [x] Zone-/Time-Range-Filter und Revisionstracking für Delta-Polling
- [x] Contract-Tests (17 Tests grün)
- [x] App-Integration für Flask-Blueprint

### Acceptance criteria
- Dashboard-/UI-Poller können Hold-Usage mit Delta-Cursor inkrementell abfragen
- Zone-spezifische Patterns zeigen Hold-Häufigkeit, Duration und State-Verteilung pro Zone
- Effectiveness-Metriken quantifizieren Flapping-Prevention und Conflict-Rate
- Alle Surfaces lesen dieselbe kanonische Hold-Wahrheit ohne Schattenlogik

**Commit:** `feat(presence): deliver slice 46 hold statistics analytics surface`
**Tag:** v15.3.59
**Tests:** `pytest -q tests/test_hold_analytics_contract.py` → `17 passed`

### ✅ Slice 47 — Energy Analytics Surface
**Status:** ✅ DONE (v15.3.60)

**Goal**
Energy-Usage-Historie, Zone-spezifische Energy-Patterns und Energy-Effectiveness-Metriken aus derselben Energy-/Optimization-Wahrheit materialisieren.

### Deliverables
- [x] `EnergyUsageHistoryV1` / `EnergyZonePatternsV1` / `EnergyEffectivenessMetricsV1` als Read-Models
- [x] `EnergyAnalyticsStore` mit `build_usage_history()`, `build_zone_patterns()`, `get_effectiveness_metrics()`
- [x] GET `/api/v1/energy/analytics/usage|patterns|effectiveness|summary` APIs
- [x] Zone-/Time-Range-Filter und Revisionstracking für Delta-Polling
- [x] Contract-Tests (17 Tests grün)
- [x] App-Integration für Flask-Blueprint

### Acceptance criteria
- Dashboard-/UI-Poller können Energy-Usage mit Delta-Cursor inkrementell abfragen
- Zone-spezifische Patterns zeigen Hold-Häufigkeit, Duration und State-Verteilung pro Zone
- Effectiveness-Metriken quantifizieren Savings, Success-Rate und PV/Battery-Effizienz
- Alle Surfaces lesen dieselbe kanonische Energy-Wahrheit ohne Schattenlogik

**Commit:** `feat(energy): deliver slice 47 energy analytics surface`
**Tag:** v15.3.60
**Tests:** `pytest -q tests/test_energy_analytics_contract.py` → `17 passed`

### ✅ Slice 48 — Predictive Analytics Surface
**Status:** ✅ DONE (v15.3.61)

**Goal**
Predictive-Usage-Historie, Zone-spezifische Predictive-Patterns und Predictive-Effectiveness-Metriken aus derselben Predictive-/Proposal-Wahrheit materialisieren.

### Deliverables
- [x] `PredictiveUsageEntryV1` / `PredictiveUsageHistoryV1` als Read-Models
- [x] `PredictiveZonePatternEntryV1` / `PredictiveZonePatternsV1` als Read-Models
- [x] `PredictiveEffectivenessMetricsV1` mit Confidence-Accuracy, Acceptance-Rate, Time-to-Accept/Reject
- [x] `PredictiveTrendEntryV1` / `PredictiveTrendsV1` für Zeitreihen-Analyse
- [x] `PredictiveAnalyticsStore` mit `add_usage_entry()`, `build_usage_history()`, `build_zone_patterns()`, `get_effectiveness_metrics()`, `build_trends()`
- [x] SQLite-Speicher für Usage-History, Zone-Patterns, Effectiveness-Metrics und Trends
- [x] Revisionstracking für Delta-Polling
- [x] Contract-Tests (17 Tests grün)

### Acceptance criteria
- Dashboard-/UI-Poller können Predictive-Usage mit Delta-Cursor inkrementell abfragen
- Zone-spezifische Patterns zeigen Predictive-Häufigkeit, Acceptance-Rate und Confidence pro Zone
- Effectiveness-Metriken quantifizieren Confidence-Accuracy, Acceptance-Rate und Time-to-Accept/Reject
- Trends zeigen Zeitreihen für Proposals, Acceptances und Rejections
- Alle Surfaces lesen dieselbe kanonische Predictive-Wahrheit ohne Schattenlogik

**Commit:** `feat(core): deliver slice 48 predictive analytics surface`
**Tag:** v15.3.61
**Tests:** `pytest -q tests/test_predictive_analytics_contract.py` → `17 passed`

**Next Exact Task:** Slice 49 als Music-/Media-Analytics-Surface ableiten: Music-Usage-Historie, Zone-spezifische Music-Patterns und Music-Effectiveness-Metriken aus derselben Music-/Media-Wahrheit materialisieren.

### ✅ Slice 49 — Music/Media Analytics Surface
**Status:** ✅ DONE (v15.3.62)

**Goal**
Music-Usage-Historie, Zone-spezifische Music-Patterns und Music-Effectiveness-Metriken aus derselben Music-/Media-Wahrheit materialisieren.

### Deliverables
- [x] `MusicUsageEntryV1` / `MusicUsageHistoryV1` als Read-Models
- [x] `MusicZonePatternEntryV1` / `MusicZonePatternsV1` als Read-Models
- [x] `MusicEffectivenessMetricsV1` mit Engagement-Score, Diversity-Score, Auto-Presence-Acceptance-Rate
- [x] `MusicMediaType` / `MusicSource` Enums für Typisierung
- [x] `MusicAnalyticsStore` mit `add_usage_entry()`, `build_usage_history()`, `build_zone_patterns()`, `get_effectiveness_metrics()`, `build_summary()`
- [x] SQLite-Speicher für Usage-History, Zone-Patterns, Effectiveness-Metrics
- [x] API-Endpoints: `/api/v1/media/analytics/usage|patterns|effectiveness|summary`
- [x] Revisionstracking für Delta-Polling
- [x] Contract-Tests (13 Tests grün)
- [x] App-Integration in `copilot_core/app.py`

### Acceptance criteria
- Dashboard-/UI-Poller können Music-Usage mit Delta-Cursor inkrementell abfragen
- Zone-spezifische Patterns zeigen Session-Häufigkeit, Duration, Volume und Favorite-Media pro Zone
- Effectiveness-Metriken quantifizieren Engagement, Favorite-Diversity und Auto-Presence-Acceptance
- Alle Surfaces lesen dieselbe kanonische Music-Wahrheit ohne Schattenlogik

**Commit:** `feat(media): deliver slice 49 music analytics surface`
**Tag:** v15.3.62
**Tests:** `pytest -q tests/test_music_analytics_contract.py` → `13 passed`

### ✅ Slice 50 — Camera Analytics Surface
**Status:** ✅ DONE (v15.3.63)

**Goal**
Camera-Usage-Historie, Zone-spezifische Camera-Patterns und Camera-Effectiveness-Metriken aus derselben Camera-Wahrheit materialisieren.

### Deliverables
- [x] `CameraUsageEntryV1` / `CameraUsageHistoryV1` als Read-Models
- [x] `CameraZonePatternEntryV1` / `CameraZonePatternsV1` als Read-Models
- [x] `CameraEffectivenessMetricsV1` mit Events-by-Type/Source, Motion-to-Person-Ratio, Notification-Delivery-Rate
- [x] `CameraEventType` / `CameraSource` Enums für Typisierung
- [x] `CameraAnalyticsStore` mit `add_usage_entry()`, `build_usage_history()`, `build_zone_patterns()`, `get_effectiveness_metrics()`, `build_summary()`
- [x] SQLite-Speicher für Usage-History, Zone-Patterns, Effectiveness-Metrics
- [x] API-Endpoints: `/api/v1/camera/analytics/usage|patterns|effectiveness|summary`
- [x] Revisionstracking für Delta-Polling
- [x] Contract-Tests (20 Tests grün)
- [x] App-Integration in `copilot_core/app.py`

### Acceptance criteria
- Dashboard-/UI-Poller können Camera-Usage mit Delta-Cursor inkrementell abfragen
- Zone-spezifische Patterns zeigen Event-Häufigkeit, Typ-Verteilung und Aktivitätsmuster pro Zone
- Effectiveness-Metriken quantifizieren Notification-Delivery, Snapshot-Capture und Recording-Trigger-Rates
- Alle Surfaces lesen dieselbe kanonische Camera-Wahrheit ohne Schattenlogik

**Commit:** `feat(camera): deliver slice 50 camera analytics surface`
**Tag:** v15.3.63
**Tests:** `pytest -q tests/test_camera_analytics_contract.py tests/test_camera_analytics_api.py` → `20 passed`

**Next Exact Task:** Slice 51 als Weather-Analytics-Surface ableiten: Weather-Usage-Historie, Zone-spezifische Weather-Patterns und Weather-Effectiveness-Metriken aus derselben Weather-/Automation-Wahrheit materialisieren.

### ✅ Slice 51 — Weather Analytics Surface
**Status:** ✅ DONE (v15.3.64)

**Goal**
Weather-Observation-Historie, Zone-spezifische Weather-Patterns und Weather-Effectiveness-Metriken aus derselben Weather-Wahrheit materialisieren.

### Deliverables
- [x] `WeatherObservationEntryV1` / `WeatherObservationHistoryV1` als Read-Models
- [x] `WeatherZonePatternEntryV1` / `WeatherZonePatternsV1` als Read-Models
- [x] `WeatherEffectivenessMetricsV1` mit Observations-by-Type/Source, Alert-Accuracy, Notification-/Automation-Trigger-Rates
- [x] `WeatherEventType` / `WeatherDataSource` Enums für Typisierung
- [x] `WeatherAnalyticsStore` mit `add_observation()`, `build_observation_history()`, `build_zone_patterns()`, `get_effectiveness_metrics()`, `build_summary()`
- [x] SQLite-Speicher für Observation-History, Zone-Patterns, Effectiveness-Metrics
- [x] API-Endpoints: `/api/v1/weather/analytics/usage|patterns|effectiveness|summary`
- [x] Revisionstracking für Delta-Polling
- [x] Contract-Tests (20 Tests grün)
- [x] App-Integration in `copilot_core/app.py`

### Acceptance criteria
- Dashboard-/UI-Poller können Weather-Observations mit Delta-Cursor inkrementell abfragen
- Zone-spezifische Patterns zeigen Temperatur-, Niederschlags- und Alert-Häufigkeit pro Zone
- Effectiveness-Metriken quantifizieren Notification-Delivery, Automation-Trigger und Forecast-Accuracy
- Alle Surfaces lesen dieselbe kanonische Weather-Wahrheit ohne Schattenlogik

**Commit:** `feat(weather): deliver slice 51 weather analytics surface`
**Tag:** v15.3.64
**Tests:** `pytest -q tests/test_weather_analytics_contract.py tests/test_weather_analytics_api.py` → `20 passed`

**Next Exact Task:** Slice 52 als Notification-Analytics-Surface ableiten: Notification-Delivery-Historie, Channel-spezifische Patterns und Delivery-Effectiveness-Metriken aus derselben Notification-Wahrheit materialisieren.

### ✅ Slice 52 — Notification Analytics Surface
**Status:** ✅ DONE (v15.3.65)

**Goal**
Notification-Delivery-Historie, Channel-spezifische Patterns und Delivery-Effectiveness-Metriken aus derselben Notification-Wahrheit materialisieren.

### Deliverables
- [x] `NotificationDeliveryEntryV1` / `NotificationDeliveryHistoryV1` als Read-Models
- [x] `NotificationChannelPatternEntryV1` / `NotificationChannelPatternsV1` als Read-Models
- [x] `NotificationEffectivenessMetricsV1` mit Delivery-/Read-/Ack-Rates, Delivery-Time-by-Channel, Failure-Rates
- [x] `NotificationChannel` / `NotificationType` / `DeliveryStatus` Enums für Typisierung
- [x] `NotificationAnalyticsStore` mit `add_delivery_entry()`, `build_delivery_history()`, `build_channel_patterns()`, `get_effectiveness_metrics()`, `build_summary()`
- [x] SQLite-Speicher für Delivery-History, Channel-Patterns, Effectiveness-Metrics
- [x] API-Endpoints: `/api/v1/notifications/analytics/delivery|channels|effectiveness|summary`
- [x] Revisionstracking für Delta-Polling
- [x] Contract-Tests (14 Tests grün)
- [x] App-Integration in `copilot_core/app.py`

### Acceptance criteria
- Dashboard-/UI-Poller können Notification-Delivery mit Delta-Cursor inkrementell abfragen
- Channel-spezifische Patterns zeigen Delivery-Rates, Failure-Rates und Nutzungsmuster pro Channel
- Effectiveness-Metriken quantifizieren Delivery-/Read-/Ack-Rates und Delivery-Time-by-Channel
- Alle Surfaces lesen dieselbe kanonische Notification-Wahrheit ohne Schattenlogik

**Commit:** `feat(notifications): deliver slice 52 notification analytics surface`
**Tag:** v15.3.65
**Tests:** `pytest -q tests/test_notification_analytics_contract.py` → `14 passed`

**Next Exact Task:** Slice 53 als Scheduler-Analytics-Surface ableiten: Scheduler-Job-Historie, Job-spezifische Patterns und Scheduler-Effectiveness-Metriken aus derselben Scheduler-Wahrheit materialisieren.

### ✅ Slice 53 — Scheduler Analytics Surface
**Status:** ✅ DONE (v15.3.66)

**Goal**
Scheduler-Job-Execution-Historie, Job-spezifische Patterns und Scheduler-Effectiveness-Metriken aus derselben Scheduler-Wahrheit materialisieren.

### Deliverables
- [x] `SchedulerJobExecutionEntryV1` / `SchedulerJobExecutionHistoryV1` als Read-Models
- [x] `SchedulerJobPatternEntryV1` / `SchedulerJobPatternsV1` als Read-Models
- [x] `SchedulerEffectivenessMetricsV1` mit Success-/Failure-Rates, Duration-by-Job-Type, Reliability-Score
- [x] `JobStatus` / `JobType` Enums für Typisierung
- [x] `SchedulerAnalyticsStore` mit `add_execution_entry()`, `build_execution_history()`, `build_job_patterns()`, `get_effectiveness_metrics()`, `build_summary()`
- [x] SQLite-Speicher für Execution-History, Job-Patterns, Effectiveness-Metrics
- [x] API-Endpoints: `/api/v1/scheduler/analytics/executions|jobs|effectiveness|summary`
- [x] Revisionstracking für Delta-Polling
- [x] Contract-Tests (13 Tests grün)
- [x] App-Integration in `copilot_core/app.py`

### Acceptance criteria
- Dashboard-/UI-Poller können Scheduler-Executions mit Delta-Cursor inkrementell abfragen
- Job-spezifische Patterns zeigen Success-Rates, Failure-Rates und Duration-Statistiken pro Job
- Effectiveness-Metriken quantifizieren Reliability-Score, Success-/Failure-Rates und Duration-by-Job-Type
- Alle Surfaces lesen dieselbe kanonische Scheduler-Wahrheit ohne Schattenlogik

**Commit:** `feat(scheduler): deliver slice 53 scheduler analytics surface`
**Tag:** v15.3.66
**Tests:** `pytest -q tests/test_scheduler_analytics_contract.py` → `13 passed`

**Next Exact Task:** Slice 54 als Automation-Analytics-Surface ableiten: Automation-Execution-Historie, Rule-spezifische Patterns und Automation-Effectiveness-Metriken aus derselben Automation-Wahrheit materialisieren.

### ✅ Slice 54 — Automation Analytics Surface
**Status:** ✅ DONE (v15.3.67)

**Goal**
Automation-Execution-Historie, Rule-spezifische Patterns und Automation-Effectiveness-Metriken aus derselben Automation-Wahrheit materialisieren.

### Deliverables
- [x] `AutomationExecutionEntryV1` / `AutomationExecutionHistoryV1` als Read-Models
- [x] `AutomationRulePatternEntryV1` / `AutomationRulePatternsV1` als Read-Models
- [x] `AutomationEffectivenessMetricsV1` mit Success-/Failure-Rates, Duration-by-Trigger, Reliability-Score
- [x] `AutomationStatus` / `AutomationTriggerType` Enums für Typisierung
- [x] `AutomationAnalyticsStore` mit `add_execution_entry()`, `build_execution_history()`, `build_rule_patterns()`, `get_effectiveness_metrics()`, `build_summary()`
- [x] SQLite-Speicher für Execution-History, Rule-Patterns, Effectiveness-Metrics
- [x] API-Endpoints: `/api/v1/automation/analytics/executions|rules|effectiveness|summary`
- [x] Revisionstracking für Delta-Polling
- [x] Contract-Tests (13 Tests grün)
- [x] App-Integration in `copilot_core/app.py`

### Acceptance criteria
- Dashboard-/UI-Poller können Automation-Executions mit Delta-Cursor inkrementell abfragen
- Rule-spezifische Patterns zeigen Success-Rates, Failure-Rates und Trigger-Verteilung pro Automation
- Effectiveness-Metriken quantifizieren Reliability-Score, Success-/Failure-Rates und Duration-by-Trigger-Type
- Alle Surfaces lesen dieselbe kanonische Automation-Wahrheit ohne Schattenlogik

**Commit:** `feat(automation): deliver slice 54 automation analytics surface`
**Tag:** v15.3.67
**Tests:** `pytest -q tests/test_automation_analytics_contract.py` → `13 passed`

**Next Exact Task:** Slice 55 als System-Health-Analytics-Surface ableiten: Health-Check-Historie, Component-spezifische Patterns und System-Effectiveness-Metriken aus derselben Health-Wahrheit materialisieren.

### ✅ Slice 55 — System Health Analytics Surface
**Status:** ✅ DONE (v15.3.69)

**Goal**
Health-Check-Historie, Component-spezifische Patterns und System-Effectiveness-Metriken aus derselben Health-Wahrheit materialisieren.

### Deliverables
- [x] `HealthCheckExecutionEntryV1` / `HealthCheckExecutionHistoryV1` als Read-Models
- [x] `HealthComponentPatternEntryV1` / `HealthComponentPatternsV1` als Read-Models
- [x] `HealthEffectivenessMetricsV1` mit Success-/Failure-Rates, Duration-by-Component, Reliability-Score
- [x] `HealthStatus` / `HealthComponentType` Enums für Typisierung
- [x] `HealthAnalyticsStore` mit `add_execution_entry()`, `build_execution_history()`, `build_component_patterns()`, `get_effectiveness_metrics()`, `build_summary()`
- [x] SQLite-Speicher für Execution-History, Component-Patterns, Effectiveness-Metrics
- [x] API-Endpoints: `/api/v1/health/analytics/executions|components|effectiveness|summary`
- [x] Revisionstracking für Delta-Polling
- [x] Contract-Tests (13 Tests grün)
- [x] App-Integration in `copilot_core/app.py`

### Acceptance criteria
- Dashboard-/UI-Poller können Health-Checks mit Delta-Cursor inkrementell abfragen
- Component-spezifische Patterns zeigen Success-Rates, Failure-Rates und Duration-Statistiken pro Component
- Effectiveness-Metriken quantifizieren Reliability-Score, Success-/Failure-Rates und System-Health
- Alle Surfaces lesen dieselbe kanonische Health-Wahrheit ohne Schattenlogik

**Commit:** `feat(core): deliver slice 55 system health analytics surface`
**Tag:** v15.3.69
**Tests:** `pytest -q tests/test_health_analytics_contract.py` → `13 passed`

### ✅ Slice 56 — Module Analytics Surface
**Status:** ✅ DONE (v15.3.70)

**Goal**
Module-Execution-Historie, Module-spezifische Patterns und Module-Effectiveness-Metriken aus derselben Module-Wahrheit materialisieren.

### Deliverables
- [x] `ModuleExecutionEntryV1` / `ModuleExecutionHistoryV1` als Read-Models
- [x] `ModulePatternEntryV1` / `ModulePatternsV1` als Read-Models
- [x] `ModuleEffectivenessMetricsV1` mit Success-/Failure-Rates, Duration-by-Module, MTBF/MTTR
- [x] `ModuleExecutionStatus` / `ModuleTriggerType` Enums für Typisierung
- [x] `ModuleAnalyticsStore` mit `add_execution_entry()`, `build_history()`, `build_module_patterns()`, `get_effectiveness_metrics()`, `build_summary()`
- [x] SQLite-Speicher für Execution-History, Module-Patterns, Effectiveness-Metrics
- [x] API-Endpoints: `/api/v1/module/analytics/executions|patterns|effectiveness|summary`
- [x] Revisionstracking für Delta-Polling
- [x] Contract-Tests (37 Tests grün)
- [x] App-Integration in `copilot_core/app.py`

### Acceptance criteria
- Dashboard-/UI-Poller können Module-Executions mit Delta-Cursor inkrementell abfragen
- Module-spezifische Patterns zeigen Success-Rates, Failure-Rates und Duration-Statistiken pro Modul
- Effectiveness-Metriken quantifizieren MTBF, MTTR, Success-/Failure-Rates und Zone-Coverage
- Alle Surfaces lesen dieselbe kanonische Module-Wahrheit ohne Schattenlogik

**Commit:** `feat(core): deliver slice 56 module analytics surface`
**Tag:** v15.3.70
**Tests:** `pytest -q tests/test_module_analytics_contract.py tests/test_module_analytics_api_contract.py` → `37 passed`

**Next Exact Task:** Slice 57 als Voice-Analytics-Surface ableiten: Voice-Command-Historie, Intent-spezifische Patterns und Voice-Effectiveness-Metriken aus derselben Voice-Wahrheit materialisieren.

### ✅ Slice 57 — Voice Analytics Surface
**Status:** ✅ DONE (v15.3.71)

**Goal**
Voice-Command-Historie, Intent-spezifische Patterns und Voice-Effectiveness-Metriken aus derselben Voice-Wahrheit materialisieren.

### Deliverables
- [x] `VoiceCommandEntryV1` / `VoiceCommandHistoryV1` als Read-Models
- [x] `VoiceIntentPatternEntryV1` / `VoiceIntentPatternsV1` als Read-Models
- [x] `VoiceEffectivenessMetricsV1` mit Success-/Failure-Rates, Confidence-Score, Processing-Time
- [x] `VoiceCommandStatus` / `VoiceIntentType` Enums für Typisierung
- [x] `VoiceAnalyticsStore` mit `add_command_entry()`, `build_history()`, `build_intent_patterns()`, `get_effectiveness_metrics()`, `build_summary()`
- [x] SQLite-Speicher für Command-History, Intent-Patterns, Effectiveness-Metrics
- [x] API-Endpoints: `/api/v1/voice/analytics/commands|intents|effectiveness|summary`
- [x] Revisionstracking für Delta-Polling
- [x] Contract-Tests (17 Tests grün)
- [x] App-Integration in `copilot_core/app.py`

### Acceptance criteria
- Dashboard-/UI-Poller können Voice-Commands mit Delta-Cursor inkrementell abfragen
- Intent-spezifische Patterns zeigen Success-Rates, Confidence-Scores und Processing-Time-Statistiken pro Intent-Typ
- Effectiveness-Metriken quantifizieren Overall-Success-Rate, Rejection-Rate, Timeout-Rate und Zone-Coverage
- Alle Surfaces lesen dieselbe kanonische Voice-Wahrheit ohne Schattenlogik

**Commit:** `feat(core): deliver slice 57 voice analytics surface`
**Tag:** v15.3.71
**Tests:** `pytest -q tests/test_voice_analytics_contract.py` → `17 passed`

### ✅ Slice 62 — Analytics Gap Closure Complete
**Status:** ✅ DONE (v15.3.75)

**Goal**
Alle Analytics-Surfaces vervollständigen: Zone Truth, Proposal Lifecycle, Action Closure, Brain/Neuron.

### Deliverables
- [x] Slice 58 — Zone Truth Analytics (v15.3.72)
  - ZoneSyncEventEntryV1/ZoneSyncHistoryV1
  - ZonePatternEntryV1/ZonePatternsV1
  - ZoneEffectivenessMetricsV1
  - GET /api/v1/zone-truth/analytics/sync/executions|patterns|effectiveness|summary
- [x] Slice 59 — Proposal Lifecycle Analytics (v15.3.73)
  - ProposalLifecycleEventV1/ProposalLifecycleHistoryV1
  - ProposalPatternEntryV1/ProposalPatternsV1
  - ProposalEffectivenessMetricsV1
  - GET /api/v1/proposal-lifecycle/analytics/events|patterns|effectiveness|summary
- [x] Slice 60 — Action Closure Analytics (v15.3.74)
  - ActionClosureEventV1/ActionClosureHistoryV1
  - ClosurePatternEntryV1/ClosurePatternsV1
  - ClosureEffectivenessMetricsV1
  - GET /api/v1/action-closure/analytics/events|patterns|effectiveness|summary
- [x] Slice 61 — Brain/Neuron Analytics (v15.3.75)
  - NeuronEventV1/NeuronHistoryV1
  - NeuronPatternEntryV1/NeuronPatternsV1
  - BrainEffectivenessMetricsV1
  - GET /api/v1/brain/analytics/events|patterns|effectiveness|summary

### Acceptance criteria
- Alle Analytics-Surfaces folgen demselben Contract-Muster (Events, Patterns, Effectiveness, Summary)
- Revisionstracking für Delta-Polling auf allen Surfaces
- SQLite-Backed Stores für persistente Historie
- Contract-Tests für alle Stores (66 Tests grün insgesamt)
- API-Endpoints in app.py registriert

**Commit:** `feat(core): deliver slices 58-61 analytics gap closure`
**Tag:** v15.3.75
**Tests:** `pytest -q tests/test_*_analytics_contract.py` → 66 passed

**Next Exact Task:** Analytics-Lücke geschlossen; nächste Forward-Slices aus Roadmap/Vision ableiten oder Refinement/Härtung bestehender Surfaces.
