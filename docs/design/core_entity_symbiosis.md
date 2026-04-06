# Core Entity Symbiosis: Zonen-Matrize & Entity-Rollen-System

**Status:** Draft / Content Evolution  
**Erstellt:** Content-Evolution-Worker aegis  
**Ziel:** Massiver inhaltlicher Ausbau der Habitus-Zonen und deren semantischer Tiefe  
**Kontext:** PilotSuite Styx Core — Habitus-Zonen Verwaltung

---

## Executive Summary

Dieses Dokument definiert die **vollständige Symbiose** zwischen Home Assistant Entitäten und intelligenten Core-Entitäten (Entity-Roles) innerhalb des PilotSuite Zonen-Systems.

**Kernkonzept:** HA-Entitäten werden nicht kopiert, sondern semantisch aufgeladen — jede Entität erhält im Core eine oder mehrere **Rollen**, die ihr Verhalten in Automationskontexten definieren.

---

## 1. Zonen-Archetypen (ZoneTypes)

Die 10 standardisierten Habituszonen mit ihren semantischen Charakteristiken:

| Zone-Type | Deutsch | Semantischer Kontext | Priorität | Core-Verhalten |
| :--- | :--- | :--- | :--- | :--- |
| `living` | Wohnbereich | Aufenthalts-, Entspannungs-, Sozialbereich | 10 | Ausgewogene Automatisierung, Media-Fokus |
| `bath` | Badbereich | Sanitär-, Hygiene-, Kurzzeit-Aufenthalt | 10 | Diskrete Automatisierung, Privacy-Modus |
| `kitchen` | Kochbereich | Arbeits-, Ess-, Wirtschaftsbereich | 11 | Höchste Priorität (Sicherheit), aktive Automatisierung |
| `office` | Bürobereich | Fokus-, Produktivitäts-, Arbeitsbereich | 8 | Produktivitäts-optimierte Steuerung |
| `hallway` | Gangbereich | Transit-, Verbindungs-, Durchgangszone | 5 | Minimal-invasive, präsenz-getriggerte Steuerung |
| `bedroom` | Schlafbereich | Ruhe-, Regenerations-, Intimbereich | 12 | Maximale Rücksicht, restriktive Media-Regeln |
| `room_mira` | Zimmer Mira | Persönlicher Raum (Kind) | 20 | Personalisierte Regeln, höchste Priorität |
| `room_paul` | Zimmer Paul | Persönlicher Raum (Kind) | 20 | Personalisierte Regeln, höchste Priorität |
| `terrace` | Terrassenbereich | Übergangsbereich Indoor/Outdoor | 8 | Wetter-abhängige Logik |
| `outside` | Aussenbereich | Outdoor, Garten, Garage | 9 | Sicherheits-Fokus, reduzierte Sensitivität |

### Zone-Semantik pro Typ

#### `living` — Der soziale Kern
- **Primary Intent:** Komfort, Geselligkeit, Entspannung
- **Automationscharakter:** Ausgewogen, adaptiv, media-freundlich
- **Besonderheiten:** Musikwolke-Integration, Szenen-Management, Gast-Modus

#### `bath` — Der private Rückzugsort
- **Primary Intent:** Hygiene, Entspannung (Badewanne), Kurzaufenthalt
- **Automationscharakter:** Diskret, schnell, privacy-respektierend
- **Besonderheiten:** Feuchtigkeitsmanagement, Nachtlicht-Modus, keine Kameras

#### `kitchen` — Der aktive Arbeitsbereich
- **Primary Intent:** Zubereitung, Sicherheit, Kommunikation
- **Automationscharakter:** Proaktiv, sicherheitsbewusst, anwesenheits-getriggert
- **Besonderheiten:** Herd-Überwachung, Abzugssteuerung, Timer-Integration

#### `bedroom` — Der regenerative Raum
- **Primary Intent:** Schlaf, Regeneration, Intimität
- **Automationscharakter:** Minimal-invasiv, schlafzyklus-bewusst
- **Besonderheiten:** Kein automatisches Media-Play, sanftes Aufwachen, Schlaf-Tracking

#### `hallway` — Der unsichtbare Verbinder
- **Primary Intent:** Navigation, Sicherheit, Übergang
- **Automationscharakter:** Unauffällig, präsenz-basiert, sofortige Reaktion
- **Besonderheiten:** Nachtlicht-Navigation, Abwesenheits-Erkennung, Einbruchserkennung

