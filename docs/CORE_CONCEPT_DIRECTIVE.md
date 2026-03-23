# PilotSuite Core Concept Directive

**Date:** 2026-03-22  
**Owner:** PilotClaw  
**Scope:** `pilotsuite-styx-core`  
**Authority:** This document defines the durable Core concept, responsibility boundary, and development direction for current and future work.

---

## 1. Executive decision

**PilotSuite Core is the semantic brain of PilotSuite: truth engine, module runtime, policy engine, explanation engine, and conversational reasoning layer.**

That means Core is not just a backend API and not just a mining engine. It is the place where:
- raw HA inputs become normalized semantic inputs,
- those inputs are transferred into the growing brain representation,
- Core modules consume prepared signals and zone truth,
- Habitus/mood/neuron logic derive meaning and proposals,
- governance decides what is only suggested vs what is execution-ready,
- dashboards and chat consume stable read models instead of rebuilding semantics.

That does **not** mean Core replaces Home Assistant as the raw runtime source of device state.
The durable split is:

- **Home Assistant / HACS** = physical system shell
  - discovers devices/entities/areas,
  - observes raw HA state and events,
  - executes HA service calls,
  - renders HA-native UX,
  - materializes HA-facing entities/cards/controls.
- **PilotSuite Core** = semantic brain
  - normalizes inputs,
  - owns zone/entity/module meaning,
  - turns events/entities/sensors into brain-relevant semantic signals,
  - grows the brain representation from those signals,
  - runs modules, neurons, mood, habitus, proposals, and RAG chat,
  - emits explainable read models and action-intent contracts.

So the precise rule is:

- **HA owns raw home runtime truth.**
- **Core owns normalized semantic truth and reasoning.**

This is the only boundary that fits the repo’s docs, current wiring, and clarified product intent.

---

## 2. Evidence from the current repo

This directive is evidence-driven from current docs and code.

### 2.1 Repo-level intent already points to a split backend brain

Evidence:
- `README.md`
- `CLAUDE.md`
- `docs/ARCHITECTURE_CONCEPT.md`
- `docs/ARCHITECTURE.md`
- `docs/MODULE_INVENTORY.md`

What they say together:
- Core is the backend add-on for Brain Graph, Mood, Habitus, Neurons, Zone Automation, API, and chat.
- HA integration is the counterpart shell for entities, cards, dashboard projection, and runtime integration.
- `docs/ARCHITECTURE_CONCEPT.md` explicitly recommends keeping **two projects** because backend logic and HA integration have different responsibilities.
- `README.md` explicitly says: **“Dieses Repo ist nicht die HACS-Integration.”**

### 2.2 The runtime currently has two entry-point realities

Evidence:
- `copilot_core/rootfs/usr/src/app/copilot_core/app.py`
- `copilot_core/rootfs/usr/src/app/copilot_core/api/v1/blueprint.py`
- `copilot_core/rootfs/usr/src/app/copilot_core/core_setup.py`
- `CLAUDE.md`

Current reality:
- `app.py` registers the nested `api_v1` blueprint used by tests and lightweight app creation.
- `core_setup.py` registers the production route set flat on the Flask app.
- `CLAUDE.md` correctly warns that `app.py` and production do **not** expose the same route surface.

**Directive consequence:** Core needs conceptually single responsibilities even while the repo still has dual wiring paths.

### 2.3 Event ingest is the clearest architectural split still live in code

Evidence:
- `docs/HA_CORE_INGEST_CONTRACT.md`
- `copilot_core/api/v1/events_ingest.py`
- `copilot_core/ingest/event_store.py`
- `copilot_core/ingest/event_processor.py`
- `copilot_core/api/v1/events.py`
- `copilot_core/storage/events.py`
- `copilot_core/core_setup.py`
- `copilot_core/api/v1/blueprint.py`

Current reality:
- `events_ingest.py` already defines the canonical contract at `POST /api/v1/events`.
- `schemas.py` and `ingest/event_store.py` already normalize legacy and canonical HA envelopes into one shape.
- `EventProcessor` already exists as the post-ingest pipeline into Brain Graph and auto-mining.
- But `events.py` is still a second ingest surface with a **different** store implementation: `copilot_core.storage.events.EventStore`.
- Production registration in `core_setup.py` exposes both ingest lanes in different ways.
- Test/runtime registration through `app.py` + `blueprint.py` still centers the legacy `events.py` blueprint.

So this is not just a route naming problem. It is also:
- two ingest implementations,
- two store types,
- two wiring stories.

**Directive consequence:** Core must have one authoritative ingest lane, one authoritative normalized event store, and one authoritative post-ingest pipeline.

