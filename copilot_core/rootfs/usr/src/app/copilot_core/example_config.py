"""
Example Configuration for PilotSuite after Zero-Config Setup.

Provides a realistic example configuration based on a typical German household
with 10 Habitus zones, Sonos speakers, Hue lights, motion sensors, climate
controls, media players, switches, covers, locks, energy sensors, cameras,
playlists, birthdays, todos, and notifications.

This file serves as:
1. Reference documentation for the expected entity structure
2. Seed data for demo/test environments
3. Blueprint for new installations
"""

from __future__ import annotations

from typing import Any, Dict, List


# ═══════════════════════════════════════════════════════════════════════════
# Zone → Entity Mapping (nach Zero-Config Auto-Discovery)
# ═══════════════════════════════════════════════════════════════════════════

EXAMPLE_ZONE_ENTITIES: Dict[str, Dict[str, List[str]]] = {
    "living": {
        "lights": [
            "light.wohnzimmer_decke",
            "light.wohnzimmer_stehlampe",
            "light.wohnzimmer_tv_hintergrund",
            "light.esstisch_pendel",
        ],
        "motion": [
            "binary_sensor.wohnzimmer_praesenz",
            "binary_sensor.wohnzimmer_bewegung",
        ],
        "media": [
            "media_player.sonos_wohnzimmer",
            "media_player.sonos_sub_wohnzimmer",
            "media_player.tv_wohnzimmer",
        ],
        "climate": [
            "climate.wohnzimmer_thermostat",
            "sensor.wohnzimmer_temperatur",
            "sensor.wohnzimmer_luftfeuchtigkeit",
        ],
        "sensors": [
            "sensor.wohnzimmer_co2",
            "sensor.wohnzimmer_helligkeit",
            "binary_sensor.wohnzimmer_fenster",
        ],
        "cover": [
            "cover.wohnzimmer_rollladen_links",
            "cover.wohnzimmer_rollladen_rechts",
        ],
        "switches": [
            "switch.wohnzimmer_steckdose_tv",
            "switch.wohnzimmer_steckdose_stehlampe",
        ],
        "energy": [
            "sensor.wohnzimmer_verbrauch_kwh",
            "sensor.tv_verbrauch_watt",
        ],
        "cameras": [
            "camera.wohnzimmer_overview",
        ],
    },

    "kitchen": {
        "lights": [
            "light.kueche_decke",
            "light.kueche_arbeitsplatte",
            "light.kueche_essbar",
        ],
        "motion": [
            "binary_sensor.kueche_bewegung",
        ],
        "media": [
            "media_player.sonos_kueche",
        ],
        "climate": [
            "climate.kueche_thermostat",
            "sensor.kueche_temperatur",
        ],
        "sensors": [
            "sensor.kueche_helligkeit",
            "binary_sensor.kueche_fenster",
            "sensor.kueche_luftqualitaet",
        ],
        "switches": [
            "switch.kaffeemaschine",
            "switch.spuelmaschine",
            "switch.kueche_steckdose_arbeitsplatte",
        ],
        "energy": [
            "sensor.spuelmaschine_verbrauch",
            "sensor.kuehlschrank_verbrauch",
            "sensor.kaffeemaschine_verbrauch",
            "sensor.kueche_gesamt_kwh",
        ],
    },

    "bath": {
        "lights": [
            "light.bad_decke",
            "light.bad_spiegel",
        ],
        "motion": [
            "binary_sensor.bad_praesenz",
        ],
        "media": [
            "media_player.sonos_bad",
        ],
        "climate": [
            "climate.bad_fussbodenheizung",
            "sensor.bad_temperatur",
            "sensor.bad_luftfeuchtigkeit",
        ],
        "sensors": [
            "binary_sensor.bad_fenster",
            "binary_sensor.bad_wassermelder",
        ],
        "switches": [
            "switch.bad_luefter",
            "switch.bad_handtuchheizung",
        ],
        "fans": [
            "fan.bad_abluft",
        ],
    },

    "hallway": {
        "lights": [
            "light.flur_decke",
            "light.flur_garderobe",
            "light.treppenhaus",
        ],
        "motion": [
            "binary_sensor.flur_bewegung",
            "binary_sensor.eingang_bewegung",
        ],
        "sensors": [
            "binary_sensor.haustuer",
        ],
        "locks": [
            "lock.haustuer_schloss",
        ],
        "switches": [
            "switch.flur_steckdose",
        ],
        "cameras": [
            "camera.eingang_klingel",
        ],
    },

    "bedroom": {
        "lights": [
            "light.schlafzimmer_decke",
            "light.schlafzimmer_nachttisch_links",
            "light.schlafzimmer_nachttisch_rechts",
        ],
        "motion": [
            "binary_sensor.schlafzimmer_praesenz",
        ],
        "media": [
            "media_player.sonos_schlafzimmer",
        ],
        "climate": [
            "climate.schlafzimmer_thermostat",
            "sensor.schlafzimmer_temperatur",
            "sensor.schlafzimmer_luftfeuchtigkeit",
            "sensor.schlafzimmer_co2",
        ],
        "cover": [
            "cover.schlafzimmer_rollladen",
        ],
        "switches": [
            "switch.schlafzimmer_steckdose_links",
            "switch.schlafzimmer_steckdose_rechts",
        ],
        "fans": [
            "fan.schlafzimmer_ventilator",
        ],
    },

    "office": {
        "lights": [
            "light.buero_decke",
            "light.buero_schreibtisch",
            "light.buero_bildschirm_bias",
        ],
        "motion": [
            "binary_sensor.buero_praesenz",
        ],
        "media": [
            "media_player.sonos_buero",
        ],
        "climate": [
            "climate.buero_thermostat",
            "sensor.buero_temperatur",
            "sensor.buero_co2",
        ],
        "sensors": [
            "sensor.buero_helligkeit",
            "binary_sensor.buero_fenster",
        ],
        "switches": [
            "switch.buero_monitor",
            "switch.buero_drucker",
            "switch.buero_steckdose_schreibtisch",
        ],
        "energy": [
            "sensor.buero_pc_verbrauch_watt",
            "sensor.buero_gesamt_kwh",
        ],
    },

    "room_mira": {
        "lights": [
            "light.mira_decke",
            "light.mira_nachtlicht",
            "light.mira_schreibtisch",
        ],
        "motion": [
            "binary_sensor.mira_bewegung",
        ],
        "media": [
            "media_player.sonos_mira",
        ],
        "climate": [
            "climate.mira_thermostat",
            "sensor.mira_temperatur",
        ],
        "cover": [
            "cover.mira_rollladen",
        ],
        "switches": [
            "switch.mira_steckdose",
        ],
    },

    "room_paul": {
        "lights": [
            "light.paul_decke",
            "light.paul_nachtlicht",
            "light.paul_schreibtisch",
        ],
        "motion": [
            "binary_sensor.paul_bewegung",
        ],
        "media": [
            "media_player.sonos_paul",
        ],
        "climate": [
            "climate.paul_thermostat",
            "sensor.paul_temperatur",
        ],
        "cover": [
            "cover.paul_rollladen",
        ],
        "switches": [
            "switch.paul_steckdose",
            "switch.paul_gaming_pc",
        ],
        "energy": [
            "sensor.paul_pc_verbrauch_watt",
        ],
    },

    "terrace": {
        "lights": [
            "light.terrasse_aussen",
            "light.terrasse_lichterkette",
            "light.terrasse_spots",
        ],
        "motion": [
            "binary_sensor.terrasse_bewegung",
        ],
        "media": [
            "media_player.sonos_terrasse",
        ],
        "sensors": [
            "sensor.terrasse_temperatur",
            "sensor.terrasse_helligkeit",
            "binary_sensor.terrasse_tuer",
        ],
        "switches": [
            "switch.terrasse_markise",
            "switch.terrasse_heizstrahler",
        ],
        "cover": [
            "cover.terrasse_markise",
        ],
    },

    "outside": {
        "lights": [
            "light.garten_einfahrt",
            "light.garten_weg",
            "light.garten_terrassenrand",
        ],
        "motion": [
            "binary_sensor.einfahrt_bewegung",
            "binary_sensor.garten_bewegung",
        ],
        "sensors": [
            "sensor.wetter_temperatur",
            "sensor.wetter_luftfeuchtigkeit",
            "sensor.wetter_wind",
            "sensor.wetter_regen_mm",
            "sensor.wetter_uv_index",
        ],
        "switches": [
            "switch.garagentor",
            "switch.bewaesserung",
            "switch.pool_pumpe",
        ],
        "cameras": [
            "camera.garten_uebersicht",
            "camera.einfahrt",
        ],
        "energy": [
            "sensor.pv_erzeugung_watt",
            "sensor.pv_einspeisung_kwh",
            "sensor.pv_eigenverbrauch_kwh",
            "sensor.hausstrom_verbrauch_watt",
            "sensor.batterie_ladezustand_pct",
        ],
    },
}


