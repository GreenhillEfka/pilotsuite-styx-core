# Slice 131: Neuron-View Expansion

**Status:** Analyzed (2026-04-05)
**Basis:** neurons.py (existing) + neuron_graph.py

## Current State

| Endpoint | Status |
|----------|--------|
| GET /api/v1/neurons | ✅ List all neurons |
| GET /api/v1/neurons/<id> | ✅ Get neuron state |
| POST /api/v1/neurons/evaluate | ✅ Run evaluation |
| GET /api/v1/mood | ✅ Current mood |
| GET /api/v1/neuron-connections | ✅ Graph connections |
| GET /api/v1/neuron-paths | ✅ Path finding |

## Expansion Needed

1. **Neuron Activity Stream** — Real-time firing patterns
2. **Neuron Clustering** — Group by function/context
3. **Neuron Health Metrics** — Activation rates, latency
4. **Neuron Recommendations** — Auto-suggest new neurons

## Decision

**Action:** Add activity stream + clustering endpoints

**Priority:**
1. Activity stream (real-time firing)
2. Neuron clustering (functional groups)
3. Health metrics (performance)
4. Recommendations (auto-suggest)