---

## 2. Entity-Rollen-System (Entity-Roles)

### 2.1 Rollen-Hierarchie

Jede HA-Entität kann im Core eine oder mehrere Rollen annehmen. Rollen definieren **Verhalten**, nicht nur **Typ**.

| Rolle | Core-Key | Domains | Beschreibung | Verhalten |
| :--- | :--- | :--- | :--- | :--- |
| **Primary Light** | `primary_light` | `light` | Hauptlichtquelle der Zone | Bei Präsenz: primäre Steuerung, volle Helligkeit |
| **Ambient Light** | `ambient_light` | `light` | Ambiente/Akzent-Beleuchtung | Bei Moods: dimmbar, farbig, atmosphärisch |
| **Task Light** | `task_light` | `light` | Arbeitsbeleuchtung | Bei Fokus-Aktivitäten: hell, neutral |
| **Motion Master** | `motion_master` | `binary_sensor` | Primärer Präsenzmelder | PIR/mmWave — triggert Präsenz-Erkennung |
| **Motion Secondary** | `motion_secondary` | `binary_sensor` | Verifizierungs-Sensor | Sekundäre Quelle zur Präsenz-Bestätigung |
| **Ambient Sound** | `ambient_sound` | `media_player` | Primärer Audio-Output | Musikwolke-Ziel, TTS, Ambient-Sounds |
| **Video Display** | `video_display` | `media_player`, `tv` | Primäres Display | TV-Steuerung, Dashboard-Anzeige |
| **Temperature Master** | `temp_master` | `sensor`, `climate` | Referenz-Temperatur | Klimasteuerungs-Input, Trend-Analyse |
| **Humidity Master** | `humidity_master` | `sensor` | Referenz-Feuchtigkeit | Belüftungs-Steuerung, Schimmel-Prävention |
| **Air Quality** | `air_quality` | `sensor` | Luftqualitäts-Sensor | Lüftungs-Empfehlungen, Filter-Status |
| **Window/Door** | `opening_sensor` | `binary_sensor` | Öffnungs-Kontakt | Heizungs-Stop, Alarm, Lüftungs-Trigger |
| **Cover Master** | `cover_master` | `cover` | Primäre Beschattung | Sonnenschutz, Sichtschutz, Nacht-Modus |
| **Safety Sensor** | `safety_sensor` | `binary_sensor` | Sicherheits-relevant | Rauch, CO, Wasser — Alarm-Pfad |
| **Energy Monitor** | `energy_monitor` | `sensor` | Verbrauchs-Messung | Standby-Erkennung, Budget-Tracking |

### 2.2 Rollen-zu-Modul-Mapping

| Modul | Primäre Rollen | Sekundäre Rollen | Trigger-Logik |
| :--- | :--- | :--- | :--- |
| **light** | `primary_light`, `ambient_light`, `task_light` | `motion_master` (als Trigger) | Präsenz + Lux + Tageszeit |
| **motion** | `motion_master`, `motion_secondary` | — | Raw PIR → Fusion-Engine |
| **music** | `ambient_sound` | — | Präsenz + Mood + Follow-Mode |
| **tv** | `video_display` | — | Aktivitäts-basiert, Zeit-gesteuert |
| **climate** | `temp_master`, `humidity_master` | `opening_sensor` (Heizungs-Stop) | Sollwert + Präsenz + Fenster-Status |
| **cover** | `cover_master` | — | Sonnenstand + Lux + Zeit |
| **energy** | `energy_monitor` | — | Standby-Schwelle überschritten |
| **security** | `safety_sensor`, `opening_sensor` | `motion_master` | Alarm-Zustände, Zone-Absicherung |

### 2.3 Multi-Rollen-Entitäten

Einige Entitäten können **mehrere Rollen** gleichzeitig erfüllen:

```python
# Beispiel: Ein smartes Thermostat
entity_id = "climate.wohnzimmer"
roles = ["temp_master", "humidity_master"]  # Kombiniert Temperatur + Feuchtigkeit

# Beispiel: Ein smartes Display
entity_id = "media_player.wohnzimmer_tv"
roles = ["video_display", "ambient_sound"]  # TV + Soundbar-Integration
```

