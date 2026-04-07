# Synapsen-Layer Dokumentation

## Konzept

Der Synapsen-Layer ist die zentrale Verbindung zwischen Home Assistant (HA) Entities und Core Neuronen. Er stellt sicher, dass jede HA-Entität sauber auf ein Core-Neuron abgebildet wird.

```
HA Entity (light.living_room) ──┐
HA Entity (sensor.temperature) ──┼──► Synapsen Contract ──► Core Neuronen
HA Entity (person.mira) ────────┘
```

## Komponenten

### 1. NeuronFeeder (`neurons/feeding.py`)

Haupteingang für HA-Events. Verantwortlich für:
- Empfang von HA Webhook-Events (entity_id, state, attributes)
- Mapping entity_id → neuron_id via Synapse Contract
- Schreiben von Aktivierungen in Brain Graph

**API:**
```python
feeder = NeuronFeeder()
result = feeder.feed("light.living_room", "on", attributes={"brightness": 255})
neuron_id = feeder.get_neuron_id("light.living_room")  # → "state.light_living_room"
```

### 2. DynamicNeuronCreator (`neurons/dynamic.py`)

Erstellt Neuronen dynamisch wenn neue HA-Entities auftauchen:
- Sensor → Context Neuron
- Switch/Light → State Neuron  
- Person/Device → Presence Neuron

### 3. ZonePresenceManager (`neurons/presence.py`)

Verbindet Presence-Neuronen mit Habitus-Zonen:
```python
manager = get_zone_presence_manager()
manager.register_zone("living", entity_ids=["person.mira", "person.paul"])
manager.get_zone_presence("living")
# → {"presence": true, "confidence": 0.95, "last_seen": "..."}
```

### 4. AutomationSynapseIntegrator (`automation/synapse_integration.py`)

Liest HA-Automationen und extrahiert neuronale Abhängigkeiten:
- Trigger Entities → Neuronen
- Condition Entities → Neuronen
- Action Entities → Neuronen

## API Endpoints

| Endpoint | Methode | Beschreibung |
|----------|---------|--------------|
| `/api/v1/synapse/feed` | POST | HA Event aufnehmen |
| `/api/v1/synapse/batch` | POST | Batch HA Events |
| `/api/v1/synapse/resolve/<entity_id>` | GET | entity_id → neuron_id |
| `/api/v1/synapse/contracts` | GET | Alle Synapse Contracts |
| `/api/v1/neurons/dynamic` | GET | Alle dynamischen Neuronen |
| `/api/v1/neurons/dynamic/<type>` | GET | Dynamische Neuronen nach Typ |
| `/api/v1/presence/zone/<zone_id>` | GET | Zonen-Präsenz |
| `/api/v1/presence/zones` | GET | Alle Zonen-Präsenzen |
| `/api/v1/synapse/integration/automations` | GET | Automation Synapses |
| `/api/v1/synapse/integration/zone/<zone_id>` | GET | Zonale Synapsen-Map |

## Entity → Neuron Type Mapping

| HA Domain | Neuron Type | Beispiel Neuron ID |
|-----------|-------------|-------------------|
| sensor | context | context.sensor_temperature |
| binary_sensor | context | context.binary_sensor_motion |
| light | state | state.light_living_room |
| switch | state | state.switch_kitchen |
| person | presence | presence.person_mira |
| device_tracker | presence | presence.device_tracker_phone |
| media_player | energy | energy.media_player_sonos |
| climate | context | context.climate_thermostat |

## Flow

1. **HA Event** → Webhook → Core
2. **NeuronFeeder.feed()** → Synapse Contract Lookup
3. **DynamicNeuronCreator.create_for_entity()** (falls neue Entity)
4. **Brain Graph Update** → Neuron aktiviert
5. **ZonePresenceManager** → Präsenz-Status aktualisiert
6. **AutomationSynapseIntegrator** → Betroffene Automations evaluieren

## Integration mit habitus_zones

```python
from copilot_core.homeassistant.habitus_zones import (
    get_automation_neurons,
    get_zone_synapses
)

# Neuron-IDs für Zonen-Automations
neurons = get_automation_neurons("living")

# Vollständige Synapsen-Map für Zone
synapse_map = get_zone_synapses("living")
```