### 2.4 Zone truth is still fragmented across archetypes, config, and dashboard assembly

Evidence:
- `docs/ZONE_EDITOR.md`
- `copilot_core/api/v1/zone_automation.py`
- `copilot_core/hub/zone_automation.py`
- `copilot_core/homeassistant/habitus_zones.py`
- `copilot_core/api/v1/habitus_zones.py`
- `copilot_core/api/v1/zone_dashboard.py`
- `copilot_core/rootfs/usr/src/app/docs/ZONE_DASHBOARD.md`

Current reality:
- `homeassistant/habitus_zones.py` defines valuable **zone archetypes** and default module policy.
- `hub/zone_automation.py` separately owns runtime zone configs, entity assignments, tags, roles, and automation state.
- `zone_automation.py` exposes `POST /api/v1/zone-automation/sync-definitions`, but currently stores synced HA topology ad hoc onto config attributes like `cfg._ha_entities`.
- `docs/ZONE_EDITOR.md` documents a different topology sync story under `/api/v1/habitus/zones/sync`.
- `api/v1/habitus_zones.py` exposes archetype/config APIs, not the same live synced topology lane.
- `zone_dashboard.py` still assembles data from `habitus_zones` plus `example_config` enrichment and local mood overrides.

So the repo currently has:
- zone archetypes,
- zone runtime configs,
- zone sync docs,
- zone sync implementation,
- zone dashboard read models,

but **not yet one canonical zone truth layer**.

**Directive consequence:** Core must separate:
- **zone archetype** = policy template,
- **zone instance** = synced real home topology,
- **zone read model** = visualization/product output.

### 2.5 Modules already exist as a real Core layer and must become first-class in the concept

Evidence:
- `docs/MODULE_INVENTORY.md`
- `copilot_core/core_setup.py`
- `copilot_core/hub/licht_module.py`
- `copilot_core/hub/helligkeit_module.py`
- `copilot_core/hub/heiz_module.py`
- `copilot_core/hub/zone_automation.py`
- `copilot_core/api/v1/zone_dashboard.py`

Current reality:
- `core_setup.py` initializes concrete Core module engines, including `hub_licht`, `hub_helligkeit`, `hub_heiz`, `hub_bewegung`, `hub_praesenz`, plus network/HA engines.
- `core_setup.py` also wires these modules into dashboard and module endpoints.
- `licht_module.py`, `helligkeit_module.py`, and `heiz_module.py` are not placeholders; they already contain tracked entities, zone config, summaries, and LLM/dashboard context helpers.
- `zone_dashboard` initialization explicitly consumes basis modules, intelligence engines, and control engines together.
- `zone_automation.py` and `homeassistant/habitus_zones.py` already assume per-zone module applicability and policy.

**Directive consequence:** modules are not a side detail. Core modules must be first-class product/runtime units with:
- identity,
- configuration,
- zone applicability,
- entity membership,
- input contract,
- output/read-model contract,
- governance state,
- execution adapter mapping.

### 2.6 The Home Assistant module in Core already points toward a connection-module role

Evidence:
- `copilot_core/hub/homeassistant_module.py`
- `copilot_core/hub/module_router.py`
- `copilot_core/ingest/event_processor.py`
- `copilot_core/core_setup.py`

Current reality:
- `HomeAssistantModuleEngine` tracks connection status, forwarding, webhook activity, diagnostics, and pipeline health.
- `ModuleRouter` is wired into `EventProcessor` and consumes normalized ingested events before routing relevant state to modules.
- `ModuleRouter` already acts as a bridge from HA-derived state into network modules and uses the HA module engine as part of the routing/diagnostic picture.

**Directive consequence:** the Core-side HA module should be described explicitly as a **connection module**:
- not the owner of semantics,
- but the Core-side adapter that receives HA-origin inputs,
- validates/observes transport health,
- and delivers semantically prepared inputs to the rest of Core.

### 2.7 The brain representation is already split between graph growth and neuron pipeline

Evidence:
- `copilot_core/ingest/event_processor.py`
- `copilot_core/brain_graph/service.py`
- `copilot_core/neurons/manager.py`
- `README.md`
- `CLAUDE.md`

Current reality:
- `EventProcessor` already converts normalized events into Brain Graph node/edge updates.
- `_process_state_change_for_graph()` creates/touches entity and zone nodes and links them.
- `_process_service_call_for_graph()` creates/touches service nodes and links them to target entities.
- `BrainGraphService._infer_triggers()` already infers additional relationships from context parent IDs.
- `NeuronManager` explicitly runs the layered pipeline `HA States → Context Neurons → State Neurons → Mood Neurons → Suggestions`.
- The repo already positions the system as Brain Graph + Neurons + Mood + Habitus, not as isolated services.

