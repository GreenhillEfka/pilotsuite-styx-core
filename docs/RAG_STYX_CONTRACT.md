# RAG Styx Contract — Slice 9 (2026-03-25)

## Status: IN PROGRESS

## Goal

Chat = stabiler Consumer von Core truth. RAG Styx nutzt Core-Read-Models als Retrieval-Quelle.

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                     PILOTSUITE CORE — Truth Layer                │
├──────────────────────────────────────────────────────────────────┤
│  EventStore (ingest/)   │  Brain Graph (brain_graph/)            │
│  Zone Truth (hub/)      │  Module Router (hub/module_router.py)  │
│  Neuron Manager         │  Mood Engine (mood/)                   │
│  Knowledge Graph        │  Proposal Store (candidates/)          │
└───────────────────────────┬──────────────────────────────────────┘
                            │
                            ▼ Read Models (TypedModels)
┌──────────────────────────────────────────────────────────────────┐
│                     RAG STYX — Retrieval Layer                   │
├──────────────────────────────────────────────────────────────────┤
│  BM25 Index (rag/bm25.py)      │  Semantic Backend (vector)      │
│  Query Router (classify)      │  SearXNG Client (web search)     │
│  Hybrid Search (RRF)          │  Context Blocks (truth-sourced)  │
└──────────────────────────────────────────────────────────────────┘
                            │
                            ▼ Chat Handler
┌──────────────────────────────────────────────────────────────────┐
│                     STYX CHAT — Generation Layer                 │
├──────────────────────────────────────────────────────────────────┤
│  styx/chat_handler.py           │  Context Blocks Assembly        │
│  Conversation Memory           │  Response Generation            │
└──────────────────────────────────────────────────────────────────┘
```

## RAG Components

| Component | File | Role |
|---|---|---|
| **BM25 Index** | `rag/bm25.py` | Lexical search over Core documents |
| **Semantic Backend** | `rag/semantic_backend.py` | Vector embedding search |
| **Hybrid Search** | `rag/hybrid_search.py` | RRF fusion of lexical + semantic |
| **Query Router** | `rag/query_router.py` | Classify queries (fact, action, context) |
| **SearXNG Client** | `rag/searxng_client.py` | Web search fallback |

## Core Truth → RAG Source Mapping

| Core Read Model | RAG Source | Context Block |
|---|---|---|
| `ZoneSummary` | Zone documents | `context_zones` |
| `ModuleSummary` | Module documents | `context_modules` |
| `NeuronState[]` | Neuron documents | `context_neurons` |
| `MoodSnapshot` | Mood documents | `context_mood` |
| `ProposalStore` | Proposal documents | `context_proposals` |
| `BrainGraph` | Entity/Zone nodes | `context_graph` |

## Context Block Assembly

```python
def assemble_context_blocks(query: str) -> list[ContextBlock]:
    """Assemble context blocks from Core truth for RAG retrieval."""
    blocks = []
    
    # 1. Zone context from Zone Truth Store
    zones = zone_engine.get_overview()
    blocks.append(ContextBlock(
        type="zones",
        source="zone_truth",
        content=zones.to_dict(),
        freshness=datetime.now(timezone.utc).isoformat()
    ))
    
    # 2. Module context from Module Router
    modules = module_router.get_summary()
    blocks.append(ContextBlock(
        type="modules",
        source="module_router",
        content=modules.to_dict(),
        freshness=datetime.now(timezone.utc).isoformat()
    ))
    
    # 3. Neuron context from Neuron Manager
    neurons = neuron_manager.get_all_states()
    blocks.append(ContextBlock(
        type="neurons",
        source="neuron_manager",
        content={n.name: n.to_dict() for n in neurons},
        freshness=datetime.now(timezone.utc).isoformat()
    ))
    
    # 4. Mood context from Mood Engine
    mood = mood_engine.get_current_mood()
    blocks.append(ContextBlock(
        type="mood",
        source="mood_engine",
        content=mood.to_dict(),
        freshness=datetime.now(timezone.utc).isoformat()
    ))
    
    # 5. Recent events from Event Store (canonical)
    events = event_store.list(limit=10)
    blocks.append(ContextBlock(
        type="events",
        source="event_store",
        content=events,
        freshness=datetime.now(timezone.utc).isoformat()
    ))
    
    return blocks
```

## Query Classification

```python
class QueryType(Enum):
    FACT = "fact"           # "What's the temperature in the living room?"
    ACTION = "action"       # "Turn off the lights in the bedroom"
    CONTEXT = "context"     # "Why did the heating turn on?"
    LEARNING = "learning"   # "How do I set up a new zone?"
    PROPOSAL = "proposal"   # "What improvements do you suggest?"
```

## Retrieval Flow

```
User Query
    │
    ▼ Query Classification (query_router.classify_query)
    │
    ├─── FACT ───► Zone/Entity/Module Read Models ───► Direct Answer
    │
    ├─── ACTION ─► Intent Parser ──► Module Router ──► Action Execution
    │
    ├─── CONTEXT ─► Event Store + Brain Graph ──► Context Assembly
    │
    ├─── LEARNING ──► Knowledge Graph + Docs ──► Explanation
    │
    └─── PROPOSAL ──► Proposal Store + Habitus Miner ──► Suggestions
```

## Provenance

Every RAG response MUST include provenance:

```python
@dataclass
class RAGProvenance:
    sources: list[str]      # ["zone_truth", "event_store", "brain_graph"]
    doc_ids: list[str]      # Document IDs retrieved
    freshness: str          # ISO timestamp
    confidence: float       # 0.0-1.0
    model_used: str         # "bm25", "semantic", "hybrid"
```

## Contract Owner

- **PilotClaw** — RAG Core, Event Store, Brain Graph
- **Stxy** — Chat Handler, Context Blocks, Query Router
- **HomeClaw** — HA Entity context for fact queries