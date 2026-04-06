# SYMBIOTIC ENTITY SPEC: ROOM_CONTEXT (SL-002)

## 1. Identität
- **ID:** `context.living_room.evening`, `context.bedroom.sleep`
- **Core-Anker:** `copilot_core/entities/room_context.py`

## 2. Symbiotische Verknüpfung
- **Auslöser:** Zeit + Präsenz + Habitualisierung
- **HA-Shadow:** Aktiviert Szenen (scene.living_room_evening)
- **Neuron-Link:** Lernt aus manuellen Korrekturen

## 3. Datenmodell
```json
{
  "context_id": "string",
  "zone_ref": "zone.living_room",
  "triggers": {"time": "20:00", "presence": "detected"},
  "actions": ["light.dim", "media.play_chill"],
  "learned": true
}
```