**Directive consequence:** the Core concept must explicitly say that incoming entities/events/sensors are semantically transferred into a **growing brain representation**:
- graph-side growth in nodes/edges/causal links,
- neuron-side growth in evaluated context/state/mood relations,
- future tightening of the link between normalized semantic truth and neuron connectivity/read models.

Important precision:
- today the graph clearly grows structurally,
- the neuron system is clearly layered and configurable,
- the repo does **not yet** fully expose one unified “brain growth” surface.

So the concept should promise unification, not falsely claim it is already complete.

### 2.8 Governance is already strong and correctly belongs in Core

Evidence:
- `copilot_core/module_registry.py`
- `copilot_core/autonomy/executor.py`
- `copilot_core/homeassistant/habitus_zones.py`
- `copilot_core/api/v1/habitus.py`

What already exists:
- global and per-zone module states: `active | learning | off`,
- double-safety before auto-apply,
- suggestion-first / explanation-first defaults,
- action policy evaluation in `evaluate_action_policy()`,
- accepted proposals becoming `ProposalIntentV1`, `ActionIntentV1`, and `HabitatModuleCommandV1`.

**Directive consequence:** policy, execution eligibility, and explanation remain Core responsibilities. HA/HACS must not become a second policy engine.

### 2.9 The RAG chat pipeline is already part of the Core product surface

Evidence:
- `copilot_core/api/v1/styx_chat.py`
- `copilot_core/styx/chat_handler.py`
- `copilot_core/api/v1/rag.py`
- `copilot_core/conversation_memory.py`
- `copilot_core/vector_store/store.py`
- `copilot_core/core_setup.py`

Current reality:
- `/api/styx/chat` is a Core endpoint backed by `ChatHandler`.
- `ChatHandler` runs an internal pipeline: query classification → internal RAG search → conversation memory context → live home context → LLM inference.
- `chat_handler.py` explicitly uses internal BM25 + semantic search + RRF fusion.
- `conversation_memory.py` is described as the bridge between chat interactions and the neural pipeline.
- `core_setup.py` initializes `ConversationMemory`, `VectorStore`, and `EmbeddingEngine` as Core services.
- `api/v1/rag.py` exposes first-class RAG search/index/rerank surfaces.

**Directive consequence:** RAG chat is not optional garnish. It is Core’s conversational reasoning surface over semantic truth, memory, and live home context.

### 2.10 Proposal logic is real, but product lifecycle is still split

Evidence:
- `copilot_core/habitus_miner/service.py`
- `copilot_core/habitus_miner/zone_mining.py`
- `copilot_core/candidates/store.py`
- `copilot_core/api/v1/suggestions.py`
- `copilot_core/api/v1/habitus.py`

Current reality:
- Zone mining produces explainable proposals with confidence, lift, evidence, and automation previews.
- `CandidateStore` already models lifecycle states (`pending`, `offered`, `accepted`, `dismissed`, `deferred`).
- `suggestions.py` still exposes a separate suggestions lane with example/fallback behavior.
- `habitus.py` already shapes accepted proposals into action-intent contracts.

**Directive consequence:** Core should expose one proposal lifecycle, not multiple semi-overlapping suggestion surfaces.

---

## 3. Durable responsibility boundary

## 3.1 What permanently belongs in Core

Core owns the following semantic and runtime responsibilities:

### A. Input normalization
- canonical event envelope acceptance,
- topology sync acceptance,
- feedback/approval acceptance,
- conversion from external contracts into internal Core models.

### B. Semantic truth
- normalized event ledger,
- entity snapshots and inferred metadata,
- zone instance topology,
- zone archetype mapping,
- role/tag/category inference,
- module state and provenance,
- evidence and explanation records.

### C. Module runtime
- first-class Core modules with durable IDs,
- per-module config schemas and zone applicability,
- module-level summaries/read models,
- module participation in zone reasoning,
- module input/output contracts,
- module policy state (`active | learning | off`),
- execution adapter targets emitted by Core.

### D. Brain and cognitive reasoning
- Brain Graph,
- semantic transfer from normalized inputs into graph nodes/edges,
- neuron pipeline,
- mood computation,
- habitus mining,
- proposal generation,
- action-intent shaping,
- autonomy eligibility.

### E. Conversational reasoning
- RAG query routing,
- lexical/semantic retrieval and reranking,
- conversation memory,
- prompt context assembly from live home truth,
- explainable chat over Core truth.

### F. Product read models
- zone summary models,
- zone detail models,
- module summary/detail models,
- proposal queue models,
- system summary models,
- diagnostics and freshness views.

