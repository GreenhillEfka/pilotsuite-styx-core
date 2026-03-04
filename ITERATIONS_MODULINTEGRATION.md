# PilotSuite Styx — 3 Iterationsschleifen: Modulintegration & Neuronenlayer

## Architektur-Überblick

```
┌─────────────────────────────────────────────────────────────────┐
│                    Home Assistant (Events + States)              │
└──────────────────────────┬──────────────────────────────────────┘
                           │
              ┌────────────▼─────────────┐
              │ pilotsuite-styx-ha       │
              │ (HACS Integration)       │
              │                          │
              │ ┌──────────────────────┐ │
              │ │ 14 Neuron Sensors    │ │  Layer 0-2 Spiegel
              │ │ 8 Spezial-Sensors    │ │  (mood, anomaly, energy...)
              │ │ 6 Core Modules       │ │  (habitus_miner, calendar...)
              │ │ Coordinator (Poll)   │ │  Polling alle 30s
              │ └──────────┬───────────┘ │
              └────────────┼─────────────┘
                           │ HTTP/REST
              ┌────────────▼─────────────┐
              │ pilotsuite-styx-core     │
              │ (Add-on, Port 8909)      │
              │                          │
              │ ┌──────────────────────┐ │
              │ │ NeuronManager        │ │  14 Neuronen, 3 Layer
              │ │ BrainGraph (SQLite)  │ │  Semantischer Wissensgraph
              │ │ Habitus Miner        │ │  A→B Pattern-Mining
              │ │ ModuleRegistry       │ │  Modul-Autonomie-Kontrolle
              │ │ SVG Renderer         │ │  Graphviz-Visualisierung
              │ └──────────────────────┘ │
              └──────────────────────────┘
```

### Aktuelle Neuronen-Architektur (14 Neuronen, 23 Synapsen)

| Layer | Neuronen | Funktion |
|-------|----------|----------|
| **0: Context** (5) | presence, time_of_day, light_level, weather, activity | Objektive HA-Sensordaten |
| **1: State** (5) | energy_level, comfort, productivity, relaxation, social | EMA-geglättete Zustände |
| **2: Mood** (4) | focus, relax, energy, calm | Aggregierte Stimmungen |

### Identifizierte Lücken

1. **Fehlende Brücke** zwischen BrainGraph (Wissensgraph) und NeuronManager (Pipeline)
2. **Keine Layer-übergreifende Visualisierung** — SVG zeigt nur BrainGraph, nicht die Neuron-Pipeline
3. **Module isoliert** — Habitus Miner, Calendar, Zone Mining arbeiten unabhängig
4. **Kein Feedback-Loop** — Akzeptierte/abgelehnte Suggestions fließen nicht zurück
5. **Sensor-Spiegelung unvollständig** — HA-Sensors spiegeln Core-Zustand, aber nicht bidirektional
6. **ModuleRegistry nicht integriert** mit NeuronManager (Modul-States beeinflussen nicht die Pipeline)

---

## Iteration 1: Modul-Integrationsbus & Best-Practice Fundament

**Ziel:** Einheitlicher Kommunikationskanal zwischen allen Modulen, robuste Basisarchitektur

### 1.1 Module Integration Bus (Core)

**Datei:** `copilot_core/rootfs/usr/src/app/copilot_core/integration/bus.py`

```python
# Konzept: Event-basierter Integrationsbus
class ModuleIntegrationBus:
    """Zentraler Bus für Modul-zu-Modul-Kommunikation."""

    # Events die Module publizieren/abonnieren können:
    # - neuron.evaluated    → Pipeline-Ergebnis (14 Werte)
    # - mood.changed        → Dominante Stimmung gewechselt
    # - pattern.discovered  → Habitus Miner neues Pattern
    # - suggestion.accepted → User hat Vorschlag akzeptiert
    # - suggestion.rejected → User hat Vorschlag abgelehnt
    # - graph.updated       → BrainGraph neue Knoten/Kanten
    # - module.state_changed → ModuleRegistry Statusänderung

    def publish(event_type: str, data: dict) → None
    def subscribe(event_type: str, callback: Callable) → str
    def unsubscribe(subscription_id: str) → None
```

