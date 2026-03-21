"""
Habituszone-Definitionen für PilotSuite Styx Core

Definiert 10 standardisierte Habituszonen mit Keywords für ML-basiertes Matching.
Erweitert um sekundäre Zustände: dark (Lichtsensor/Sonne), sleep (Switch-Override), extended (Überschreitung Zeitlimit).
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum


class ZoneType(str, Enum):
    """Typen von Habituszonen."""
    LIVING = "living"
    BATH = "bath"
    KITCHEN = "kitchen"
    OFFICE = "office"
    HALLWAY = "hallway"
    BEDROOM = "bedroom"
    ROOM_MIRA = "room_mira"
    ROOM_PAUL = "room_paul"
    TERRACE = "terrace"
    OUTSIDE = "outside"


@dataclass
class HabitusZone:
    """Eine Habituszone mit Keywords und Metadaten."""
    zone_type: ZoneType
    name_de: str  # Deutscher Name
    name_en: str  # Englischer Name
    keywords_de: List[str] = field(default_factory=list)  # Deutsche Keywords
    keywords_en: List[str] = field(default_factory=list)  # Englische Keywords
    priority: int = 0  # Höhere Priorität bei Konflikten
    description: str = ""

    def get_all_keywords(self) -> List[str]:
        """Alle Keywords (DE + EN) zurückgeben."""
        return self.keywords_de + self.keywords_en


# Standard-Habituszonen
HABITUS_ZONES: Dict[ZoneType, HabitusZone] = {
    ZoneType.LIVING: HabitusZone(
        zone_type=ZoneType.LIVING,
        name_de="Wohnbereich",
        name_en="Living Area",
        keywords_de=["wohn", "wohnzimmer", "wohnzimmer", "aufenthalt", "gast", "gästezimmer", "esszimmer", "essbereich"],
        keywords_en=["living", "lounge", "sitting", "guest", "dining", "family room"],
        priority=10,
        description="Hauptaufenthaltsbereich zum Wohnen und Entspannen"
    ),
    
    ZoneType.BATH: HabitusZone(
        zone_type=ZoneType.BATH,
        name_de="Badbereich",
        name_en="Bathroom Area",
        keywords_de=["bad", "badezimmer", "wc", "toilette", "gäste-wc", "dusche", "waschraum"],
        keywords_en=["bath", "bathroom", "toilet", "wc", "shower", "powder room"],
        priority=10,
        description="Sanitärbereich mit Bad/WC"
    ),
    
    ZoneType.KITCHEN: HabitusZone(
        zone_type=ZoneType.KITCHEN,
        name_de="Kochbereich",
        name_en="Kitchen Area",
        keywords_de=["koch", "küche", "kochen", "speis", "vorrat", "hauswirtschaft"],
        keywords_en=["kitchen", "cooking", "pantry", "utility", "laundry"],
        priority=10,
        description="Koch- und Wirtschaftsbereich"
    ),
    
    ZoneType.OFFICE: HabitusZone(
        zone_type=ZoneType.OFFICE,
        name_de="Bürobereich",
        name_en="Office Area",
        keywords_de=["büro", "arbeit", "homeoffice", "arbeitszimmer", "studie"],
        keywords_en=["office", "work", "study", "home office", "workspace"],
        priority=8,
        description="Arbeits- und Heimbürobereich"
    ),
    
    ZoneType.HALLWAY: HabitusZone(
        zone_type=ZoneType.HALLWAY,
        name_de="Gangbereich",
        name_en="Hallway Area",
        keywords_de=["gang", "flur", "diele", "treppenhaus", "eingang", "windfang"],
        keywords_en=["hallway", "hall", "corridor", "entry", "entrance", "foyer"],
        priority=5,
        description="Verbindungsbereich und Durchgang"
    ),
    
    ZoneType.BEDROOM: HabitusZone(
        zone_type=ZoneType.BEDROOM,
        name_de="Schlafbereich",
        name_en="Bedroom Area",
        keywords_de=["schlaf", "schlafzimmer", "schlafraum", "master", "eltern", "schlafbereich", "elternschlafzimmer"],
        keywords_en=["bedroom", "sleep", "master bedroom", "parents"],
        priority=12,
        description="Hauptschlafbereich"
    ),
    
    ZoneType.ROOM_MIRA: HabitusZone(
        zone_type=ZoneType.ROOM_MIRA,
        name_de="Zimmer Mira",
        name_en="Mira's Room",
        keywords_de=["mira", "kinderzimmer mira", "zimmer mira", "miras zimmer"],
        keywords_en=["mira", "mira room", "mira bedroom", "miras room"],
        priority=20,  # Hohe Priorität für spezifische Namen
        description="Persönliches Zimmer von Mira"
    ),
    
    ZoneType.ROOM_PAUL: HabitusZone(
        zone_type=ZoneType.ROOM_PAUL,
        name_de="Zimmer Paul",
        name_en="Paul's Room",
        keywords_de=["paul", "kinderzimmer paul", "zimmer paul", "pauls zimmer"],
        keywords_en=["paul", "paul room", "paul bedroom", "pauls room"],
        priority=20,  # Hohe Priorität für spezifische Namen
        description="Persönliches Zimmer von Paul"
    ),
    
    ZoneType.TERRACE: HabitusZone(
        zone_type=ZoneType.TERRACE,
        name_de="Terrassenbereich",
        name_en="Terrace Area",
        keywords_de=["terrass", "balkon", "loggia", "dachterrass"],
        keywords_en=["terrace", "balcony", "patio", "deck"],
        priority=8,
        description="Überdachte Aussenbereiche"
    ),
    
    ZoneType.OUTSIDE: HabitusZone(
        zone_type=ZoneType.OUTSIDE,
        name_de="Aussenbereich",
        name_en="Outside Area",
        keywords_de=["aussen", "garten", "hof", "vorgarten", "hintergarten", "garage", "carport", "abstell"],
        keywords_en=["outside", "garden", "yard", "garage", "shed", "outdoor"],
        priority=5,
        description="Aussenbereiche und Garten"
    ),
}


# Sekundäre Zustände für erweiterte Zone-Logik
SECONDARY_STATES = {
    "dark": {
        "name_de": "Dunkel",
        "name_en": "Dark",
        "description_de": "Zone ist dunkel (Lichtsensor/Wetter)",
        "description_en": "Zone is dark (light sensor/weather)",
        "icon": "mdi:weather-night",
        "triggers": ["lux_sensor", "sun_position", "weather_condition"]
    },
    "sleep": {
        "name_de": "Schlafmodus",
        "name_en": "Sleep Mode",
        "description_de": "Zone ist im Schlafmodus (Switch-Override)",
        "description_en": "Zone is in sleep mode (switch override)",
        "icon": "mdi:sleep",
        "triggers": ["sleep_switch", "schedule", "manual_override"]
    },
    "extended": {
        "name_de": "Erweitert",
        "name_en": "Extended",
        "description_de": "Zone überschreitet Zeitlimit (Verweildauer)",
        "description_en": "Zone exceeds time limit (dwell time)",
        "icon": "mdi:timer-plus",
        "triggers": ["time_limit_exceeded", "occupancy_duration", "schedule_override"]
    }
}


def get_all_zones() -> List[HabitusZone]:
    """Alle Habituszonen als Liste zurückgeben."""
    return list(HABITUS_ZONES.values())


def get_zone_by_type(zone_type: ZoneType) -> Optional[HabitusZone]:
    """Eine Zone nach Typ zurückgeben."""
    return HABITUS_ZONES.get(zone_type)


def get_zone_keywords() -> Dict[str, ZoneType]:
    """
    Mapping von Keywords zu ZoneTypes für schnelles Lookup.
    Alle Keywords werden lowercase gespeichert.
    """
    keyword_map = {}
    for zone in HABITUS_ZONES.values():
        for keyword in zone.get_all_keywords():
            keyword_map[keyword.lower()] = zone.zone_type
    return keyword_map


def get_secondary_states() -> Dict[str, Dict]:
    """Sekundäre Zustände für erweiterte Zone-Logik zurückgeben."""
    return SECONDARY_STATES.copy()