# ═══════════════════════════════════════════════════════════════════════════
# Musikwolke (Sonos) Zone-Player-Mapping
# ═══════════════════════════════════════════════════════════════════════════

EXAMPLE_SONOS_PLAYERS: Dict[str, Dict[str, Any]] = {
    "living": {
        "primary": "media_player.sonos_wohnzimmer",
        "secondary": ["media_player.sonos_sub_wohnzimmer"],
        "group_name": "Wohnzimmer Gruppe",
        "model": "Sonos Five",
    },
    "kitchen": {
        "primary": "media_player.sonos_kueche",
        "secondary": [],
        "group_name": "Kueche",
        "model": "Sonos One",
    },
    "bath": {
        "primary": "media_player.sonos_bad",
        "secondary": [],
        "group_name": "Bad",
        "model": "Sonos One SL",
    },
    "bedroom": {
        "primary": "media_player.sonos_schlafzimmer",
        "secondary": [],
        "group_name": "Schlafzimmer",
        "model": "Sonos Era 100",
    },
    "office": {
        "primary": "media_player.sonos_buero",
        "secondary": [],
        "group_name": "Buero",
        "model": "Sonos One",
    },
    "room_mira": {
        "primary": "media_player.sonos_mira",
        "secondary": [],
        "group_name": "Mira",
        "model": "Sonos Roam",
    },
    "room_paul": {
        "primary": "media_player.sonos_paul",
        "secondary": [],
        "group_name": "Paul",
        "model": "Sonos Roam",
    },
    "terrace": {
        "primary": "media_player.sonos_terrasse",
        "secondary": [],
        "group_name": "Terrasse",
        "model": "Sonos Move 2",
    },
}


