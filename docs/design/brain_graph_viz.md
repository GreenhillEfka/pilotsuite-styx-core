# Brain Graph Visualization: Metrics & Interaction

**Status:** Finalized (2026-04-06)
**Owner:** DesignClaw
**Core-Worktree:** pilotsuite-styx-core-current

## 1. Dashboard Metriken (Brain-Tab)
Das Backend-UI visualisiert den Zustand des Knowledge-Graphs über folgende KPIs:

- **Node-Growth:** Anzahl neuer Entitäten (letzte 24h/7d).
- **Edge-Density:** Verhältnis Beziehungen zu Entitäten.
- **Semantic-Overlap:** Maß für die Kohärenz des Wissensmodells.
- **Pruning-Status:** Anzahl entfernter veralteter Kanten.

## 2. Interaktive Visualisierung (React-Flow / D3)
- **Mapping:** `node_type` steuert Icon/Farbe.
- **Kanten:** Stärke der Kante visualisiert die `weight` / `confidence` der Beziehung.
- **Interaktion:** Click auf Node öffnet Detail-Drawer mit allen Metadaten aus `BrainGraphService`.

## 3. API-Contract (Slice 138)
`GET /api/v1/backend/brain/graph` liefert:
- `nodes`: `[{id, label, type, attributes}]`
- `edges`: `[{source, target, label, weight}]`

## 4. Success Signal
Backend-UI zeigt einen interaktiven Graphen, der direkt auf der kanonischen Graph-Wahrheit basiert.
