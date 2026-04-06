# SOTA Graph Visualization: Brain & Knowledge Spec

**Status:** Finalized (2026-04-06)
**Owner:** DesignClaw
**Core-Worktree:** pilotsuite-styx-core-current

## 1. Overview
This document specifies the interactive Knowledge Graph visualization for the PilotSuite Brain. It enables the user to navigate the semantic relationships between entities, habits, and learned patterns.

## 2. Technical Stack
- **Engine:** D3.js Force-Directed Graph.
- **Rendering:** SVG for nodes/edges, HTML/Tailwind for overlays.
- **Data Source:** `GET /api/v1/brain/graph/export` (JSON).

## 3. Node Types & Visuals
| Type | Shape | Color | Primary Info |
| :--- | :--- | :--- | :--- |
| **Zone** | Large Circle | Blue | Zone ID, Occupancy Status |
| **Entity** | Medium Circle | Green | Device Class, State |
| **Habit** | Hexagon | Gold | Activation Probability, Time-Slot |
| **User** | User Icon | Purple | Name, Preference Profile |

## 4. Interaction Patterns
- **Drag & Pin:** Nodes can be manually positioned and pinned.
- **Semantic Filtering:** Toggle visibility of specific node types.
- **Trace Replay:** Slider to visualize graph growth and state changes over time.
- **Edge Tooltip:** Shows relationship type (e.g., `IN_ZONE`, `HAS_HABIT`) and confidence score.

## 5. API-Contract (Slice 180)
`GET /api/v1/brain/graph/stream`
```json
{
  "type": "graph_update",
  "nodes": [{"id": "living_room", "group": "zone", "state": "occupied"}],
  "links": [{"source": "andreas", "target": "living_room", "value": 0.95, "label": "LOCATED_IN"}]
}
```

## 6. Success Signal
The user can intuitively "see" how the PilotSuite thinks and relates different home entities to each other.