### 1.2 Module Lifecycle Protocol

**Datei:** `copilot_core/rootfs/usr/src/app/copilot_core/integration/protocol.py`

```python
class ModuleProtocol(ABC):
    """Standardisiertes Interface für alle Module."""

    @abstractmethod
    def get_id(self) -> str: ...

    @abstractmethod
    def get_layer(self) -> int: ...  # 0=context, 1=state, 2=mood, 3=meta

    @abstractmethod
    def get_dependencies(self) -> list[str]: ...

    @abstractmethod
    def on_bus_event(self, event_type: str, data: dict) -> None: ...

    @abstractmethod
    def get_state_summary(self) -> dict: ...
```

### 1.3 ModuleRegistry ↔ NeuronManager Verknüpfung

**Änderungen in:** `neurons/manager.py`, `module_registry.py`

- ModuleRegistry-State beeinflusst Neuron-Gewichtung
- Module im "learning"-Modus: Neuronen evaluieren, aber Suggestions markiert als "learning_only"
- Module im "off"-Modus: zugehörige Neuronen überspringen

### 1.4 Feedback-Loop: Suggestions → BrainGraph

**Änderungen in:** `brain_graph/service.py`, `api/v1/habitus.py`

- Akzeptierte Suggestions: Kante im BrainGraph verstärken (+delta)
- Abgelehnte Suggestions: Kante abschwächen (-delta)
- Pattern-Confidence im Habitus Miner anpassen

### 1.5 Tests & Validierung

- Unit-Tests für IntegrationBus (publish/subscribe, async)
- Integrationstest: Neuron-Evaluation → Bus-Event → Habitus Listener
- Test: ModuleRegistry.set_state → NeuronManager reagiert
- Test: Suggestion feedback → BrainGraph edge weight update

### Dateien (Iteration 1):

| Neu/Änderung | Datei | Beschreibung |
|--------------|-------|-------------|
| **NEU** | `integration/bus.py` | Event-Bus für Modul-Kommunikation |
| **NEU** | `integration/protocol.py` | Standardisiertes Modul-Interface |
| **NEU** | `integration/__init__.py` | Package init |
| ÄNDERN | `neurons/manager.py` | Bus-Integration, ModuleRegistry-Check |
| ÄNDERN | `module_registry.py` | Bus-Events bei State-Änderung |
| ÄNDERN | `brain_graph/service.py` | Feedback-Loop für Suggestions |
| ÄNDERN | `api/v1/habitus.py` | Pattern-Confidence Anpassung |
| **NEU** | `tests/test_integration_bus.py` | Bus-Tests |
| **NEU** | `tests/test_module_protocol.py` | Protocol-Tests |

---

## Iteration 2: Visualisierung & Neuronenlayer-Dashboard

**Ziel:** Einheitliche Visualisierung aller Layer, Live-Ansicht der Neuron-Pipeline, interaktives Dashboard

### 2.1 Unified Neuron Layer Visualization (Core API)

**Datei:** `copilot_core/rootfs/usr/src/app/copilot_core/api/v1/neuron_layers.py`

Neuer Endpoint: `GET /api/v1/neurons/layers/visualization`

```json
{
  "layers": [
    {
      "id": 0, "name": "Context",
      "neurons": [
        {"id": "context.presence", "value": 0.8, "active": true, "fire_rate": 2.1, "trend": "stable"},
        ...
      ]
    },
    {
      "id": 1, "name": "State", "neurons": [...] },
    {
      "id": 2, "name": "Mood", "neurons": [...] }
  ],
  "connections": [
    {"from": "context.presence", "to": "state.energy_level", "weight": 0.8, "signal_strength": 0.64, "type": "synapse"},
    ...
  ],
  "modules": [
    {"id": "habitus_miner", "state": "active", "layer": 3, "patterns_found": 42},
    {"id": "brain_graph", "state": "active", "layer": 3, "nodes": 234, "edges": 567}
  ],
  "pipeline_status": {
    "last_evaluation": "2026-03-04T12:00:00Z",
    "cycle_ms": 14,
    "dominant_mood": "focus",
    "mood_confidence": 0.87
  }
}
```