---

## 3. Zonen-Matrize: Erwartete Rollen pro Zone-Type

| Zone-Type | Must-Have | Should-Have | Nice-to-Have |
| :--- | :--- | :--- | :--- |
| **living** | `primary_light`, `motion_master` | `ambient_light`, `ambient_sound`, `temp_master` | `task_light`, `video_display`, `cover_master` |
| **bath** | `primary_light`, `motion_master` | `temp_master`, `humidity_master` | `ambient_light`, `opening_sensor` |
| **kitchen** | `primary_light`, `motion_master`, `safety_sensor` | `ambient_sound`, `temp_master` | `task_light`, `energy_monitor` |
| **office** | `primary_light`, `motion_master` | `task_light`, `temp_master`, `ambient_sound` | `video_display`, `air_quality` |
| **hallway** | `primary_light`, `motion_master` | `ambient_light` | `motion_secondary`, `opening_sensor` |
| **bedroom** | `primary_light`, `motion_master` | `ambient_light`, `temp_master`, `cover_master` | `ambient_sound` (restriktiv) |
| **room_mira** | `primary_light`, `motion_master` | `ambient_light`, `ambient_sound` | `temp_master`, `cover_master` |
| **room_paul** | `primary_light`, `motion_master` | `ambient_light`, `ambient_sound` | `temp_master`, `cover_master` |
| **terrace** | `primary_light`, `motion_master` | `ambient_sound` | `temp_master` |
| **outside** | `primary_light`, `motion_master` | `safety_sensor`, `opening_sensor` | `energy_monitor` |

---

## 4. Implementierungs-Flow: HA → Core → Automation

### 4.1 Discovery Phase

```
HA Areas/Entities
       ↓
[ZoneAutomationController.sync_from_ha()]
       ↓
Entity Classification (Domain → Role)
       ↓
Zone Assignment (Area-Name Matching → ZoneType)
       ↓
Role Detection (detect_entity_role() + TAG_DEFINITIONS)
       ↓
ZoneTruthStore (SSOT)
```

### 4.2 Role Detection Algorithmus

```python
# Pseudocode aus zone_automation.py
def detect_entity_role(entity_id: str, tags: list) -> str | None:
    domain = entity_id.split(".")[0]
    
    # Domain-basiertes Mapping
    if domain == "light":
        if "decken" in entity_id or "haupt" in entity_id:
            return "primary_light"
        return "ambient_light"
    
    if domain == "binary_sensor":
        if "motion" in entity_id or "bewegung" in entity_id:
            return "motion_master"
        if "window" in entity_id or "door" in entity_id:
            return "opening_sensor"
    
    if domain == "media_player":
        if "tv" in entity_id:
            return "video_display"
        return "ambient_sound"
    
    if domain in ["climate", "sensor"]:
        if "temperature" in entity_id or "temperatur" in entity_id:
            return "temp_master"
    
    return None  # Keine eindeutige Rolle erkannt
```

### 4.3 Core-Automation Integration

```python
# Beispiel: Light Module nutzt Rollen
def get_light_entities_for_zone(zone_id: str) -> dict:
    zone = zone_truth_store.get_zone(zone_id)
    
    return {
        "primary": zone.get_entity_by_role("primary_light"),
        "ambient": zone.get_entities_by_role("ambient_light"),
        "task": zone.get_entities_by_role("task_light")
    }

# Steuerung basiert auf Rollen, nicht Entity-IDs
def handle_presence_detected(zone_id: str):
    lights = get_light_entities_for_zone(zone_id)
    
    if lights["primary"]:
        dim_light(lights["primary"], brightness=80)
    
    for ambient in lights["ambient"]:
        dim_light(ambient, brightness=40)
```

---

## 5. API-Contract für PilotClaw

### 5.1 Zone-Definition Sync

**Endpoint:** `POST /api/v1/zone-automation/sync-definitions`

**Request:**
```json
{
  "zones": [
    {
      "zone_id": "zone:living",
      "name": "Wohnzimmer",
      "zone_type": "living",
      "entity_ids": [
        "light.wohnzimmer_hauptlicht",
        "light.wohnzimmer_ambient",
        "binary_sensor.wohnzimmer_motion",
        "media_player.wohnzimmer_soundbar"
      ],
      "entities": {
        "primary_light": "light.wohnzimmer_hauptlicht",
        "ambient_light": "light.wohnzimmer_ambient",
        "motion_master": "binary_sensor.wohnzimmer_motion",
        "ambient_sound": "media_player.wohnzimmer_soundbar"
      }
    }
  ]
}
```