### G. Governance
- module states,
- per-zone overrides,
- explanation requirements,
- approval requirements,
- eligibility and blocking reasons,
- behavioral/audit log semantics.

## 3.2 What permanently belongs in HA / HACS

HA/HACS owns the physical/runtime shell:

### A. Raw collection
- HA entity discovery,
- area registry access,
- raw state/event extraction,
- history backfill from HA,
- HA auth/session realities.

### B. Execution adapters
- HA service call execution,
- HA entity creation/materialization,
- HA-native service/data schemas,
- Repairs integration,
- config flows/options flows.

### C. Projection and UX
- Lovelace cards,
- HA entities/sensors/selects/numbers/switches,
- HA dashboard rendering,
- HA-native naming/localization/operator controls.

## 3.3 One-owner rule

The following semantics must have exactly one owner, and that owner is **Core**:
- canonical event meaning after normalization,
- zone type taxonomy,
- role/tag/category taxonomy,
- module identity and applicability semantics,
- policy meaning,
- proposal confidence semantics,
- action-intent state semantics,
- visualization read-model semantics,
- conversational context semantics over Core truth.

HA may mirror, cache, or render those semantics.
HA must not redefine them.

---

## 4. Uniform input model

## 4.1 External ingress contracts

Core should support four external ingress families.

### 1. `HAEventInputV1`
Already materially present in:
- `api/v1/schemas.py`
- `ingest/event_store.py`
- `docs/HA_CORE_INGEST_CONTRACT.md`

This is the time-series/event lane.

### 2. `ZoneDefinitionSyncV1`
The repo needs one canonical topology sync contract for:
- zone id,
- human names,
- zone type hint,
- entity membership,
- role hints,
- metadata,
- source revision,
- synced/provenance timestamps.

Current docs and routes are split between:
- `/api/v1/habitus/zones/sync` in docs,
- `/api/v1/zone-automation/sync-definitions` in code.

**Directive:** choose one canonical sync surface and reduce the other to compatibility/shim behavior.

### 3. `OperatorFeedbackV1`
Feedback and governance inputs should cover:
- accept / reject / snooze,
- explicit Styx instruction,
- policy override changes,
- false-positive annotations,
- module-state changes.

### 4. `ChatQueryInputV1`
Conversational ingress should remain first-class and include:
- user query,
- user/session/conversation context,
- model preference,
- web allowance,
- optional namespace/scope hints for retrieval.

## 4.2 Internal Core models

Core should standardize on three internal model families.

### A. `NeuronInputV1`
This name is already referenced in `homeassistant/habitus_zones.py` and should become real architectural law.

Every reasoning subsystem should consume a normalized signal frame with at least:
- `signal_id`
- `ts`
- `source`
- `kind`
- `entity_id`
- `domain`
- `zone_ids[]`
- `zone_type`
- `old`
- `new`
- `service`
- `trigger`
- `context_id`
- `context_parent_id`
- `context_user_id`
- `classification.role`
- `classification.tags[]`
- `classification.category`
- `classification.module_ids[]`
- `topology_ref`
- `policy_ref`
- `raw_contract_version`

### B. `ZoneSnapshotV1`
Every zone-aware subsystem should consume a normalized topology/policy snapshot with:
- `zone_id`
- `zone_instance_name`
- `zone_type`
- `archetype_ref`
- `entity_ids[]`
- `entity_roles`
- `entity_tags`
- `module_overrides`
- `freshness`
- `provenance`
- `revision`

### C. `ModuleSnapshotV1`
Every first-class Core module should expose/consume a normalized module view with:
- `module_id`
- `module_kind`
- `state`
- `config_schema_ref`
- `zone_applicability`
- `entity_membership`
- `input_requirements`
- `output_capabilities`
- `policy_ref`
- `freshness`
- `summary`

## 4.3 Hard rule

**No downstream Core subsystem should continue parsing raw HA envelope variants after normalization.**

That rule applies to:
- Brain Graph feeding,
- module routing,
- mood,
- habitus mining,
- dashboard assembly,
- autonomy,
- suggestions/proposals,
- chat home-context assembly,
- visualization APIs.

---

## 5. The Core truth layer

Core needs an explicit truth layer between ingress and higher reasoning.

## 5.1 Truth layer responsibilities

### A. Event truth
- deduplicated canonical ledger,
- normalized event storage,
- correlation/context fields,
- ingest health and provenance.

### B. Entity truth
- latest normalized state per entity,
- domain/device metadata,
- inferred role/tags/category,
- zone membership references,
- freshness and health.

