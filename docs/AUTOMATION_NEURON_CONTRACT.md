# Automation-Neuron Contract — Slice 3+4 (2026-03-25)

## Status: IN PROGRESS

## Goal

Automationen und Neuronen als einheitliches System: Jede Automation
referenziert beteiligte Neuronen und deren Synapsen (Entity-Trigger).

## Automation → Neuron Binding Matrix

### Bedtime Automation

```yaml
automation: lights_off_bedtime
  description: "Dim lights at bedtime when presence in bedroom"
  triggers:
    - time: "22:00"
    - condition:
        - zone: bedroom
        - presence: home
  neurons:
    - neuron: context.time_of_day
      triggers:
        - hour >= 22
      weight: 0.8
    - neuron: context.presence
      triggers:
        - person.* = home
      weight: 0.6
  mood_effect:
    mood: sleep
    weight: 0.7
  actions:
    - service: light.turn_on
      target: light.bedroom
      data:
        brightness: 20
        transition: 60
```

### Kids Home Alone Automation

```yaml
automation: kids_home_alone
  description: "Alert when only children present at home"
  triggers:
    - state_changed:
        entity_id: person.*
        to: "home"
  neurons:
    - neuron: context.presence
      triggers:
        - person.adult_* != home
        - person.child_* = home
      weight: 1.0
    - neuron: mood.alert
      weight: 0.9
  mood_effect:
    mood: alert
    weight: 1.0
  actions:
    - service: notify.parents
      message: "Only children home"
    - service: lock.lock
      target: lock.front_door
    - service: cover.close
      target: cover.ground_floor_windows
```

### Morning Routine Automation

```yaml
automation: morning_routine
  description: "Gentle wake-up lighting when anyone wakes"
  triggers:
    - time: "06:30"
    - condition:
        - presence: home
        - time_range: 06:00-08:00
  neurons:
    - neuron: context.time_of_day
      triggers:
        - hour: 06-08
      weight: 0.7
    - neuron: context.presence
      triggers:
        - person.* = home
      weight: 0.5
    - neuron: context.light_level
      triggers:
        - sensor.illuminance_* < 100
      weight: 0.3
  mood_effect:
    mood: active
    weight: 0.6
  actions:
    - service: light.turn_on
      target: light.living_room
      data:
        brightness: 30
        kelvin: 3000
        transition: 300
    - service: climate.set_temperature
      target: climate.living_room
      data:
        temperature: 21
```

### Party Mode Automation

```yaml
automation: party_mode
  description: "Dynamic lighting and music when party detected"
  triggers:
    - manual_trigger: button.party_mode
  neurons:
    - neuron: mood.social
      weight: 0.9
  mood_effect:
    mood: social
    weight: 1.0
  suppress_automations:
    - lights_off_bedtime
    - motion_lights_timeout
  actions:
    - service: light.turn_on
      target: group.party_lights
      data:
        effect: random
        brightness: 255
    - service: media_player.play_media
      target: media_player.party_zone
      data:
        playlist: "party_mix"
```

## Synapse Model

A **Synapse** is a connection between an Automation and a Neuron:

```python
@dataclass
class AutomationSynapse:
    """Binding between automation and neuron."""
    automation_id: str
    neuron_name: str
    entity_ids: list[str]  # HA entities that trigger this synapse
    triggers: list[dict]   # Trigger conditions
    weight: float          # 0.0-1.0 influence weight
    mood_effect: Optional[dict]  # Mood contribution if any
```

## Synapse Graph

```
Automation                Neuron                    Entity
────────────────────────────────────────────────────────────
lights_off_bedtime ──────► context.time_of_day ────── time_of_day
                    │     │
                    └────► context.presence ──────── person.*
                          │
                          └──► mood.sleep (weight: 0.7)
```

## Neuron Evaluation Pipeline

```
1. Event Ingest (HA state_changed)
2. EventProcessor.process_events()
3. ModuleRouter.ingest_event(event)
4. NeuronManager.evaluate_all(context)
   ├── ContextNeuron.evaluate() → value, confidence
   ├── StateNeuron.evaluate() → value, confidence
   └── MoodNeuron.evaluate() → mood, weight
5. BrainGraph.feed(neuron_states)
6. AutomationEngine.check_triggers(neuron_states)
7. ActionExecutor.execute(actions)
```

## Contract Owner

- **PilotClaw** — Neuron Manager, Automation Synapse Graph
- **HomeClaw** — HA Automation → Synapse Bridge
- **Stxy** — Automation Configuration UI