### 5.2 Entity Read-Model

**Endpoint:** `GET /api/v1/zone-automation/zones/{zone_id}/entities/read-model`

**Response:**
```json
{
  "zone_id": "zone:living",
  "revision": 42,
  "entities": [
    {
      "entity_id": "light.wohnzimmer_hauptlicht",
      "role": "primary_light",
      "tags": ["licht", "haupt", "dimmbar"],
      "source": "ha",
      "assigned_at": "2026-04-06T12:00:00Z"
    }
  ]
}
```

---

## 6. Handoff-Checkliste für PilotClaw

- [ ] **Zonen-Typen verstehen:** Die 10 ZoneTypes und ihre Semantik
- [ ] **Rollen-System verstehen:** Entity-Roles vs. HA-Entities
- [ ] **Role Detection:** `detect_entity_role()` Logik implementieren
- [ ] **Zone-Matrize:** Erwartete Rollen pro Zone-Type kennen
- [ ] **API-Contract:** Sync-Endpoints nutzen
- [ ] **Multi-Rollen:** Unterstützung für Entitäten mit mehreren Rollen
- [ ] **UI-Representation:** Rollen im Zone Editor darstellen

---

## 7. Semantische Tiefe: Jenseits der technischen Implementierung

### 7.1 Verhalten als Code

Zonen sind nicht nur Container — sie sind **Verhaltens-Policies**:

```python
# Ein bedroom reagiert anders als ein living:
if zone.zone_type == ZoneType.BEDROOM:
    # Später Abend: Keine Musik-Vorschläge
    # Nacht: Nur rotes Nachtlicht
    # Morgen: Sanftes Aufwecken erlaubt
    pass
elif zone.zone_type == ZoneType.LIVING:
    # Später Abend: Entertainment-Modus
    # Nacht: Abwesenheits-Simulation
    pass
```

### 7.2 Kontext-Awareness

Die Kombination aus Zone-Type + Entity-Roles ermöglicht **kontextuelle Intelligenz**:

- Ein `motion_master` im `hallway` → "Jemand kommt nach Hause"
- Ein `motion_master` im `bedroom` → "Bewegung im Schlafzimmer (Nachtmodus?)"
- Ein `ambient_sound` im `living` → "Musikwolke aktivieren"
- Ein `ambient_sound` im `bedroom` → "Nur wenn explizit gewünscht"

---

## Appendix: Vollständige Rollen-Liste

| Core-Key | Menschen-lesbar | Domain(s) | Icon |
| :--- | :--- | :--- | :--- |
| `primary_light` | Hauptlicht | `light` | `mdi:lightbulb` |
| `ambient_light` | Ambient Licht | `light` | `mdi:lamp` |
| `task_light` | Arbeitslicht | `light` | `mdi:desk-lamp` |
| `motion_master` | Präsenzmelder (Primär) | `binary_sensor` | `mdi:motion-sensor` |
| `motion_secondary` | Präsenzmelder (Sekundär) | `binary_sensor` | `mdi:motion-sensor-outline` |
| `ambient_sound` | Audio-Player | `media_player` | `mdi:speaker` |
| `video_display` | Display/TV | `media_player`, `tv` | `mdi:television` |
| `temp_master` | Temperatur-Referenz | `sensor`, `climate` | `mdi:thermometer` |
| `humidity_master` | Feuchtigkeits-Referenz | `sensor` | `mdi:water-percent` |
| `air_quality` | Luftqualität | `sensor` | `mdi:air-filter` |
| `opening_sensor` | Fenster/Tür-Kontakt | `binary_sensor` | `mdi:door-open` |
| `cover_master` | Beschattung | `cover` | `mdi:blinds` |
| `safety_sensor` | Sicherheits-Sensor | `binary_sensor` | `mdi:shield-alert` |
| `energy_monitor` | Energie-Messung | `sensor` | `mdi:flash` |

---

**Success Signal:** Dokument vollständig. PilotClaw kann mit Implementierung beginnen.