### 2.2 Layer-übergreifende SVG-Visualisierung (Core)

**Datei:** `copilot_core/rootfs/usr/src/app/copilot_core/brain_graph/neuron_render.py`

Neuer Endpoint: `GET /api/v1/neurons/layers/snapshot.svg`

```
Visualisierung:
┌─────────────────────────────────────────────┐
│ Layer 0: Context                            │
│  ○ presence  ○ time  ○ light  ○ weather  ○ act │
│  │\          │/      │        │         /│  │
│  │ \─────────┼───────┼────────┼────────/ │  │
├──┼───────────┼───────┼────────┼──────────┼──┤
│ Layer 1: State                              │
│  ● energy    ● comfort  ● productivity      │
│  ● relaxation  ● social                     │
│  │\          │/         │                   │
├──┼───────────┼──────────┼───────────────────┤
│ Layer 2: Mood                               │
│  ◉ focus    ◉ relax   ◉ energy   ◉ calm    │
├─────────────────────────────────────────────┤
│ Layer 3: Meta-Module                        │
│  □ habitus  □ brain_graph  □ calendar       │
└─────────────────────────────────────────────┘

Legende:
○ = inaktives Neuron  ● = aktives Neuron  ◉ = dominantes Mood
─ = Synapse (Dicke = Gewicht)
→ = Signal-Fluss  ⟲ = Feedback-Loop
Farbe = Signal-Stärke (grau→grün→gelb→rot)
```

**Rendering-Features:**
- Graphviz DOT-Layout mit custom Layer-Constraint (rank=same)
- Knotenfarbe: Wert-basiert (0.0=grau, 0.5=grün, 1.0=rot)
- Kantendicke: proportional zu weight × signal_strength
- Feedback-Loops: gestrichelte Linien
- Modulatory: gepunktete Linien
- Meta-Module (Layer 3): Rechtecke statt Kreise

### 2.3 HA Frontend: Lovelace Custom Card (styx-ha)

**Datei:** `custom_components/copilot_ha/frontend/neuron-layer-card.js`

Custom Lovelace Card die:
- Layer-SVG vom Core-Endpoint lädt
- Interaktive Neuronen (Click → Detail-Panel)
- Live-Update alle 30s (via Coordinator)
- Touch-gesten für Mobile (Swipe zwischen Layers)
- Dark/Light Theme Support

### 2.4 Connection Heatmap Endpoint

**Datei:** `copilot_core/rootfs/usr/src/app/copilot_core/api/v1/neuron_layers.py`

`GET /api/v1/neurons/connections/heatmap`

```json
{
  "matrix": [
    [0, 0.8, 0, 0, 0, 0.64, 0, 0, 0.56, 0, 0, 0, 0, 0],
    ...
  ],
  "labels": ["presence", "time", "light", "weather", "activity",
             "energy", "comfort", "productivity", "relaxation", "social",
             "focus", "relax", "energy_mood", "calm"],
  "layer_boundaries": [5, 10, 14]
}
```

### 2.5 Tests & Validierung

- Test: Layer visualization endpoint returns correct structure
- Test: SVG rendering with all 14 neurons + 23 edges
- Test: Heatmap matrix dimensions match neuron count
- Test: Signal strength calculation (weight × source_value)
- Test: Frontend card renders without errors

### Dateien (Iteration 2):

| Neu/Änderung | Datei | Beschreibung |
|--------------|-------|-------------|
| **NEU** | `api/v1/neuron_layers.py` | Layer-Visualization + Heatmap Endpoints |
| **NEU** | `brain_graph/neuron_render.py` | Layer-SVG Renderer |
| ÄNDERN | `app.py` | Blueprint registrieren |
| **NEU** (HA) | `frontend/neuron-layer-card.js` | Lovelace Custom Card |
| ÄNDERN (HA) | `coordinator.py` | Layer-Daten in Polling integrieren |
| **NEU** | `tests/test_neuron_layers_api.py` | API-Tests |
| **NEU** | `tests/test_neuron_render.py` | SVG-Render-Tests |

---

## Iteration 3: Modul-Vernetzung & Intelligente Verknüpfung

**Ziel:** Module arbeiten zusammen, lernen voneinander, automatische Synapse-Gewichtsanpassung