### C. Zone truth
- synced zone instances from HA,
- zone type and archetype mapping,
- entity membership by role/tag,
- revisioned topology history,
- explicit provenance and freshness.

### D. Module truth
- canonical module registry and metadata,
- per-zone applicability/config,
- module entity membership,
- module summary state,
- module policy state,
- module execution adapter mapping.

### E. Policy truth
- module registry state,
- per-zone module overrides,
- autonomy mode,
- approval/explanation requirements,
- execution eligibility basis.

### F. Evidence truth
- mined rules,
- proposal evidence,
- confidence breakdowns,
- behavioral log/audit semantics,
- explanation provenance.

### G. Conversational truth
- indexed documents and retrieval stats,
- conversation memory,
- retrieval provenance,
- live home context summary blocks,
- chat-useful explanation fragments.

## 5.2 Truth ownership nuance

To stay precise:
- HA is authoritative for raw device registry and raw device state.
- Core is authoritative for **normalized semantic interpretation** of those inputs.

That means Core should not pretend to own the Home Assistant registry itself.
It should own the normalized model built from it.

## 5.3 Current gap to close

Today, the truth layer is implied, not explicit.
That is why the repo currently drifts between:
- archetype catalogs,
- runtime configs,
- example data,
- dashboard assembly,
- sync docs,
- sync endpoints,
- module summaries,
- chat context assembly.

**Directive:** create a first-class truth layer and make all zone-aware, module-aware, and chat-aware features read from it.

---

## 6. Modules are first-class Core units

## 6.1 What a Core module is

A Core module is not just a code package. It is a durable semantic/runtime unit that:
- consumes prepared Core inputs,
- operates on zone/entity/module truth,
- exposes config and summary state,
- participates in policy,
- emits suggestions, state, or execution-ready commands.

Examples already present in repo/code:
- `hub_licht`
- `hub_helligkeit`
- `hub_heiz`
- `hub_bewegung`
- `hub_praesenz`
- `zone_automation`
- `hub_media`
- `hub_energy`
- `hub_scenes`
- `ha_module_engine`

## 6.2 Modules and Habitus zones

For Habitus zones, module participation must be explicit.
A zone is not only:
- a name,
- a type,
- a bag of entities.

A zone must also say:
- which modules are applicable,
- which modules are active/learning/off,
- which entities belong to which module view,
- what each module needs as input,
- what each module can emit for that zone.

This follows directly from existing code:
- per-zone module policy in `homeassistant/habitus_zones.py`,
- per-zone config and module APIs in `zone_automation.py`,
- module summaries in module engines,
- dashboard composition in `core_setup.py`.

## 6.3 Existing modules are a wiring problem, not a blank-sheet problem

The concept must reflect the real status:
- light, brightness, heating, movement, presence, music/media, scenes, energy, and network/HA modules already exist in parts,
- the main product need is not “invent modules later”,
- it is **correct, align, and wire them end-to-end through one truth + module + policy model**.

So future work should prefer:
- consolidating semantics,
- aligning module contracts,
- wiring real inputs and read models,
- reducing duplicated derivation,

instead of introducing parallel module abstractions unnecessarily.

---

## 7. The Home Assistant module inside Core

## 7.1 Durable role

The Core-side Home Assistant module should be treated as a **connection module**.

Its job is to:
- represent HA connectivity and transport health inside Core,
- receive and monitor forwarded HA-origin inputs,
- expose forwarding and diagnostics status,
- hand semantically prepared inputs to the rest of Core.

It is **not** the semantic owner of the home model.
It is the Core-side connection and preparation layer.

## 7.2 Input-preparation responsibility

The clarified product intent is:
- raw HA payloads arrive from HA/HACS,
- Core normalizes them,
- the Core HA connection module participates in delivering prepared inputs onward,
- downstream modules/neurons/reasoners consume the prepared form, not HA’s raw transport form.

That matches the current direction seen in:
- `homeassistant_module.py` for connection/diagnostics state,
- `module_router.py` for event/state routing,
- `event_processor.py` for normalized ingest and downstream processing.

---

## 8. Brain representation and semantic transfer

## 8.1 Durable concept

Core must explicitly model the system as a **growing brain representation** built from semantic transfer of incoming sensors, events, entities, zones, services, and conversational traces.

This brain representation has two coupled layers:

### A. Graph layer
- entities become nodes,
- zones become nodes,
- services become nodes,
- relationships become edges,
- repeated co-occurrence and causality strengthen links,
- inferred triggers add new structure.

### B. Neuron layer
- normalized signals feed context neurons,
- smoothed state neurons derive higher-order state,
- mood neurons aggregate into actionable emotional/household state,
- suggestions emerge from this layered evaluation.

