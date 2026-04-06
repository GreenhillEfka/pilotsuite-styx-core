# MUSIKWOLKE SOTA SPEC — Smart Audio Follow (Slice 162)

**Status:** Draft / SOTA Specification
**Target:** pilot-suite-styx-core
**Module ID:** `music` / `musikwolke`

## 1. Overview
Die Musikwolke realisiert ein nahtloses Audio-Erlebnis, bei dem die Wiedergabe (Musik, Radio, Podcast) einer Person intelligent durch das Haus folgt (Follow-Mode) oder zonen-spezifisch bei Präsenz startet. Sie integriert Sonos-Hardware über die `MusikwolkeBridge` direkt in das Habitus-Zonensystem.

## 2. Habitus-Integration (Slice 162)
Die Musikwolke wird als primäres Habitus-Modul geführt. Jede Zone besitzt eine dedizierte `MusicModuleConfig`.

### 2.1 Zone-Speaker-Mapping
- Jede Habitus-Zone (`zone_id`) wird einem oder mehreren Sonos-Räumen zugeordnet.
- Speicherung erfolgt in der `MusikwolkeBridge` (persistiert in `/data/musikwolke_bridge.json`).
- Automatisches Mapping über Namensähnlichkeit (Auto-Discovery).

### 2.2 Per-Zone Konfiguration
Die Konfiguration erfolgt über `ZoneModuleRegistry` und ist per API/UI einstellbar:
- `enabled` (bool): Modul für diese Zone aktiv.
- `presence_auto_play` (bool): Startet Musik bei Betreten der Zone (nach Delay).
- `presence_delay_s` (int): Verzögerung vor Start bei Präsenz.
- `absence_pause_s` (int): Verzögerung vor Pause bei Abwesenheit.
- `follow_mode` (bool): Playback folgt der Person in diese Zone.
- `default_volume_pct` (int): Standard-Lautstärke beim Betreten.
- `fade_duration_s` (int): Cross-fade Zeit beim Zonenwechsel.
- `favorite_name` (str): Preselected Favorite (Sonos) für diese Zone.

## 3. Data Model
### 3.1 PlaybackSession (MediaFollowEngine)
```python
@dataclass
class PlaybackSession:
    session_id: str
    person_id: str          # Verknüpfung mit Person für Follow-Mode
    source_entity: str      # Aktueller Speaker
    zone_id: str            # Aktuelle Zone
    media_type: str         # music, radio, etc.
    state: str              # playing, paused
    follow_enabled: bool    # Ob Session aktiv folgen darf
```

## 4. API Contracts

### 4.1 Modul-Konfiguration
`GET /api/v1/zone-automation/zones/<zone_id>/modules/music`
`POST /api/v1/zone-automation/zones/<zone_id>/modules/music`
**Payload:**
```json
{
  "enabled": true,
  "follow_mode": true,
  "favorite_name": "Chillout Radio",
  "default_volume_pct": 35
}
```

### 4.2 Musikwolke Control
`POST /api/v1/musikwolke/create` — Gruppe über mehrere Zonen bilden.
`POST /api/v1/musikwolke/dissolve` — Gruppe auflösen.
`POST /api/v1/media/musikwolke/start` — Follow-Session für Person starten.
`GET /api/v1/musikwolke/status` — Globaler Status aller Zonen und Sessions.

## 5. UI Integration (Lovelace)

### 5.1 Musikwolke-Steuerung
- **Card-Typ:** `custom:styx-musikwolke-card`
- **Features:** 
  - Visualisierung aktiver Follow-Sessions (Person -> Zone).
  - Quick-Toggle für Follow-Mode pro Zone.
  - Auswahl der Zone-Favorites.
  - Visualisierung der Sonos-Gruppen-Topologie.

### 5.2 HA Entities
- `switch.musikwolke_follow_<zone_id>`: Direktes Schalten des Follow-Modes.
- `select.musikwolke_favorite_<zone_id>`: Auswahl des Preselected Favorites.
- `sensor.musikwolke_active_session`: Zeigt an, wer gerade verfolgt wird.

## 6. Success Signal
- [ ] Musik startet in Zone B, wenn Person A von Zone A nach B wechselt (Cross-fade aktiv).
- [ ] Zone-Favorites sind über die UI einstellbar und werden korrekt geladen.
- [ ] Das Zone-Speaker-Mapping überlebt einen Core-Neustart.