### 3.1 Adaptive Synapse Weights (Hebbian Learning)

**Datei:** `copilot_core/rootfs/usr/src/app/copilot_core/neurons/learning.py`

```python
class HebbianLearning:
    """
    Hebbian Learning für Synapse-Gewichtsanpassung.

    Prinzip: "Neurons that fire together, wire together"

    Wenn Context-Neuron A und State-Neuron B gleichzeitig hoch feuern,
    wird die Synapse A→B verstärkt. Wenn A hoch und B niedrig, abschwächen.

    Δw = η * (x_pre * x_post - λ * w)

    η = Lernrate (default: 0.01)
    λ = Weight Decay (default: 0.001)
    """

    def update_weights(self, pre_values: dict, post_values: dict,
                       connections: list[GraphEdge]) -> list[WeightUpdate]:
        """Berechne Gewichts-Updates basierend auf Co-Aktivierung."""

    def apply_suggestion_feedback(self, suggestion_id: str, accepted: bool,
                                   related_neurons: list[str]) -> list[WeightUpdate]:
        """Passe Gewichte an basierend auf User-Feedback."""
```

### 3.2 Cross-Module Pattern Discovery

**Datei:** `copilot_core/rootfs/usr/src/app/copilot_core/integration/cross_module.py`

```python
class CrossModuleAnalyzer:
    """
    Entdeckt Muster ZWISCHEN Modulen.

    Beispiele:
    - Habitus Pattern "light.on → coffee.on" + Mood "focus" →
      Neues Meta-Pattern: "morning_focus_routine"
    - Calendar "meeting_start" + Zone "office" + Mood "focus" →
      Automation: "Pre-Meeting Focus Mode"
    - Energy "solar_peak" + Activity "low" →
      Suggestion: "Waschmaschine starten (Solarstrom)"
    """

    def analyze_correlations(self, timeframe_hours: int = 24) -> list[CrossPattern]:
        """Analysiere Korrelationen zwischen Modul-Outputs."""

    def suggest_new_connections(self) -> list[ProposedSynapse]:
        """Schlage neue Synapsen zwischen Neuronen vor."""
```

### 3.3 Dynamic Layer Extension

**Datei:** `copilot_core/rootfs/usr/src/app/copilot_core/neurons/dynamic.py`

```python
class DynamicNeuronFactory:
    """
    Erstellt neue Neuronen basierend auf entdeckten Mustern.

    Wenn der CrossModuleAnalyzer wiederholt das Pattern
    "morning + solar_high + low_activity" findet, kann ein neues
    Context-Neuron "routine.morning_solar" vorgeschlagen werden.

    Layer 3 (Meta): Aggregiert Outputs mehrerer Module:
    - meta.routine_stability  → Kombination aus Habitus + Calendar
    - meta.energy_context     → Energy + Weather + Solar
    - meta.security_status    → UniFi + Camera + Door Sensors
    """

    def propose_neuron(self, pattern: CrossPattern) -> ProposedNeuron: ...
    def create_neuron(self, proposal: ProposedNeuron) -> BaseNeuron: ...
    def connect_to_existing(self, neuron: BaseNeuron) -> list[GraphEdge]: ...
```

### 3.4 Module Health & Performance Dashboard

**Datei:** `copilot_core/rootfs/usr/src/app/copilot_core/api/v1/module_health.py`

`GET /api/v1/modules/health/dashboard`

```json
{
  "modules": [
    {
      "id": "habitus_miner",
      "state": "active",
      "health": "healthy",
      "metrics": {
        "patterns_discovered": 42,
        "suggestions_generated": 128,
        "acceptance_rate": 0.67,
        "avg_confidence": 0.78
      },
      "connections_to": ["brain_graph", "mood_engine", "suggestion_panel"],
      "bus_events_published": 234,
      "bus_events_consumed": 567,
      "last_activity": "2026-03-04T12:00:00Z"
    },
    ...
  ],
  "integration_health": {
    "bus_throughput_per_min": 45,
    "cross_module_patterns": 12,
    "synapse_updates_24h": 89,
    "proposed_neurons": 3
  }
}
```

### 3.5 HA Integration: Module Status Sensor