# ═══════════════════════════════════════════════════════════════════════════
# Playlists & Favoriten (Sonos/Musikwolke)
# ═══════════════════════════════════════════════════════════════════════════

EXAMPLE_PLAYLISTS: List[Dict[str, Any]] = [
    {
        "id": "pl_morgen_energie",
        "name": "Morgen-Energie",
        "source": "spotify",
        "uri": "spotify:playlist:37i9dQZF1DX3rxVfibe1L0",
        "icon": "mdi:weather-sunny",
        "zone_affinity": ["kitchen", "bath"],
        "time_affinity": "morning",
        "track_count": 45,
    },
    {
        "id": "pl_konzentration",
        "name": "Deep Focus",
        "source": "spotify",
        "uri": "spotify:playlist:37i9dQZF1DWZeKCadgRdKQ",
        "icon": "mdi:head-lightbulb",
        "zone_affinity": ["office"],
        "time_affinity": "day",
        "track_count": 120,
    },
    {
        "id": "pl_abend_chill",
        "name": "Abend Chill",
        "source": "spotify",
        "uri": "spotify:playlist:37i9dQZF1DX4sWSpwq3LiO",
        "icon": "mdi:candle",
        "zone_affinity": ["living", "bedroom"],
        "time_affinity": "evening",
        "track_count": 80,
    },
    {
        "id": "pl_kinder_hits",
        "name": "Kinder-Hits",
        "source": "spotify",
        "uri": "spotify:playlist:37i9dQZF1DX6z20IXmBjWI",
        "icon": "mdi:music-note-eighth",
        "zone_affinity": ["room_mira", "room_paul"],
        "time_affinity": "day",
        "track_count": 60,
    },
    {
        "id": "pl_garten_party",
        "name": "Gartenparty",
        "source": "spotify",
        "uri": "spotify:playlist:37i9dQZF1DXaXB8fQg7xif",
        "icon": "mdi:grill",
        "zone_affinity": ["terrace", "outside"],
        "time_affinity": "day",
        "track_count": 55,
    },
    {
        "id": "pl_einschlaf",
        "name": "Einschlafmusik",
        "source": "spotify",
        "uri": "spotify:playlist:37i9dQZF1DWZd79rJ6a7lp",
        "icon": "mdi:weather-night",
        "zone_affinity": ["bedroom", "room_mira", "room_paul"],
        "time_affinity": "night",
        "track_count": 35,
    },
    {
        "id": "pl_radio_swr3",
        "name": "SWR3 Radio",
        "source": "tunein",
        "uri": "x-rincon-mp3radio://swr3.de/stream",
        "icon": "mdi:radio",
        "zone_affinity": ["kitchen", "bath"],
        "time_affinity": "morning",
    },
    {
        "id": "pl_kochen",
        "name": "Kochen & Geniessen",
        "source": "spotify",
        "uri": "spotify:playlist:37i9dQZF1DX0BcQWzuB7ZO",
        "icon": "mdi:pot-steam",
        "zone_affinity": ["kitchen"],
        "time_affinity": "evening",
        "track_count": 70,
    },
]

