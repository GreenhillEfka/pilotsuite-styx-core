# SYMBIOTIC ENTITY SPEC: DEVICE_LINK (SL-003)

## 1. Identität
- **ID:** `device.light.living_room`, `device.media_player.bedroom`
- **Core-Anker:** `copilot_core/entities/device_link.py`

## 2. Symbiotische Verknüpfung
- **HA-Shadow:** Spiegelt HA entity_id, fügt Core-Metadaten hinzu
- **Capabilities:** Deklariert was das Gerät kann (dim, color, play, pause)
- **State-Cache:** Core hält letzte bekannte Zustände für Offline-Betrieb

## 3. Datenmodell
```json
{
  "link_id": "device.light.living_room",
  "ha_entity_id": "light.living_room",
  "capabilities": ["on_off", "brightness", "color_temp"],
  "last_state": {"state": "on", "brightness": 200},
  "linked_zone": "zone.living_room"
}
```
