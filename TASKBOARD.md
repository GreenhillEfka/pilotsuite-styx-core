# PilotSuite Core Taskboard

## Directive (2026-03-22)
**Owner:** PilotClaw  
**Scope:** `pilotsuite-styx-core`  
**Authority:** PilotClaw has the last word for Core development.

---

## Status summary

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

## Ready signal for next implementation agent
Concept work is complete.

**Do next, in order:**
1. **Slice 1 — canonical ingest lane**
2. **Slice 2 — zone truth layer + canonical topology sync**
3. **Slice 3 — first-class module model + end-to-end wiring**
4. **Slice 5 — brain growth unification**

Those slices remove the biggest semantic ambiguity and make the rest of the product architecture honest.