EXAMPLE_SONOS_FAVORITES: List[Dict[str, str]] = [
    {"name": "SWR3", "uri": "x-rincon-mp3radio://swr3.de/stream", "type": "radio"},
    {"name": "Deutschlandfunk", "uri": "x-rincon-mp3radio://dradio.de/dlf", "type": "radio"},
    {"name": "Jazz FM", "uri": "x-rincon-mp3radio://jazzfm.com/stream", "type": "radio"},
    {"name": "Liked Songs", "uri": "spotify:collection:tracks", "type": "playlist"},
]


# ═══════════════════════════════════════════════════════════════════════════
# Haushalt — Personen, Geburtstage, Device-Tracker
# ═══════════════════════════════════════════════════════════════════════════

EXAMPLE_HOUSEHOLD: List[Dict[str, Any]] = [
    {
        "person_id": "person.papa",
        "name": "Papa",
        "role": "adult",
        "birthday": "1985-06-14",
        "device_trackers": [
            "device_tracker.papa_iphone",
            "device_tracker.papa_watch",
        ],
        "preferred_zones": ["office", "living"],
        "wake_time": "06:30",
        "sleep_time": "22:30",
    },
    {
        "person_id": "person.mama",
        "name": "Mama",
        "role": "adult",
        "birthday": "1987-03-22",
        "device_trackers": [
            "device_tracker.mama_iphone",
        ],
        "preferred_zones": ["kitchen", "living"],
        "wake_time": "06:15",
        "sleep_time": "22:00",
    },
    {
        "person_id": "person.mira",
        "name": "Mira",
        "role": "child",
        "birthday": "2015-11-08",
        "device_trackers": [
            "device_tracker.mira_tablet",
        ],
        "preferred_zones": ["room_mira", "living"],
        "wake_time": "07:00",
        "sleep_time": "20:30",
    },
    {
        "person_id": "person.paul",
        "name": "Paul",
        "role": "child",
        "birthday": "2018-04-25",
        "device_trackers": [
            "device_tracker.paul_tablet",
        ],
        "preferred_zones": ["room_paul", "living"],
        "wake_time": "07:00",
        "sleep_time": "20:00",
    },
]


