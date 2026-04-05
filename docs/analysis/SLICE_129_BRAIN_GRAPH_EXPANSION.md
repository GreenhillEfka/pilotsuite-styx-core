# Slice 129: Brain-Graph API Expansion

**Status:** Analyzed (2026-04-05)
**Basis:** Existing graph.py + test_brain_graph_api.py

## Current State

| Endpoint | Status |
|----------|--------|
| GET /api/v1/graph/state | ✅ Implemented |
| POST /api/v1/graph/node | ✅ Implemented |
| POST /api/v1/graph/edge | ✅ Implemented |
| GET /api/v1/graph/query | ⚠️ Basic |
| GET /api/v1/graph/traverse | ⚠️ Basic |

## Expansion Needed

1. **Knowledge Graph Queries** — SPARQL-like queries
2. **Neuron-View Expansion** — Multi-hop traversal
3. **Graph Analytics** — Centrality, clustering, patterns
4. **Temporal Queries** — Time-based graph slices

## Decision

**Action:** Expand query endpoints + add analytics

**Priority:**
1. Graph query expansion (SPARQL-like)
2. Neuron multi-hop traversal
3. Graph analytics (centrality, patterns)
4. Temporal graph slices

## Next: Implementation

- Expand `graph.py` with query/analytics endpoints
- Add contract tests
- Document API

