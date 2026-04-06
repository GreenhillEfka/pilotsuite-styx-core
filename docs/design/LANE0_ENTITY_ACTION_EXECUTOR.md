# SYMBIOTIC ENTITY SPEC: ACTION_EXECUTOR (SL-005)

## 1. Identität
- **ID:** `action.lights_on`, `action.set_temperature`
- **Core-Anker:** `copilot_core/entities/action_executor.py`

## 2. Symbiotische Verknüpfung
- **Eingabe:** Intent-Resolution oder Automation-Trigger
- **Ausführung:** Mapped zu HA Service Calls via Device Links
- **Rollback:** Speichert vorherigen Zustand für Undo

## 3. Datenmodell
```json
{
  "action_id": "action.living_room_cozy",
  "target_devices": ["device.light.living", "device.media_player.sonos"],
  "commands": [
    {"device": "light.living", "service": "light.turn_on", "data": {"brightness": 50}},
    {"device": "media_player.sonos", "service": "media_player.play_media", "data": {"media_id": "spotify:playlist:chill"}}
  ],
  "undo_state": [{"device": "light.living", "state": "off"}]
}
```
