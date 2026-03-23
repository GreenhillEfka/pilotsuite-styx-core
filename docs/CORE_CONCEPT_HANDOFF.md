# Core Concept Handoff

## What was completed
- Revised `docs/CORE_CONCEPT_DIRECTIVE.md` with the missing product intent made explicit.
- Updated `TASKBOARD.md` so the roadmap now treats modules, brain growth, HA connection-module work, and RAG/chat as first-class slices.
- Kept the revision evidence-based against current docs and code, not just product preference.

## The durable decision
**Core is the semantic brain of PilotSuite.**

More precisely, Core is now explicitly defined as:
- semantic truth engine,
- first-class module runtime,
- brain / neuron / habitus reasoning layer,
- policy engine,
- explanation engine,
- and RAG/chat reasoning surface.

Boundary:
- **HA/HACS owns raw runtime truth**: devices, areas, raw state/events, HA service execution, HA-native UX.
- **Core owns normalized semantic truth and reasoning**: normalization, zones/entities/modules, semantic transfer into brain state, mood/habitus/proposals, action intents, read models, and chat context over that truth.

## What changed in this revision
1. **Modules are now first-class in the concept**
   - Existing modules like `licht`, `helligkeit`, `heiz`, `bewegung`, `praesenz`, media/music, scenes, energy, and the HA connection module are no longer treated like side details.
   - The concept now says zones must include module applicability, module policy, and module-facing inputs/outputs.
   - The roadmap now explicitly focuses on correcting and wiring existing modules end-to-end, not inventing a second abstraction layer.

2. **The growing brain representation is explicit**
   - Incoming normalized sensors/events/entities are now described as semantically transferring into:
     - truth updates,
     - graph updates,
     - neuron inputs,
     - and module context.
   - This stays evidence-based: the graph already grows via node/edge/trigger updates, and the neuron pipeline already exists, but the unified “brain growth” surface is still a roadmap item.

3. **The Core-side HA module is now described correctly**
   - It should be treated as a **connection module**.
   - It is not the semantic owner.
   - It monitors/bridges HA-origin input flow and delivers semantically prepared inputs to the rest of Core.

4. **RAG/chat is explicitly in scope**
   - The directive now treats `/api/styx/chat`, `ChatHandler`, `ConversationMemory`, `VectorStore`, `EmbeddingEngine`, and `/api/v1/rag/*` as part of Core’s product surface.
   - Chat is defined as a conversational layer over Core truth, memory, and live home context, not a sidecar.

## Most important findings
1. **Ingest is split twice**
   - not just route split (`events_ingest.py` vs `events.py`),
   - but also store split (`ingest/event_store.py` vs `storage/events.py`),
   - and test/prod wiring split (`app.py`/`blueprint.py` vs `core_setup.py`).

2. **Zone truth is still fragmented**
   - archetypes live in `homeassistant/habitus_zones.py`,
   - runtime config/entities live in `hub/zone_automation.py`,
   - synced HA topology is currently stored ad hoc via config attrs like `cfg._ha_entities`,
   - dashboard truth still depends on `habitus_zones` + `example_config` enrichment.

3. **Modules are present but not yet unified**
   - basis modules already exist and are wired into dashboard init,
   - but Core still lacks one canonical module truth/policy/read-model layer.

4. **Brain representation is real but split**
   - graph growth and neuron layering both exist,
   - but the semantic transfer model is still implicit.

5. **Chat/RAG already belongs to Core**
   - retrieval, memory, and live home context assembly are already in Core services,
   - but they should read from the same truth/read-model architecture as the rest of the system.

## Recommended next move
Do these next, in order:
1. **Slice 1 — canonical ingest lane**
2. **Slice 2 — zone truth layer + canonical topology sync**
3. **Slice 3 — first-class module model + end-to-end wiring**
4. **Slice 5 — brain growth unification**

## Main watch-outs
- Do not let HA/HACS become a second semantic engine.
- Do not keep dashboard production truth dependent on example data.
- Do not keep two event-ingest/storage realities alive.
- Do not keep raw HA payload parsing alive downstream after normalization.
- Do not treat existing modules as “later”; the repo already has them and now needs unification.
- Do not let chat/RAG drift into a separate truth model.