## 8.2 Evidence-based phrasing

What is safe to say today:
- the graph grows structurally via `touch_node()`, `touch_edge()`, and trigger inference,
- the neuron system already exists as a layered evaluation pipeline,
- the repo already treats chat/mood/habitus/brain as connected subsystems.

What is **not** yet fully true:
- one explicit unified public model tying graph growth, neuron connectivity, module truth, and proposal reasoning into one visible “brain growth” contract.

**Directive:** make that unification part of the roadmap.

## 8.3 Semantic transfer rule

Every normalized input should be capable of transferring into brain-relevant state in four directions:
- truth update,
- graph update,
- neuron input update,
- module-relevant update.

This is the architectural bridge between ingest and intelligence.

---

## 9. Normalization, categorization, and zone semantics

## 9.1 Normalization

Core owns canonical normalization of:
- `service_call -> call_service`,
- `home_assistant -> ha`,
- `zone_id -> zone_ids[]`,
- legacy `attributes.*` into structured `old/new/service/context`,
- convenience fields for downstream reasoning.

This is already partially implemented in:
- `api/v1/schemas.py`
- `ingest/event_store.py`

## 9.2 Categorization

Core must become the single classification authority for:
- domain,
- device class,
- zone type,
- entity role,
- tags,
- module bucket,
- proposal type,
- risk class.

Current seeds are split across:
- `hub/zone_automation.py` (`ENTITY_ROLES`, `TAG_DEFINITIONS`, role/tag detection),
- `homeassistant/habitus_zones.py` (zone archetypes, module defaults, policy),
- `habitus_miner/zone_mining.py` (proposal typing and semantic bucketing).

**Directive:** consolidate these into one canonical classification layer, even if compatibility adapters remain temporarily.

## 9.3 Zone archetype vs zone instance

This distinction is durable and non-optional.

### Zone archetype
Examples:
- `living`
- `kitchen`
- `bath`
- `office`

Archetypes define:
- default module policy,
- default privacy posture,
- default suggestion/execution stance,
- expected signal families,
- likely module applicability.

### Zone instance
Examples:
- `zone:wohnzimmer`
- `zone:kueche`
- `zone:bad`

Instances carry:
- actual synced entity membership,
- live freshness/provenance,
- real policy overrides,
- real module applicability/config,
- real dashboard state.

**Directive:** archetypes stay in Core as policy templates; instances come from synced truth.

---

## 10. Habitus, proposals, and action intents

## 10.1 What Habitus is for

Habitus is the Core layer that turns observed repeated behavior into:
- explainable correlations,
- zone-aware and module-aware automation proposals,
- policy-scoped action intents.

It is not just a mining utility.
It is the bridge from observation to governed automation.

## 10.2 Lifecycle Core must own

The durable lifecycle is:

`observed -> normalized -> categorized -> transferred into truth/brain/module context -> mined -> proposed -> offered -> accepted/rejected/deferred -> action_intent -> executed/skipped/blocked`

## 10.3 Durable contracts

The following contracts should become first-class Core outputs:
- `ProposalIntentV1`
- `ActionIntentV1`
- `HabitatModuleCommandV1`
- behavioral log / execution result view

`api/v1/habitus.py` already points in the right direction and should be treated as the nucleus of the unified lifecycle.

## 10.4 Split to remove

Current split:
- `CandidateStore` lifecycle,
- `suggestions.py` lifecycle,
- zone proposals in `habitus.py`,
- direct policy shaping in proposal accept.

**Directive:** Core should expose one obvious proposal surface and treat example/fallback suggestions as demo-only behavior, not product truth.

---

## 11. RAG chat pipeline as a Core surface

## 11.1 What chat is for

The Core chat surface exists to let users and operators query:
- semantic truth,
- live home context,
- memory,
- indexed knowledge,
- explanations of current recommendations and state.

## 11.2 Durable architecture

The durable chat pipeline is:

`query -> query classification -> retrieval (BM25 + semantic + optional web) -> RRF fusion -> conversation memory/context -> live home context -> LLM inference -> explainable response with sources`

That is already substantially visible in:
- `styx_chat.py`
- `chat_handler.py`
- `rag.py`
- `conversation_memory.py`
- `vector_store/store.py`

## 11.3 Architectural rule

Chat must consume Core truth/read models rather than re-derive semantics ad hoc from random service internals.

In other words:
- chat is not a separate intelligence silo,
- it is a conversational surface over Core truth, memory, and reasoning.

---

## 12. API surfaces Core should own

Core APIs should be grouped by responsibility, not historical accidents.

