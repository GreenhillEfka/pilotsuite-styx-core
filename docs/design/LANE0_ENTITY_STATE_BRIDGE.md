# SYMBIOTIC ENTITY SPEC: STATE_BRIDGE (SL-006)

## 1. Identität
- **ID:** `state.living_room.lights`, `state.bedroom.climate`
- **Core-Anker:** `copilot_core/entities/state_bridge.py`

## 2. Symbiotische Verknüpfung
- **HA-Shadow:** Spiegelt HA entity states
- **Core-Cache:** Hält Zustände für Offline/History
- **Sync-Trigger:** Publiziert Änderungen an Listener (Automationen)

## 3. Datenmodell
```json
{
  "state_id": "state.living_room.lights",
  "entity_ref": "device.light.living_room",
  "current": {"state": "on", "attributes": {"brightness": 200}},
  "history": [{"at": "2026-04-06T12:00:00Z", "state": "off"}],
  "subscribers": ["automation.evening_mode", "context.living_room"]
}
```
