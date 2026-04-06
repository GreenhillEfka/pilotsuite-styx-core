# Brain Graph: Semantic Overlap Visualization

**Status:** Finalized (2026-04-06)
**Owner:** DesignClaw
**Core-Worktree:** pilotsuite-styx-core-current

## 1. Übersicht
Die "Semantic Overlap Heatmap" visualisiert, wie stark verschiedene Wissensbereiche (Zonen, Module, User-Präferenzen) im Knowledge-Graph miteinander verknüpft sind. Dies dient der Identifikation von "Knowledge Gaps" oder "Inconsistency Clusters".

## 2. Heatmap Matrix
Die Matrix stellt Entitäten auf beiden Achsen dar. Die Farbsättigung eines Quadrants visualisiert den `overlap_score` (0.0 - 1.0).

- **Achse X:** Source Entities (z.B. User-Moods)
- **Achse Y:** Target Entities (z.B. Zone-Automations)
- **Farbe:** 
  - Blau (Low Overlap / Silo)
  - Orange (High Overlap / Coherent)
  - Rot (Conflict Cluster)

## 3. UI-Interaktion
- **Hover:** Zeigt die Top 3 verbindenden Kanten (Edges) und deren Typen (z.B. `belongs_to`, `influences`).
- **Click:** Öffnet die betroffenen Entitäten im Graph-Viewer (Slice 138 Basis).

## 4. API-Contract (Erweiterung Slice 138)
`GET /api/v1/backend/brain/overlap` liefert:
```json
{
  "matrix": [
    {"source": "user_1", "target": "zone_living", "score": 0.85, "reason": "strong mood correlation"},
    {"source": "light_module", "target": "presence_sensor", "score": 0.92, "reason": "direct automation binding"}
  ]
}
```

## 5. Success Signal
Das Backend-UI ermöglicht dem User, die semantische Dichte seines "Haus-Gehirns" auf einen Blick zu erfassen und logische Lücken zu finden.