**Datei (HA):** `custom_components/copilot_ha/sensors/module_integration.py`

Neue Sensoren:
- `sensor.copilot_module_health` — Gesamtstatus aller Module
- `sensor.copilot_synapse_activity` — Synapse-Update-Rate
- `sensor.copilot_cross_patterns` — Entdeckte Cross-Module Patterns
- `sensor.copilot_learning_progress` — Lernfortschritt (% of patterns confirmed)

### 3.6 Suggestion Enrichment Pipeline

**Änderungen in:** `api/v1/habitus.py`, `neurons/manager.py`

Vorschläge werden angereichert mit:
- Welche Module zum Vorschlag beigetragen haben
- Confidence aus jedem Modul einzeln
- Neuron-Layer-Kontext (welche Neuronen aktiv waren)
- Historische Akzeptanzrate für ähnliche Vorschläge

### 3.7 Tests & Validierung

- Test: Hebbian Learning konvergiert bei wiederholter Co-Aktivierung
- Test: Weight Decay verhindert unbegrenztes Wachstum
- Test: CrossModuleAnalyzer findet bekannte Test-Patterns
- Test: DynamicNeuronFactory erstellt valide Neuronen
- Test: Module Health Dashboard aggregiert korrekt
- Test: Suggestion Enrichment enthält alle Quellen

### Dateien (Iteration 3):

| Neu/Änderung | Datei | Beschreibung |
|--------------|-------|-------------|
| **NEU** | `neurons/learning.py` | Hebbian Learning für Synapsen |
| **NEU** | `integration/cross_module.py` | Cross-Module Pattern Discovery |
| **NEU** | `neurons/dynamic.py` | Dynamische Neuron-Erzeugung |
| **NEU** | `api/v1/module_health.py` | Modul-Health Dashboard API |
| ÄNDERN | `neurons/manager.py` | Learning-Integration, Dynamic Neurons |
| ÄNDERN | `api/v1/habitus.py` | Suggestion Enrichment |
| ÄNDERN | `app.py` | Neue Blueprints registrieren |
| **NEU** (HA) | `sensors/module_integration.py` | Neue HA-Sensoren |
| ÄNDERN (HA) | `__init__.py` | Sensor-Platform registrieren |
| **NEU** | `tests/test_hebbian_learning.py` | Learning-Tests |
| **NEU** | `tests/test_cross_module.py` | Cross-Module-Tests |
| **NEU** | `tests/test_dynamic_neurons.py` | Dynamic-Neuron-Tests |

---

## Zusammenfassung: 3 Iterationen

| Iteration | Fokus | Neue Dateien | Geänderte Dateien | Tests |
|-----------|-------|-------------|-------------------|-------|
| **1** | Integrationsbus & Fundament | 4 | 4 | 2 Test-Dateien |
| **2** | Visualisierung & Dashboard | 4 (+ 1 HA) | 2 (+ 1 HA) | 2 Test-Dateien |
| **3** | Vernetzung & Intelligenz | 5 (+ 1 HA) | 3 (+ 1 HA) | 3 Test-Dateien |
| **Gesamt** | | **13 neue** | **9 geänderte** | **7 Test-Dateien** |

### Abhängigkeiten

```
Iteration 1 (Bus + Protocol)
    ↓ (Bus wird von allen folgenden genutzt)
Iteration 2 (Visualisierung)
    ↓ (Visualisierung zeigt auch Iteration 3 Daten)
Iteration 3 (Vernetzung + Learning)
```

### Prioritäten pro Iteration

**Iteration 1** — Muss zuerst, da alle anderen darauf aufbauen
- IntegrationBus ist das Fundament
- ModuleProtocol standardisiert alle Module
- Feedback-Loop ist sofort wertvoll

**Iteration 2** — Macht die Architektur sichtbar
- Layer-SVG zeigt den gesamten Neuron-Fluss
- Lovelace Card macht es für User greifbar
- Heatmap für Debugging und Optimierung

**Iteration 3** — Macht das System intelligent
- Hebbian Learning: Synapsen passen sich an
- Cross-Module Patterns: emergente Intelligenz
- Dynamic Neurons: System wächst organisch
