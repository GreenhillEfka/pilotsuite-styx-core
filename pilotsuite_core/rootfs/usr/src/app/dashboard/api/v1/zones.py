from __future__ import annotations

from copy import deepcopy

from flask import Blueprint, jsonify, request


zones_bp = Blueprint("zones_v1", __name__, url_prefix="/api/v1/zones")

_ZONES = [
    {
        "id": "living",
        "zone_type": "living",
        "name_de": "Wohnbereich",
        "name_en": "Living Area",
        "description": "Hauptaufenthaltsbereich zum Wohnen und Entspannen",
        "keywords_de": [
            "wohn",
            "wohnzimmer",
            "aufenthalt",
            "gast",
            "gästezimmer",
            "esszimmer",
            "essbereich",
        ],
        "keywords_en": ["living", "lounge", "sitting", "guest", "dining", "family room"],
        "priority": 10,
    },
    {
        "id": "bath",
        "zone_type": "bath",
        "name_de": "Badbereich",
        "name_en": "Bathroom Area",
        "description": "Sanitärbereich mit Bad/WC",
        "keywords_de": [
            "bad",
            "badbereich",
            "badezimmer",
            "wc",
            "toilette",
            "gäste-wc",
            "dusche",
            "waschraum",
        ],
        "keywords_en": ["bath", "bathroom", "toilet", "wc", "shower", "powder room"],
        "priority": 10,
    },
    {
        "id": "kitchen",
        "zone_type": "kitchen",
        "name_de": "Kochbereich",
        "name_en": "Kitchen Area",
        "description": "Koch-, Ess- und Wirtschaftsbereich",
        "keywords_de": [
            "koch",
            "küche",
            "kochen",
            "kochbereich",
            "speis",
            "vorrat",
            "hauswirtschaft",
            "esszimmer",
            "essbereich",
        ],
        "keywords_en": ["kitchen", "cooking", "pantry", "utility", "laundry", "dining room"],
        "priority": 11,
    },
    {
        "id": "office",
        "zone_type": "office",
        "name_de": "Bürobereich",
        "name_en": "Office Area",
        "description": "Arbeits- und Heimbürobereich",
        "keywords_de": ["büro", "arbeit", "homeoffice", "arbeitszimmer", "studie"],
        "keywords_en": ["office", "work", "study", "home office", "workspace"],
        "priority": 8,
    },
    {
        "id": "hallway",
        "zone_type": "hallway",
        "name_de": "Gangbereich",
        "name_en": "Hallway Area",
        "description": "Verbindungsbereich und Durchgang",
        "keywords_de": [
            "gang",
            "gangbereich",
            "flur",
            "flurbereich",
            "diele",
            "treppenhaus",
            "eingang",
            "eingangsbereich",
            "windfang",
        ],
        "keywords_en": ["hallway", "hall", "corridor", "entry", "entrance", "foyer"],
        "priority": 5,
    },
    {
        "id": "bedroom",
        "zone_type": "bedroom",
        "name_de": "Schlafbereich",
        "name_en": "Bedroom Area",
        "description": "Hauptschlafbereich",
        "keywords_de": [
            "schlaf",
            "schlafzimmer",
            "schlafraum",
            "master",
            "eltern",
            "schlafbereich",
            "elternschlafzimmer",
        ],
        "keywords_en": ["bedroom", "sleep", "master bedroom", "parents"],
        "priority": 12,
    },
    {
        "id": "room_mira",
        "zone_type": "room_mira",
        "name_de": "Zimmer Mira",
        "name_en": "Mira's Room",
        "description": "Persönliches Zimmer von Mira",
        "keywords_de": ["mira", "kinderzimmer mira", "zimmer mira", "miras zimmer"],
        "keywords_en": ["mira", "mira room", "mira bedroom", "miras room"],
        "priority": 20,
    },
    {
        "id": "room_paul",
        "zone_type": "room_paul",
        "name_de": "Zimmer Paul",
        "name_en": "Paul's Room",
        "description": "Persönliches Zimmer von Paul",
        "keywords_de": ["paul", "kinderzimmer paul", "zimmer paul", "pauls zimmer"],
        "keywords_en": ["paul", "paul room", "paul bedroom", "pauls room"],
        "priority": 20,
    },
    {
        "id": "terrace",
        "zone_type": "terrace",
        "name_de": "Terrassenbereich",
        "name_en": "Terrace Area",
        "description": "Überdachte Aussenbereiche",
        "keywords_de": ["terrass", "balkon", "loggia", "dachterrass"],
        "keywords_en": ["terrace", "balcony", "patio", "deck"],
        "priority": 8,
    },
    {
        "id": "outside",
        "zone_type": "outside",
        "name_de": "Aussenbereich",
        "name_en": "Outside Area",
        "description": "Aussenbereiche und smart aggregierte Outdoor-Zonen",
        "keywords_de": [
            "aussen",
            "außen",
            "garten",
            "hof",
            "vorgarten",
            "hintergarten",
            "garage",
            "carport",
            "abstell",
            "terrasse",
            "terrassenbereich",
            "balkon",
            "loggia",
        ],
        "keywords_en": ["outside", "garden", "yard", "garage", "shed", "outdoor", "terrace", "balcony"],
        "priority": 9,
    },
]

_VALID_ZONE_TYPES = {zone["zone_type"] for zone in _ZONES}


@zones_bp.get("")
def get_zones():
    zone_type = request.args.get("zone_type", "").strip().lower()

    if zone_type and zone_type not in _VALID_ZONE_TYPES:
        return (
            jsonify(
                {
                    "error": "invalid_zone_type",
                    "message": f"Invalid zone type: {zone_type}",
                    "valid_zone_types": sorted(_VALID_ZONE_TYPES),
                }
            ),
            400,
        )

    zones = [zone for zone in _ZONES if not zone_type or zone["zone_type"] == zone_type]

    return jsonify(
        {
            "status": "ok",
            "source": "static_habitus_catalog",
            "total_zones": len(zones),
            "zones": deepcopy(zones),
        }
    )
