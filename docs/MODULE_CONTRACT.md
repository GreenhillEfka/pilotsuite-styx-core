# Module Contract — Slice 3 (2026-03-25)

## Status: IN PROGRESS

## Hub Module System

Hub-Module sind die Aktor-Ebene von PilotSuite Core. Sie erhalten Events vom
Event Ingest Pipeline und können Aktionen auslösen.

### Core Modules (hub/)

| Module | Role | Entity Types |
|---|---|---|
| `helligkeit_module` | Light/brightness control | light.*, sensor.illuminance |
| `heiz_module` | Heating/climate control | climate.*, sensor.temperature |
| `bewegung_module` | Motion-based automation | binary_sensor.motion |
| `light_intelligence` | Adaptive lighting | light.* |
| `scene_intelligence` | Scene orchestration | scene.* |
| `predictive_maintenance` | Device health monitoring | device_tracker.*, sensor.* |
| `media_follow` | Media follow-me | media_player.* |
| `zone_automation` | Zone-based automation rules | zone.* |
| `brain_architecture` | Neural routing brain graph | — |
| `module_router` | Event→Module routing hub | — |

### Module Lifecycle

```
1. __init__(services) — receive service dependencies
2. register_routes(bus) — subscribe to IntegrationBus events
3. ingest_event(event) — receive events from EventProcessor
4. evaluate() — process and optionally trigger actions
```

### Module Metadata (TypedModel)

```python
@dataclass
class ModuleMetadata:
    module_id: str          # e.g. "helligkeit"
    display_name: str       # "Helligkeitssteuerung"
    description: str
    entity_domains: list[str]  # ["light", "sensor"]
    zone_applicable: set[str]  # ZoneTypes where module is active
    priority: int           # 0-100, higher = more important
    enabled: bool
    config_schema: dict     # JSON schema for module config
```

### Module Router

The `module_router.py` is the central hub that routes events to modules:

```
Event Ingest → EventProcessor → ModuleRouter.ingest_event(event)
                                         │
                    ┌────────────────────┼────────────────────┐
                    ▼                    ▼                    ▼
           HelligkeitModule     HeizModule        BewegungModule
```

## Neuron System

Neurons are the sensing layer that feeds into the brain graph and automation decisions.

### Neuron Types

| Type | Role | Examples |
|---|---|---|
| CONTEXT | Objective environmental factors | PresenceNeuron, TimeOfDayNeuron, LightLevelNeuron |
| STATE | Smoothed, inertial values | EnergyLevelNeuron, StressIndexNeuron, ComfortIndexNeuron |
| MOOD | Aggregated decision triggers | RelaxMood, FocusMood, ActiveMood, SleepMood |

### Neuron Configuration

```python
@dataclass
class NeuronConfig:
    name: str
    neuron_type: NeuronType
    threshold: float = 0.5
    decay_rate: float = 0.1
    smoothing_factor: float = 0.3
    entity_ids: List[str] = field(default_factory=list)  # HA entities watched
    weights: Dict[str, float] = field(default_factory=dict)
    enabled: bool = True
```

### Neuron State

```python
@dataclass
class NeuronState:
    active: bool = False
    value: float = 0.0
    confidence: float = 0.0
    last_update: Optional[str] = None
    last_trigger: Optional[str] = None
    trigger_count: int = 0
```

### Available Neurons

| Neuron | Type | Entity IDs (examples) | Output |
|---|---|---|---|
| PresenceNeuron | CONTEXT | person.*, binary_sensor.presence | 0-1 presence probability |
| TimeOfDayNeuron | CONTEXT | — | 0-1 time factor |
| LightLevelNeuron | CONTEXT | sensor.illuminance_* | 0-1 light level |
| WeatherNeuron | CONTEXT | weather.* | 0-1 weather factor |
| EnergyLevelNeuron | STATE | sensor.battery_*, sensor.power_* | 0-1 energy state |
| StressIndexNeuron | STATE | — (computed) | 0-1 stress level |
| ComfortIndexNeuron | STATE | sensor.temperature_*, sensor.humidity_* | 0-1 comfort |
| PVForecastNeuron | ENERGY | sensor.pv_forecast_* | 0-1 PV availability |
| GridOptimizationNeuron | ENERGY | sensor.grid_price | 0-1 grid cost factor |

## Contract Owner

- **PilotClaw** — Hub Module system, Neuron Manager
- **HomeClaw** — HA entity mapping
- **Stxy** — Dashboard visualization of modules