# ═══════════════════════════════════════════════════════════════════════════
# Todos — Aufgabenlisten pro Zone oder Haushalt
# ═══════════════════════════════════════════════════════════════════════════

EXAMPLE_TODOS: List[Dict[str, Any]] = [
    {
        "id": "todo_001",
        "title": "Rauchmelder Batterie pruefen",
        "zone_id": "hallway",
        "priority": "high",
        "due_date": "2026-04-01",
        "category": "maintenance",
        "status": "pending",
        "assigned_to": "Papa",
    },
    {
        "id": "todo_002",
        "title": "Filter Dunstabzugshaube wechseln",
        "zone_id": "kitchen",
        "priority": "medium",
        "due_date": "2026-03-20",
        "category": "maintenance",
        "status": "pending",
        "assigned_to": "Mama",
    },
    {
        "id": "todo_003",
        "title": "Rollladen Service (jaehrlich)",
        "zone_id": "living",
        "priority": "low",
        "due_date": "2026-06-15",
        "category": "maintenance",
        "status": "pending",
    },
    {
        "id": "todo_004",
        "title": "Garten winterfest machen",
        "zone_id": "outside",
        "priority": "medium",
        "due_date": "2026-10-30",
        "category": "seasonal",
        "status": "pending",
        "assigned_to": "Papa",
    },
    {
        "id": "todo_005",
        "title": "Sonos Firmware Update",
        "zone_id": "_global",
        "priority": "low",
        "due_date": None,
        "category": "tech",
        "status": "completed",
    },
    {
        "id": "todo_006",
        "title": "Terrasse Lichterkette reparieren",
        "zone_id": "terrace",
        "priority": "medium",
        "due_date": "2026-04-15",
        "category": "maintenance",
        "status": "pending",
        "assigned_to": "Papa",
    },
    {
        "id": "todo_007",
        "title": "Kinderzimmer aufraeuemen (Mira)",
        "zone_id": "room_mira",
        "priority": "medium",
        "due_date": "2026-03-15",
        "category": "household",
        "status": "pending",
        "assigned_to": "Mira",
    },
    {
        "id": "todo_008",
        "title": "PV-Anlage Reinigung",
        "zone_id": "outside",
        "priority": "low",
        "due_date": "2026-05-01",
        "category": "maintenance",
        "status": "pending",
        "estimated_cost_eur": 150.0,
    },
]


# ═══════════════════════════════════════════════════════════════════════════
# Nachrichten / Notifications (Zone-spezifisch)
# ═══════════════════════════════════════════════════════════════════════════