## 12.1 Ingest surfaces
- canonical event ingest,
- canonical topology sync,
- operator feedback / proposal decisions,
- ingest health/stats.

## 12.2 Truth/query surfaces
- zones,
- entities,
- modules,
- current normalized state,
- policy state,
- diagnostics/freshness,
- graph/truth summaries.

## 12.3 Cognitive/output surfaces
- proposals,
- action intents,
- mood views,
- autonomy status,
- explanations,
- behavioral history,
- brain/neuron summaries.

## 12.4 Visualization surfaces
- zone dashboard summary,
- zone detail,
- module dashboard/read models,
- system overview,
- timelines/history feeds.

## 12.5 Conversational surfaces
- Styx chat,
- RAG search/index/rerank,
- memory stats/history,
- source/explanation payloads for answers.

## 12.6 Adapter surfaces
Core may emit HA-facing commands and schemas, but those must stay thin.
Core should decide; adapters should execute.

---

## 13. What Core must emit back for visualization

Visualization should consume Core read models, not rebuild semantics from internals.

## 13.1 Required `ZoneSummaryReadModelV1`
At minimum:
- `zone_id`
- `name`
- `zone_type`
- `status`
- `last_activity_at`
- `entity_count`
- `entity_counts_by_domain`
- `entity_counts_by_role`
- `module_states`
- `module_summaries`
- `automation_mode`
- `mood`
- `health`
- `pending_proposals_count`
- `top_active_signals`
- `quick_actions`
- `freshness`
- `provenance`

## 13.2 Required `ZoneDetailReadModelV1`
At minimum:
- summary fields above,
- canonical entity list,
- entities grouped by role/tag/domain,
- module configs and applicability,
- recent events,
- recent proposals,
- recent action intents / outcomes,
- autonomy history,
- explanation snippets,
- confidence/warning flags when data is partial or inferred.

## 13.3 Required `ModuleReadModelV1`
At minimum:
- `module_id`
- `state`
- `zones[]`
- `entity_count`
- `inputs_ready`
- `outputs_available`
- `policy_state`
- `summary_metrics`
- `freshness`
- `explanation`

## 13.4 Required `SystemOverviewReadModelV1`
At minimum:
- total zones,
- total synced entities,
- total modules,
- ingest freshness,
- topology sync freshness,
- proposal backlog,
- autonomy activity stats,
- top warnings/errors,
- graph/mood/zone-health summaries,
- chat/RAG health summary.

## 13.5 Visualization rule

Dashboards should not have to re-derive:
- zone membership,
- zone type,
- role/tag meaning,
- module applicability,
- proposal risk,
- execution eligibility,
- mood meaning,
- chat-usable explanation fragments.

That interpretation belongs in Core.

---

## 14. Non-goals for Core

Core should **not** become:
- a Lovelace card repository,
- a HACS UX repository,
- the raw HA registry owner,
- a second frontend composition layer powered by example data,
- a duplicate policy engine living beside HA.

---

## 15. Roadmap for autonomous development

This is the recommended slice order.

### Slice 1 — Canonical ingest lane
**Goal:** one event ingest path, one normalized store, one processing pipeline.

Deliverables:
- retire `events.py` as the public authoritative ingest lane or reduce it to explicit compatibility adapter behavior,
- standardize on `ingest/event_store.py` + `EventProcessor`,
- remove ambiguous duplicate route exposure between test/prod wiring,
- align `app.py` and production semantics around the same contract.

Acceptance:
- one authoritative `POST /api/v1/events`,
- one store implementation for canonical event truth,
- one post-ingest pipeline into graph/mining/modules.

### Slice 2 — Zone truth store + canonical topology sync
**Goal:** one Core-owned zone instance truth layer.

Deliverables:
- typed zone definition model,
- revisioned sync storage,
- freshness/provenance metadata,
- canonical distinction between archetype and instance,
- removal of ad hoc truth like `cfg._ha_entities` as the real source.

Acceptance:
- dashboard, habitus, autonomy, modules, and chat context can all query the same zone truth.

### Slice 3 — First-class module model and end-to-end wiring
**Goal:** promote existing Core modules into one coherent, policy-aware runtime layer.

Deliverables:
- canonical `ModuleSnapshotV1` / metadata model,
- zone-to-module applicability mapping,
- align existing modules (`licht`, `helligkeit`, `heiz`, `bewegung`, `praesenz`, music/media, energy, scenes, HA connection) with one input/output contract,
- wire module summaries and commands through truth-backed read models,
- correct inconsistent partial implementations instead of adding parallel abstractions.

Acceptance:
- existing modules appear in architecture and runtime as first-class units,
- Habitus zones can reference modules cleanly,
- dashboard and policy layers can consume module truth directly.

