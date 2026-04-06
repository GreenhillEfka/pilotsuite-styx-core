# SOTA Backend UI: Complete Visualisation & Configuration Spec

**Status:** In Progress (2026-04-06)
**Owner:** DesignClaw
**Ziel:** State-of-the-Art UI für alle Backend-Reiter

---

## 1. Dashboard (SOTA)

### Live-KPIs
- **System Health:** CPU/Memory/Token-Burn in Real-Time Charts.
- **Active Sessions:** Anzahl verbundener Clients (WebSocket).
- **API Latency:** P95/P99 Response Times pro Endpoint.
- **Anomaly Score:** ML-basierter Health-Score (0-100).

### Anomaly-Cards
- Proaktive Warnungen bei Latenz-Spikes oder Auth-Failures.
- Drill-Down zu Logs mit einem Klick.

---

## 2. Zones & Symbiosis (SOTA)

### Bidirectional Zone Mapper
- **Split-View:** Links HA-Areas, rechts Core-Habitus-Profile.
- **Drag & Drop:** Manuelles Mapping von Entitäten.
- **Auto-Match:** AI-basierte Vorschläge (z.B. "Wohnzimmer" → `living`).
- **Conflict Resolution:** UI für divergierende Zustände.

### Configuration Panel
- **Zone-Type Selector:** Dropdown mit Icons (Bett, Couch, etc.).
- **Metadata Editor:** Inline-Editing für `occupancy_timeout`, `mood_profile`.

---

## 3. Modules (SOTA)

### Inline Configuration
- **JSON Schema Forms:** Automatisch generiert aus Modul-Metadaten.
- **Live Preview:** Änderungen sofort im UI sichtbar.
- **Validation Feedback:** Rote Markierung bei invaliden Werten.
- **Feature Toggles:** Switch für jedes Modul-Feature (z.B. "Auto-Dimming").

---

## 4. Brain & Intelligence (SOTA)

### Interactive Graph Visualization
- **D3.js Force Graph:** Nodes (Entitäten) und Edges (Beziehungen).
- **Zoom & Pan:** Unbegrenzte Navigation.
- **Node Details:** Klick öffnet Drawer mit Metadaten.
- **Semantic Search:** Filter für Node-Typen und Edge-Labels.

### RAG Trace Timeline
- **Chronologische Ansicht:** Alle LLM-Entscheidungen.
- **Token Usage:** Visualisierung der Kosten pro Query.
- **Source Attribution:** Links zu den genutzten Dokumenten.

---

## 5. Security (SOTA)

### Real-Time Audit Stream
- **Live-Log:** WebSocket-basierte Updates.
- **Severity Colors:** Rot/Orange/Gelb für Alerts.
- **Quick Actions:** Acknowledge, Block IP, Rotate Token direkt im Log.

---

## 6. Design System

### Components
- **Shadcn/UI:** Basis für alle Komponenten.
- **Tailwind CSS:** Utility-first Styling.
- **Dark Mode:** Zwingend für alle Reiter.
- **Responsive:** Mobile-first Ansatz.

### Interactions
- **Micro-Animations:** 150ms Übergänge.
- **Toast Notifications:** Für alle Aktionen.
- **Skeleton Loading:** Platzhalter während Daten laden.

---

## Next Steps

1. Implementiere Dashboard-SOTA (Slice 145).
2. Implementiere Zones-SOTA (Slice 146).
3. Implementiere Modules-SOTA (Slice 147).
4. Implementiere Brain/RAG-SOTA (Slice 148).
5. Implementiere Security-SOTA (Slice 149).

**Go. Massiv parallel. Keine Pausen.**