EXAMPLE_NOTIFICATIONS: List[Dict[str, Any]] = [
    {
        "id": "notif_001",
        "title": "Fenster offen bei Regen",
        "message": "Kueche Fenster ist offen, es regnet draussen!",
        "zone_id": "kitchen",
        "severity": "warning",
        "channel": "push",
        "created_at": "2026-03-11T08:30:00Z",
        "acknowledged": False,
    },
    {
        "id": "notif_002",
        "title": "Heizung Eco-Modus",
        "message": "Schlafzimmer Heizung wurde auf Eco umgestellt (niemand anwesend).",
        "zone_id": "bedroom",
        "severity": "info",
        "channel": "display",
        "created_at": "2026-03-11T09:15:00Z",
        "acknowledged": True,
    },
    {
        "id": "notif_003",
        "title": "Wassermelder Bad",
        "message": "Wassermelder im Bad hat Feuchtigkeit erkannt!",
        "zone_id": "bath",
        "severity": "critical",
        "channel": "push",
        "created_at": "2026-03-11T10:00:00Z",
        "acknowledged": False,
    },
    {
        "id": "notif_004",
        "title": "PV-Ueberschuss",
        "message": "3.2 kW PV-Ueberschuss — Spuelmaschine starten empfohlen.",
        "zone_id": "outside",
        "severity": "info",
        "channel": "display",
        "created_at": "2026-03-11T12:00:00Z",
        "acknowledged": False,
    },
    {
        "id": "notif_005",
        "title": "Geburtstag morgen",
        "message": "Morgen ist Miras Geburtstag! Kuchen backen nicht vergessen.",
        "zone_id": "_global",
        "severity": "info",
        "channel": "push",
        "created_at": "2026-11-07T08:00:00Z",
        "acknowledged": False,
    },
    {
        "id": "notif_006",
        "title": "CO2-Warnung Buero",
        "message": "CO2 im Buero bei 1200 ppm — bitte lueften!",
        "zone_id": "office",
        "severity": "warning",
        "channel": "tts",
        "created_at": "2026-03-11T14:30:00Z",
        "acknowledged": False,
    },
]


# ═══════════════════════════════════════════════════════════════════════════
# Example Automation Suggestions (nach 7 Tagen Lernphase)
# ═══════════════════════════════════════════════════════════════════════════

EXAMPLE_SUGGESTIONS: List[Dict[str, Any]] = [
    {
        "id": "sug_morning_kitchen",
        "title": "Morgenlicht Kueche",
        "description": "Werktags 06:45: Kuechenlicht auf 80% + Kaffeemaschine an",
        "pattern": "time:06:45:workday -> light.kueche_decke:80% + switch.kaffeemaschine:on",
        "confidence": 0.92,
        "support": 14,
        "category": "comfort",
        "zone_id": "kitchen",
        "mood_type": "active",
        "risk_level": "low",
    },
    {
        "id": "sug_tv_dimm",
        "title": "TV-Modus Wohnzimmer",
        "description": "Wenn TV an: Wohnzimmerlicht auf 30%, Rolllaeden zu",
        "pattern": "media_player.tv_wohnzimmer:playing -> light.wohnzimmer_decke:30% + cover.*:close",
        "confidence": 0.87,
        "support": 22,
        "category": "comfort",
        "zone_id": "living",
        "mood_type": "relax",
        "risk_level": "low",
    },
    {
        "id": "sug_nobody_home",
        "title": "Abwesenheitsschaltung",
        "description": "Wenn 20 Min niemand: alle Lichter aus, Heizung 18\u00b0C",
        "pattern": "presence:none:20m -> light.*:off + climate.*:18",
        "confidence": 0.95,
        "support": 8,
        "category": "energy",
        "zone_id": "_global",
        "mood_type": "away",
        "risk_level": "medium",
        "estimated_savings_eur": 12.50,
    },
    {
        "id": "sug_bedtime_kids",
        "title": "Kinderzimmer Schlafenszeit",
        "description": "21:00: Kinderzimmer Licht auf Nachtlicht, Medien aus",
        "pattern": "time:21:00 -> light.mira_nachtlicht:5% + light.paul_nachtlicht:5% + media_player.sonos_mira:off",
        "confidence": 0.89,
        "support": 18,
        "category": "comfort",
        "zone_id": "room_mira",
        "mood_type": "sleep",
        "risk_level": "low",
    },
    {
        "id": "sug_solar_dishwasher",
        "title": "Solar-Spuelmaschine",
        "description": "Bei PV-Ueberschuss > 2kW: Spuelmaschine starten",
        "pattern": "sensor.pv_ueberschuss:>2000 -> switch.spuelmaschine:on",
        "confidence": 0.78,
        "support": 5,
        "category": "energy",
        "zone_id": "kitchen",
        "mood_type": "active",
        "risk_level": "medium",
        "estimated_savings_eur": 8.00,
    },
    {
        "id": "sug_ventilation_co2",
        "title": "CO2-Lueftung",
        "description": "CO2 > 1000ppm: Fensterhinweis oder Lueftung aktivieren",
        "pattern": "sensor.*_co2:>1000 -> notification:ventilate + fan.*:on",
        "confidence": 0.93,
        "support": 12,
        "category": "health",
        "zone_id": "_global",
        "mood_type": "alert",
        "risk_level": "low",
    },
    {
        "id": "sug_music_follow",
        "title": "Musikwolke aktivieren",
        "description": "Wenn du dich durch Zonen bewegst: Musik folgt automatisch",
        "pattern": "presence:zone_change + media_player:playing -> musikwolke:start",
        "confidence": 0.72,
        "support": 6,
        "category": "comfort",
        "zone_id": "_global",
        "mood_type": "social",
        "risk_level": "low",
    },
]


