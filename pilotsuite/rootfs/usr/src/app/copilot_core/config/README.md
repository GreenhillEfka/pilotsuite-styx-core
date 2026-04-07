# Cross-Module Configuration

Zentrale Konfigurationsschicht für module-übergreifende Integrationen in der PilotSuite.

## Problem

Bisher hatten Module wie **Sonos**, **Wecker**, **Mood**, **Habitus**, und **Praesenz**各自 eigene Konfigurationen für:
- Zone-Zuordnungen
- Entity-Listen (Lights, Motion, Media)
- Sonos-Room-Mappings
- Alarm-Einstellungen

**Folgen:**
- Redundante Konfigurationen
- Konflikte bei Änderungen
- Keine zentrale Übersicht
- Schwierige Integration neuer Features

## Lösung

`cross_module.py` bietet:

1. **Unified Zone Registry** — Single Source of Truth für alle Zonen
2. **Auto-Discovery** — Erkennt Entities aus HA Area Registry
3. **Conflict Detection** — Findet Konflikte automatisch
4. **Smart Defaults** — Schlägt sinnige Voreinstellungen vor
5. **Persistence** — Speichert Konfiguration in HA Storage

## Usage

```python
from copilot_core.config.cross_module import async_get_cross_module_config

# In Module Setup
async def async_setup_entry(ctx: ModuleContext) -> bool:
    config = await async_get_cross_module_config(ctx.hass)
    
    # Get zone config
    zone = config.get_zone("wohnbereich")
    if zone:
        sonos_room = zone.sonos.room_name
        light_entities = zone.light.entities
        motion_entities = zone.presence.motion_entities

# Check for conflicts
conflicts = config.get_conflicts()
for conflict in conflicts:
    if conflict.severity == "error":
        _LOGGER.error("Conflict: %s", conflict.description)
```

## Module Integration

### Sonos Module
```python
# Old: Each module had its own zone_speaker_map
# New: Use cross-module config
zone = config.get_zone(zone_id)
sonos_room = zone.sonos.room_name
```

### Wecker (Alarm) Module
```python
# Access unified alarm config
zone = config.get_zone("schlafzimmer")
if zone.alarm.enabled:
    # Use zone.sonos for wake-up music
    # Use zone.light for light ramp
```

### Mood Module
```python
# Get mood-relevant entities
zone = config.get_zone(zone_id)
motion_entities = zone.presence.motion_entities
media_entities = zone.mood.media_entities
```

### Habitus Miner
```python
# Use unified zone definitions for pattern mining
zones = config.get_all_zones()
for zone in zones:
    # Consistent entity lists across all modules
    entities = zone.light.entities + zone.presence.motion_entities
```

## Conflict Detection

Erkannte Konflikte:

| Konflikt | Severity | Modules | Beschreibung |
|----------|----------|---------|--------------|
| Sonos room mapped to multiple zones | warning | sonos, wecker, mood | Gleicher Sonos-Room in mehreren Zonen |
| Light entity in multiple zones | info | licht, wecker, mood | Geteilte Beleuchtung (kann intentional sein) |
| Motion entity in multiple zones | warning | praesenz, habitus, mood | Motion-Sensor覆盖 mehrere Zonen |
| Alarm enabled without Sonos | warning | wecker, sonos | Alarm aktiv aber kein Sonos konfiguriert |
| Mood enabled without motion | warning | mood, praesenz | Mood-Inferenz ohne Motion-Sensoren |

## Smart Defaults

Automatisch angewendete Defaults:

- **Mood enabled** → Wenn Motion-Sensoren vorhanden
- **Alarm enabled** → Wenn Sonos-Room konfiguriert
- **Light ramp** → Verknüpft mit Alarm wenn nicht gesetzt

## Architecture

```
copilot_core/config/
├── __init__.py              # Exports
├── cross_module.py          # Main config layer
└── tests/
    └── test_cross_module_config.py
```

## Persistence

Configuration wird gespeichert in:
```
HA_STORAGE/cross_module_config.json
```

Format:
```json
{
  "zones": [
    {
      "zone_id": "area_wohnbereich",
      "zone_name": "Wohnbereich",
      "sonos": {"room_name": "Wohnzimmer", ...},
      "light": {"entities": [...], ...},
      "presence": {"motion_entities": [...], ...},
      "alarm": {"enabled": true, ...},
      "mood": {"enabled": true, ...}
    }
  ],
  "updated": "2026-04-06T22:00:00Z"
}
```

## Migration

Für bestehende Module:

1. **Sonos Module** → Migrate `zone_speaker_map` to `zone.sonos.room_name`
2. **Wecker** → Use `zone.alarm` and `zone.sonos` for wake-up config
3. **Mood** → Use `zone.mood` and `zone.presence` for sensor config
4. **Habitus** → Use `config.get_all_zones()` for consistent zone definitions

## Next Steps

- [ ] Integration in bestehende Module (sonos_module, mood_module, wecker)
- [ ] UI für Konfiguration (Dashboard Card)
- [ ] CLI commands für Conflict-Check
- [ ] Auto-Remediation für einfache Konflikte
