# SYMBIOTIC ENTITY SPEC: EVENT_BUS (SL-008)

## 1. Identität
- **ID:** `event.user_entered`, `event.device_state_changed`
- **Core-Anker:** `copilot_core/entities/event_bus.py`

## 2. Symbiotische Verknüpfung
- **Publiziert:** HA Events + Core-Interne Events
- **Subscribtions:** Entitäten können auf Events lauschen
- **Persistent:** Event-Log für Debugging und Replay

## 3. Datenmodell
```json
{
  "event_id": "uuid",
  "event_type": "user_entered",
  "payload": {"zone": "living_room", "user": "andreas"},
  "timestamp": "2026-04-06T12:00:00Z",
  "subscribers": ["context.living_room", "automation.welcome_home"]
}
```
