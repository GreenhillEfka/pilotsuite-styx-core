# Musikwolke + Sonnenlichtwecker — Konzept (2026-04-06)

## 1. Musikwolke (Smart Audio Follow)

### Prinzip
- **Follow-Modus**: Musikwiedergabe folgt einer Person zwischen Habituszonen
- **Preselected Favorites**: Jede Zone hat bevorzugte Quellen/Playlists
- **Zone-basierte Übergabe**: Beim Betreten einer neuen Zone wird Playback dorthin transferiert

### Architektur
```
Person enters Zone A → Presence Detection → MediaFollowEngine
                                            ↓
                                    Transfer Playback
                                            ↓
                                    SonosHTTPClient → node-sonos-http-api
```

### Bestand (Core)
| File | Status | Notes |
|------|--------|-------|
| `hub/media_follow.py` | ✅ Vorhanden | MediaFollowEngine, PlaybackSession, ZoneMediaState |
| `media_zone_manager.py` | ✅ Vorhanden | start/update/stop_musikwolke(), Session-Management |
| `api/v1/media_zones.py` | ✅ Vollständig | /musikwolke/* Endpoints, Proactive Zone Entry |
| `sonos/client.py` | ✅ Vorhanden | SonosHTTPClient (node-sonos-http-api Wrapper) |
| `sonos/intelligence.py` | ✅ Vorhanden | Time-volume profiles, Fallback-Playlists, Presets |
| `hub/zone_modules/music_config.py` | ✅ Vorhanden | Follow-Mode, Auto-Play, Volume, Fade-Konfiguration |

### Fehlende Konsolidierung
- ❌ Musikwolke-Status nicht im Dashboard sichtbar
- ❌ Keine Zone-spezifischen Favorite-Konfigurationen persistiert
- ❌ Follow-Modus nicht als HA-Entity verfügbar
- ❌ Kein Preset-Management pro Zone

---

## 2. Sonnenlichtwecker (Smart Wake-Up)

### Prinzip
- **Licht-Ramp**: Graduelle Helligkeitssteigerung (10-30 Min vor Weckzeit)
- **Musik-Ramp**: Sanftes Anschwellen von Musik/Radio (zum Weckzeitpunkt)
- **Personen-Zuordnung**: Pro Person mit Zonen-Zuweisung (Schlafzimmer)
- **Smart Snooze**: Via HA Event oder Conversation

### Bestand (Core)
| File | Status | Notes |
|------|--------|-------|
| `alarm/engine.py` | ✅ Vorhanden | AlarmEngine, Scheduler, Licht/Musik-Steuerung |
| `alarm/models.py` | ✅ Vorhanden | AlarmConfig, AlarmRuntime, LightConfig, MusicConfig |
| `alarm/curves.py` | ✅ Vorhanden | Sunrise-Kurven, CCT-Interpolation |
| `hub/wecker.py` | ✅ Vorhanden | Wecker-Modul mit Sonos-Integration |
| `api/v1/wecker.py` | ✅ Vorhanden | REST-API für Alarm-CRUD |

### Fehlende Konsolidierung
- ❌ Wecker nicht als Zone-Modul verfügbar
- ❌ Keine HA-Entities für Alarm-Status
- ❌ Kein Preset-Management (Bedroom, Kids, etc.)
- ❌ Licht-Ramp nicht mit Habituszonen verknüpft

---

## 3. Ziel-Architektur (SOTA)

### Module
```
copilot_core/
├── modules/
│   ├── music_wolke/          ← NEU: Konsolidierte Musikwolke
│   │   ├── engine.py         # MediaFollowEngine + Session-Manager
│   │   ├── zone_favorites.py # Zone-spezifische Favorites
│   │   ├── sonos_adapter.py  # SonosHTTPClient + Intelligence
│   │   └── api.py            # REST + WebSocket Events
│   └── sunrise_alarm/        ← NEU: Konsolidierter Wecker
│       ├── engine.py         # AlarmEngine + Scheduler
│       ├── light_ramp.py     # Licht-Steuerung (HA + Hue)
│       ├── music_ramp.py     # Musik-Steuerung (Sonos)
│       └── api.py            # REST + WebSocket Events
```

### Zone Module Config (erweitern)
```python
# music_config.py — neue Felder
ZoneModuleFieldSpec(key="musikwolke_enabled", ...)
ZoneModuleFieldSpec(key="favorite_source", ...)  # Spotify, TuneIn, etc.
ZoneModuleFieldSpec(key="fallback_playlist", ...)

# sunrise_alarm_config.py — NEU
class SunriseAlarmModuleConfig(ZoneModuleConfig):
    MODULE_ID = "sunrise_alarm"
    get_field_specs() → [
        "enabled", "wake_time", "light_ramp_minutes",
        "music_ramp_minutes", "sonos_room", "favorite",
        "volume_start", "volume_end", "light_entities"
    ]
```

### HA Integration
- `sensor.musikwolke_session_{zone}` — Aktive Session
- `switch.musikwolke_follow_{zone}` — Follow-Modus
- `sensor.alarm_next_{person}` — Nächster Alarm
- `switch.alarm_{alarm_id}` — Alarm ein/aus
- `number.alarm_volume_{alarm_id}` — Lautstärke

### Dashboard Cards (HA Lovelace)
- Musikwolke-Übersicht (alle Zonen mit Playback-Status)
- Follow-Modus Toggle pro Zone
- Wecker-Karte (nächster Alarm + Snooze)
- Zone-Favorites (Quick-Select)

---

## 4. Implementierungsplan

### Phase 1: Musikwolke Konsolidierung
1. `modules/music_wolke/` erstellen
2. `MediaFollowEngine` aus `hub/` migrieren
3. Zone-Favorites persistieren (`/data/music_wolke_favorites.json`)
4. HA-Entities erstellen (`sensor.`, `switch.`)
5. Dashboard-Card `music_wolke_card.py`

### Phase 2: Sonnenlichtwecker Konsolidierung
1. `modules/sunrise_alarm/` erstellen
2. `AlarmEngine` aus `alarm/` migrieren
3. Wecker als Zone-Modul registrieren
4. HA-Entities erstellen
5. Dashboard-Card `sunrise_alarm_card.py`

### Phase 3: API + Config Flow
1. Core-API Endpoints erweitern
2. HA Config Flow für beide Module
3. Zero-Config Integration (wie Habitus Zones)

---

## 5. Offene Fragen
- Musikwolke: Sollen mehrere parallele Sessions möglich sein?
- Wecker: Sollen Licht-Ramp und Musik-Ramp unabhängig steuerbar sein?
- Sonos: Sollen auch andere Player (Spotify Connect, etc.) unterstützt werden?
