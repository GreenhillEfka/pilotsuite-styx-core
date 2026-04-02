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
