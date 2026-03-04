"""
Example Configuration for PilotSuite after Zero-Config Setup.

Provides a realistic example configuration based on a typical German household
with 10 Habitus zones, Sonos speakers, Hue lights, motion sensors, climate
controls, and media players.

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
            "sensor.spuelmaschine_verbrauch",
            "sensor.kuehlschrank_verbrauch",
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
            "lock.haustuer_schloss",
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
    },

    "office": {
        "lights": [
            "light.buero_decke",
            "light.buero_schreibtisch",
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
    },

    "room_mira": {
        "lights": [
            "light.mira_decke",
            "light.mira_nachtlicht",
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
    },

    "room_paul": {
        "lights": [
            "light.paul_decke",
            "light.paul_nachtlicht",
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
    },

    "terrace": {
        "lights": [
            "light.terrasse_aussen",
            "light.terrasse_lichterkette",
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
    },

    "outside": {
        "lights": [
            "light.garten_einfahrt",
            "light.garten_weg",
        ],
        "motion": [
            "binary_sensor.einfahrt_bewegung",
            "binary_sensor.garten_bewegung",
        ],
        "sensors": [
            "sensor.wetter_temperatur",
            "sensor.wetter_luftfeuchtigkeit",
            "sensor.wetter_wind",
            "binary_sensor.garagentor",
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
    },
    "kitchen": {
        "primary": "media_player.sonos_kueche",
        "secondary": [],
        "group_name": "Kueche",
    },
    "bath": {
        "primary": "media_player.sonos_bad",
        "secondary": [],
        "group_name": "Bad",
    },
    "bedroom": {
        "primary": "media_player.sonos_schlafzimmer",
        "secondary": [],
        "group_name": "Schlafzimmer",
    },
    "office": {
        "primary": "media_player.sonos_buero",
        "secondary": [],
        "group_name": "Buero",
    },
    "room_mira": {
        "primary": "media_player.sonos_mira",
        "secondary": [],
        "group_name": "Mira",
    },
    "room_paul": {
        "primary": "media_player.sonos_paul",
        "secondary": [],
        "group_name": "Paul",
    },
    "terrace": {
        "primary": "media_player.sonos_terrasse",
        "secondary": [],
        "group_name": "Terrasse",
    },
}


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
        "description": "Wenn 20 Min niemand: alle Lichter aus, Heizung 18°C",
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
    "living":     {"icon": "\U0001F6CB\uFE0F", "color": "#4fc3f7", "name_de": "Wohnbereich"},
    "kitchen":    {"icon": "\U0001F373",        "color": "#ffb74d", "name_de": "Kochbereich"},
    "bath":       {"icon": "\U0001F6BF",        "color": "#81c784", "name_de": "Badbereich"},
    "hallway":    {"icon": "\U0001F6AA",        "color": "#ce93d8", "name_de": "Gangbereich"},
    "bedroom":    {"icon": "\U0001F6CF\uFE0F",  "color": "#7986cb", "name_de": "Schlafbereich"},
    "office":     {"icon": "\U0001F4BC",        "color": "#4dd0e1", "name_de": "Buerobereich"},
    "room_mira":  {"icon": "\U0001F467",        "color": "#f48fb1", "name_de": "Mira"},
    "room_paul":  {"icon": "\U0001F466",        "color": "#90caf9", "name_de": "Paul"},
    "terrace":    {"icon": "\U0001F33F",        "color": "#a5d6a7", "name_de": "Terrasse"},
    "outside":    {"icon": "\U0001F333",        "color": "#c5e1a5", "name_de": "Aussenbereich"},
}


def get_example_config() -> Dict[str, Any]:
    """Return the full example configuration as a single dict."""
    return {
        "zones": EXAMPLE_ZONE_ENTITIES,
        "sonos_players": EXAMPLE_SONOS_PLAYERS,
        "suggestions": EXAMPLE_SUGGESTIONS,
        "zone_display": ZONE_DISPLAY,
        "total_entities": sum(
            sum(len(entities) for entities in zone.values())
            for zone in EXAMPLE_ZONE_ENTITIES.values()
        ),
        "total_zones": len(EXAMPLE_ZONE_ENTITIES),
    }
