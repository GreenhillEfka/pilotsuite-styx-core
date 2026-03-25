# Zone Truth Contract — Slice 2 (2026-03-25)

## Status: IN PROGRESS

## Goal

Zone definitions als **first-class Core truth store** — eine autoritative Quelle
für Zone-Typisierung, Entity→Zone-Mapping, und Modul-Policy.

## Current State (as-is)

### Two parallel implementations (TO BE UNIFIED)

| Location | Class/Module | Role |
|---|---|---|
| `homeassistant/habitus_zones.py` | `ZoneType` (enum), `HabitusZone` (dataclass) | Zone archetype + module overrides |
| `hub/habitus_zones.py` | `RoomConfig`, `HabitusZone` (different!), `HabitusZoneEngine` | Zone instance management + entity adoption |
| `homeassistant/zone_matcher.py` | `ZoneMatcher` | Entity→Zone matching using homeassistant.HabitusZone |
| `api/v1/habitus_zones.py` | `HabitusZoneEngine` from hub | API layer |

### Problem

- Two different `HabitusZone` classes in two different modules
- `ZoneMatcher` uses `homeassistant.HabitusZone` (archetype)
- `HabitusZoneEngine` uses `hub.HabitusZone` (instance)
- No unified Zone Truth Store

## Target Architecture

```
Zone Truth Store (first-class Core store)
├── ZoneDefinitionSyncV1 (TypedModel — archetype)
│   ├── zone_id: str
│   ├── zone_type: ZoneType
│   ├── name: str
│   ├── room_ids: list[str]
│   ├── entity_ids: list[str]
│   ├── enabled_modules: set[str]
│   └── settings: dict
├── ZoneInstanceSyncV1 (TypedModel — runtime instance)
│   ├── zone_id: str
│   ├── mode: str  (active/idle/sleeping/party/away)
│   ├── entities: list[str]
│   └── last_seen: datetime
└── Zone Entity Mapper (ZoneMatcher replacement)
    ├── entity_id → zone_id mapping
    ├── confidence score per mapping
    └── needs_review flag
```

## 10 Standard Zone Types (HabitusZon)

| zoneType | Name DE | Enabled Modules |
|---|---|---|
| living | Wohnbereich | light, motion, music, volume, tv, climate |
| bath | Badbereich | light, motion, climate |
| kitchen | Kochbereich | light, motion, music, volume, climate |
| office | Bürobereich | light, motion, music, volume, climate |
| hallway | Flur/Durchgang | light, motion, camera |
| bedroom | Schlafbereich | light, motion, music, volume, climate |
| room_mira | Kinderzimmer Mira | light, motion, music, volume, climate |
| room_paul | Kinderzimmer Paul | light, motion, music, volume, climate |
| terrace | Terrasse/Balkon | light, motion, music, volume, camera |
| outside | Außenbereich | light, motion, camera |

## API Endpoints

| Endpoint | Method | Role |
|---|---|---|
| `/api/v1/zones` | GET | List all zone definitions |
| `/api/v1/zones/{zone_id}` | GET | Zone detail |
| `/api/v1/zones/{zone_id}` | POST/PATCH | Update zone definition |
| `/api/v1/zones/{zone_id}/entities` | POST | Add entity to zone |
| `/api/v1/zones/{zone_id}/entities/{entity_id}` | DELETE | Remove entity from zone |
| `/api/v1/zones/summary` | GET | Zone overview |
| `/api/v1/habitus/zones/{zone_id}/match` | POST | Manually match room to zone |

## Contract Owner

- **PilotClaw** — Core Zone Truth Store + Hub
- **HomeClaw** — HA→Core zone sync
- **Stxy** — Zone dashboard read models
