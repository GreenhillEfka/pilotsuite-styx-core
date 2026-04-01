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

## Next execution slices

## Slice 1 — Canonical ingest lane
**Priority:** P0  
**Status:** ready

**Goal**
Make one event ingest path authoritative in both code and runtime.

### Deliverables
- [ ] choose the authoritative `POST /api/v1/events` implementation
- [ ] retire `api/v1/events.py` as public ingress or reduce it to explicit compatibility adapter behavior
- [ ] standardize on one canonical store (`ingest/event_store.py`) and one post-ingest flow (`EventProcessor`)
- [ ] align `app.py` test/runtime semantics with production `core_setup.py` behavior
- [ ] add route-level tests for the real registered app, not just nested blueprint assumptions

### Acceptance criteria
- one authoritative ingest route,
- one authoritative event store implementation,
- one authoritative path into Brain Graph / mining / module routing,
- no silent divergence between test app and production wiring.

---

## Slice 2 — Zone truth layer + canonical topology sync
**Priority:** P0  
**Status:** ready

**Goal**
Create one durable Core-owned topology/truth store for zone instances.

### Deliverables
- [ ] typed `ZoneDefinitionSyncV1` model and storage
- [ ] choose one canonical topology sync endpoint/path
- [ ] store provenance, revision, and freshness metadata
- [ ] separate zone archetype from zone instance explicitly
- [ ] replace ad hoc truth like `cfg._ha_entities` as the actual source of truth

### Acceptance criteria
- synced zone definitions are queryable from one store,
- dashboard, habitus, autonomy, modules, and chat context can all read the same zone truth,
- sync docs and sync runtime path no longer disagree.

---

## Slice 3 — First-class module model + end-to-end wiring
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

**Next Exact Task:** **Slice 19 Candidate**: Closure-Signale in Predictive-/Habitus-/Multi-Zone-Lern- und Priorisierungslogik rueckkoppeln, damit accept/reject/execution-outcomes nicht nur erklaert, sondern fuer kuenftige Vorschlagsqualitaet systematisch verwertet werden.

**After Refinement:** Root-Contract-Surface ist grün; Slice 13+ wieder als reguläre Forward-Slices aufnehmen

**Core is now stable enough for HA/HACS lane reactivation.**