# ═══════════════════════════════════════════════════════════════════════════
# Zone Display Metadata
# ═══════════════════════════════════════════════════════════════════════════

ZONE_DISPLAY: Dict[str, Dict[str, str]] = {
    "living":     {"icon": "\U0001F6CB\uFE0F", "color": "#4fc3f7", "name_de": "Wohnbereich",    "mdi": "mdi:sofa"},
    "kitchen":    {"icon": "\U0001F373",        "color": "#ffb74d", "name_de": "Kochbereich",    "mdi": "mdi:stove"},
    "bath":       {"icon": "\U0001F6BF",        "color": "#81c784", "name_de": "Badbereich",     "mdi": "mdi:shower"},
    "hallway":    {"icon": "\U0001F6AA",        "color": "#ce93d8", "name_de": "Gangbereich",    "mdi": "mdi:door-open"},
    "bedroom":    {"icon": "\U0001F6CF\uFE0F",  "color": "#7986cb", "name_de": "Schlafbereich",  "mdi": "mdi:bed"},
    "office":     {"icon": "\U0001F4BC",        "color": "#4dd0e1", "name_de": "Buerobereich",   "mdi": "mdi:desk"},
    "room_mira":  {"icon": "\U0001F467",        "color": "#f48fb1", "name_de": "Mira",           "mdi": "mdi:account-child"},
    "room_paul":  {"icon": "\U0001F466",        "color": "#90caf9", "name_de": "Paul",           "mdi": "mdi:account-child"},
    "terrace":    {"icon": "\U0001F33F",        "color": "#a5d6a7", "name_de": "Terrasse",       "mdi": "mdi:flower"},
    "outside":    {"icon": "\U0001F333",        "color": "#c5e1a5", "name_de": "Aussenbereich",  "mdi": "mdi:tree"},
}


def get_example_config() -> Dict[str, Any]:
    """Return the full example configuration as a single dict."""
    return {
        "zones": EXAMPLE_ZONE_ENTITIES,
        "sonos_players": EXAMPLE_SONOS_PLAYERS,
        "playlists": EXAMPLE_PLAYLISTS,
        "sonos_favorites": EXAMPLE_SONOS_FAVORITES,
        "household": EXAMPLE_HOUSEHOLD,
        "todos": EXAMPLE_TODOS,
        "notifications": EXAMPLE_NOTIFICATIONS,
        "suggestions": EXAMPLE_SUGGESTIONS,
        "zone_display": ZONE_DISPLAY,
        "total_entities": sum(
            sum(len(entities) for entities in zone.values())
            for zone in EXAMPLE_ZONE_ENTITIES.values()
        ),
        "total_zones": len(EXAMPLE_ZONE_ENTITIES),
    }