### Slice 4 — Classification authority
**Goal:** one taxonomy service for roles/tags/categories/module buckets.

Deliverables:
- canonical category registry,
- migration path from `zone_automation.py` role/tag helpers,
- shared classification outputs for ingest, topology, dashboard, proposals, and chat context.

Acceptance:
- Core no longer has multiple competing semantic classifiers.

### Slice 5 — Brain growth unification
**Goal:** make semantic transfer into graph + neuron representations explicit and inspectable.

Deliverables:
- explicit transfer layer from normalized inputs to graph/neuron/module updates,
- read model for brain growth/activity,
- stronger link between zone/entity/module truth and neuron evaluation,
- contract-level documentation for how semantic inputs strengthen graph/neuron context.

Acceptance:
- the “growing brain” is no longer only an implicit concept in separate subsystems.

### Slice 6 — Truth-backed dashboard read models
**Goal:** dashboard surfaces read live Core truth.

Deliverables:
- zone summary read model,
- zone detail read model,
- module read model,
- system overview read model,
- explicit freshness/provenance,
- production removal of example-data dependence.

Acceptance:
- `zone_dashboard.py` becomes a consumer of truth, not a place that invents truth.

### Slice 7 — Unified proposal lifecycle
**Goal:** unify candidates, suggestions, proposals, and action intents.

Deliverables:
- one lifecycle store/state machine,
- one accept/reject/snooze surface,
- first-class `ProposalIntentV1` and `ActionIntentV1`,
- attached evidence/explanation by default,
- module-aware action handoff contracts.

Acceptance:
- there is one obvious Core proposal product surface.

### Slice 8 — HA connection module hardening
**Goal:** solidify the Core-side HA module as the semantic input connection layer.

Deliverables:
- clarify connection-module contract,
- align `HomeAssistantModuleEngine` and `ModuleRouter` with normalized truth inputs,
- expose transport/pipeline health as first-class diagnostics,
- ensure downstream modules consume prepared inputs, not raw HA payloads.

Acceptance:
- the HA module is clearly a connection/preparation layer, not a second semantic owner.

### Slice 9 — RAG/chat alignment with truth layer
**Goal:** make chat a stable consumer of Core truth rather than ad hoc service scraping.

Deliverables:
- formal chat context blocks sourced from truth/read models,
- retrieval provenance improvements,
- stronger mapping between modules/zones/brain summaries and chat explanations,
- tests for source-grounded responses and memory integration.

Acceptance:
- chat is visibly attached to the Core semantic model.

### Slice 10 — Decision/execution separation hardening
**Goal:** keep Core as decider and HA as executor.

Deliverables:
- formal HA adapter command output contract,
- consistent behavioral log / audit trail,
- audit of direct execution paths that bypass unified action-intent flow.

Acceptance:
- policy remains centralized in Core.

### Slice 11 — Contract and regression coverage
**Goal:** make fragmentation hard to reintroduce.

Deliverables:
- ingest contract tests,
- topology sync contract tests,
- module contract tests,
- brain/read-model snapshot tests,
- proposal lifecycle tests,
- dashboard e2e against truth-backed data,
- chat/RAG integration coverage.

Acceptance:
- future work cannot silently re-split ingest, topology, modules, chat, or proposal semantics.

---

## 16. Final rule set

1. **HA owns raw runtime home state.**  
2. **Core owns normalized semantic truth and reasoning.**  
3. **Modules are first-class Core runtime units, not dashboard decoration.**  
4. **All reasoning uses normalized Core models, not raw HA payloads.**  
5. **Zone archetypes and policy live in Core; zone instances come from synced truth.**  
6. **Semantic inputs must transfer into truth, graph, neurons, and modules.**  
7. **Suggestions and action intents are Core products, not UI glue.**  
8. **RAG chat is a Core reasoning surface over truth, memory, and live home context.**  
9. **Visualization consumes Core read models, not internal fragments.**  
10. **Execution adapters stay thin; governance stays in Core.**

---

## 17. Practical bottom line

If a future change is about:
- normalization,
- module identity/configuration/applicability,
- zone/entity meaning,
- categorization,
- semantic transfer into brain state,
- mood/habitus reasoning,
- proposal/action-intent lifecycle,
- execution eligibility,
- stable read models,
- RAG/chat context over home truth,

then it belongs in **Core**.

If a future change is about:
- collecting from Home Assistant,
- calling HA services,
- materializing HA entities,
- Repairs/Lovelace/config-flow UX,
- presenting controls inside HA,

then it belongs in **HA/HACS**.

That is the durable boundary.