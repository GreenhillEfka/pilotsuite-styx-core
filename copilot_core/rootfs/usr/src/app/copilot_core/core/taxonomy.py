"""
Classification Authority — Single Source of Truth für Entity-Rollen, Tags und Module-Routing.

Fasst die verteilte Classification-Logik aus:
  - hub/zone_automation.py      (detect_entity_role, detect_entity_tags, DOMAIN_TO_ROLE,
                                  ENTITY_ID_ROLE_HINTS, TAG_DEFINITIONS)
  - homeassistant/habitus_zones.py (ZoneType, MODULE_OVERRIDE_IDS, _ZONE_ENABLED_MODULES)
  - habitus_miner/service.py    (domain-to-module bucket Logik)

In ein einziges, inspizierbares Interface:
  classify_entity(entity_id, entity_state=None) -> EntityClassification

Jede Classification enthält:
  - role:       Canonical Role (lights, motion, media, climate, sensors, cover, ...)
  - tags:       Semantische Tags (indoor, outdoor, critical, ambient, ...)
  - module_bucket: Welches Hub-Modul für diese Entity zuständig ist
  - zone_type:  Falls aus ZoneType ableitbar
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, List, Optional


# ── Domain → Role ────────────────────────────────────────────────────────────

DOMAIN_TO_ROLE: dict[str, str] = {
    "light": "lights",
    "binary_sensor": "motion",
    "sensor": "sensors",
    "media_player": "media",
    "climate": "climate",
    "cover": "cover",
    "lock": "lock",
    "fan": "climate",
    "switch": "other",
    "input_boolean": "other",
    "person": "presence",
    "device_tracker": "presence",
    "camera": "camera",
    "automation": "system",
    "scene": "system",
    "script": "system",
}

# Domänen, die niemals outdoor sind
_INDOOR_DOMAINS: frozenset[str] = frozenset({
    "light", "media_player", "climate", "cover", "lock",
    "fan", "switch", "input_boolean", "person", "device_tracker",
    "automation", "scene", "script",
})

# Domänen die typischerweise outdoor sind
_OUTDOOR_DOMAINS: frozenset[str] = frozenset({
    "camera", "weather", "sensor",
})

# Kritische Domains (Sicherheit, Energie, Life-Safety)
_CRITICAL_DOMAINS: frozenset[str] = frozenset({
    "lock", "cover", "camera", "alarm", "smoke", "co", "binary_sensor",
})

# Ambient domains (kein sicherheitskritisches Verhalten)
_AMBIENT_DOMAINS: frozenset[str] = frozenset({
    "sensor", "light", "media_player", "fan",
})

# Keywords in entity_id → spezifischere Rollen
ENTITY_ID_ROLE_HINTS: dict[str, str] = {
    "praesenz": "motion",
    "bewegung": "motion",
    "motion": "motion",
    "presence": "motion",
    "occupancy": "motion",
    "helligkeit": "sensors",
    "illuminance": "sensors",
    "lux": "sensors",
    "temperatur": "climate",
    "temperature": "climate",
    "humidity": "climate",
    "luftfeucht": "climate",
    "co2": "sensors",
    "fenster": "window",
    "window": "window",
    "tuer": "door",
    "door": "door",
    "schloss": "lock",
    "verbrauch": "energy",
    "power": "energy",
    "energy": "energy",
    "smoke": "safety",
    "gas": "safety",
    "alarm": "safety",
    "camera": "camera",
    "wach": "camera",
    "ton": "camera",
    "stream": "camera",
}

# Keywords → Tags
_ENTITY_ID_TAG_KEYWORDS: dict[str, str] = {
    "licht": "licht",
    "light": "licht",
    "dimmer": "licht",
    "stripe": "licht",
    "led": "licht",
    "bewegung": "bewegung",
    "motion": "motion",
    "praesenz": "praesenz",
    "helligkeit": "ambient",
    "brightness": "ambient",
    "lux": "ambient",
    "illuminance": "ambient",
    "klima": "climate",
    "heiz": "climate",
    "thermostat": "climate",
    "temperatur": "climate",
    "temperature": "climate",
    "humidity": "climate",
    "feucht": "climate",
    "medien": "media",
    "media": "media",
    "speaker": "media",
    "tv": "media",
    "fernseher": "media",
    "musik": "music",
    "music": "music",
    "playlist": "music",
    "sensor": "sensor",
    "smoke": "safety",
    "gas": "safety",
    "alarm": "safety",
    "co2": "safety",
    "schloss": "lock",
    "lock": "lock",
    "tuer": "door",
    "door": "door",
    "fenster": "window",
    "window": "window",
    "rollladen": "cover",
    "cover": "cover",
    "shutter": "cover",
    "jalousie": "cover",
    "energie": "energy",
    "power": "energy",
    "verbrauch": "energy",
    "pv": "energy",
    "battery": "energy",
    "solar": "energy",
    "camera": "camera",
    "wach": "camera",
    "ton": "camera",
    "kamera": "camera",
    "aussen": "outdoor",
    "outdoor": "outdoor",
    "garden": "outdoor",
    "terrace": "outdoor",
    "balcony": "outdoor",
    "garage": "outdoor",
    "innen": "indoor",
    "indoor": "indoor",
}

# Module Bucket Mapping (welches Hub-Modul ist für diese Entity zuständig)
_DOMAIN_TO_MODULE_BUCKET: dict[str, str] = {
    "light": "licht",
    "binary_sensor": "bewegung",
    "sensor": "helligkeit",
    "media_player": "medien",
    "climate": "heiz",
    "cover": "cover",
    "lock": "sicherheit",
    "fan": "heiz",
    "switch": "other",
    "input_boolean": "other",
    "person": "praesenz",
    "device_tracker": "praesenz",
    "camera": "kamera",
    "automation": "system",
    "scene": "system",
    "script": "system",
}

_TAG_TO_MODULE_BUCKET: dict[str, str] = {
    "licht": "licht",
    "light": "licht",
    "bewegung": "bewegung",
    "motion": "bewegung",
    "praesenz": "praesenz",
    "climate": "heiz",
    "klima": "heiz",
    "heiz": "heiz",
    "temperatur": "heiz",
    "temperature": "heiz",
    "humidity": "heiz",
    "feucht": "heiz",
    "medien": "medien",
    "media": "medien",
    "tv": "tv",
    "musik": "musik",
    "music": "musik",
    "camera": "kamera",
    "kamera": "kamera",
    "energie": "energie",
    "energy": "energie",
    "power": "energie",
    "lock": "sicherheit",
    "schloss": "sicherheit",
    "door": "sicherheit",
    "tuer": "sicherheit",
    "cover": "cover",
    "rollladen": "cover",
    "window": "cover",
    "fenster": "cover",
    "safety": "sicherheit",
    "smoke": "sicherheit",
    "gas": "sicherheit",
    "alarm": "sicherheit",
}

# ── Data Models ──────────────────────────────────────────────────────────────


class EntityRole(str, Enum):
    """Canonical entity roles."""
    LIGHTS = "lights"
    MOTION = "motion"
    MEDIA = "media"
    CLIMATE = "climate"
    SENSORS = "sensors"
    COVER = "cover"
    LOCK = "lock"
    DOOR = "door"
    WINDOW = "window"
    ENERGY = "energy"
    CAMERA = "camera"
    PRESENCE = "presence"
    SAFETY = "safety"
    MUSIC = "music"
    SYSTEM = "system"
    OTHER = "other"


class EntityTag(str, Enum):
    """Semantic entity tags."""
    INDOOR = "indoor"
    OUTDOOR = "outdoor"
    CRITICAL = "critical"
    AMBIENT = "ambient"
    LIGHTING = "lighting"
    CLIMATE_CONTROL = "climate_control"
    SECURITY = "security"
    ENTERTAINMENT = "entertainment"
    ENERGY_MANAGEMENT = "energy_management"
    PRESENCE_DETECTION = "presence_detection"


# ── Classification Result ────────────────────────────────────────────────────


@dataclass(frozen=True)
class EntityClassification:
    """Canonical classification for a Home Assistant entity."""

    entity_id: str
    role: EntityRole
    module_bucket: str                    # Hub-Modul Bucket
    tags: tuple[str, ...] = field(default_factory=tuple)   # semantische Tags
    zone_type_hint: Optional[str] = None  # ZoneType.value wenn ableitbar
    domain: str = ""
    confidence: float = 1.0             # confidence der Rollen-Detektion
    source: str = "auto"                # "auto" | "manual" | "import"

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "role": self.role.value,
            "module_bucket": self.module_bucket,
            "tags": list(self.tags),
            "zone_type_hint": self.zone_type_hint,
            "domain": self.domain,
            "confidence": round(self.confidence, 3),
            "source": self.source,
        }


# ── Classification Function ──────────────────────────────────────────────────


def classify_entity(
    entity_id: str,
    entity_state: Any = None,
    *,
    explicit_role: Optional[str] = None,
    explicit_tags: Optional[List[str]] = None,
    explicit_module: Optional[str] = None,
) -> EntityClassification:
    """
    Klassifiziere eine Home-Assistant-Entity in Role + Tags + Module-Bucket.

    Dies ist das SINGLE SOURCE OF TRUTH Interface für alle Entity-Klassifikation.

    Args:
        entity_id:       Vollständige HA entity_id (z.B. "light.kitchen_main")
        entity_state:    Optionaler State-Wert (z.B. "on", "23.5", "home")
        explicit_role:  Manuelle Rollen-Überschreibung (höchste Priorität)
        explicit_tags:  Manuelle Tags-Überschreibung
        explicit_module:Manuelle Module-Bucket-Überschreibung

    Returns:
        EntityClassification mit role, tags, module_bucket
    """
    parts = entity_id.split(".", 1)
    domain = parts[0] if parts else ""
    name = parts[1] if len(parts) > 1 else ""
    name_lower = name.lower()
    full_lower = entity_id.lower()

    # ── 1. Role Detection ──────────────────────────────────────────────────
    if explicit_role:
        role = EntityRole(explicit_role)
        confidence = 1.0
        role_source = "manual"
    else:
        role, confidence, role_source = _detect_role(domain, name_lower, full_lower)

    # ── 2. Tags Detection ───────────────────────────────────────────────────
    if explicit_tags:
        tags = tuple(explicit_tags)
    else:
        tags = _detect_tags(domain, name_lower, full_lower, entity_state)

    # ── 3. Module Bucket ────────────────────────────────────────────────────
    if explicit_module:
        module_bucket = explicit_module
    else:
        module_bucket = _resolve_module_bucket(domain, name_lower, full_lower, tags)

    # ── 4. Zone Type Hint (from entity_id keywords) ─────────────────────────
    zone_type_hint = _detect_zone_type_hint(full_lower)

    return EntityClassification(
        entity_id=entity_id,
        role=role,
        module_bucket=module_bucket,
        tags=tags,
        zone_type_hint=zone_type_hint,
        domain=domain,
        confidence=confidence,
        source=role_source,
    )


def _detect_role(
    domain: str, name_lower: str, full_lower: str
) -> tuple[EntityRole, float, str]:
    """Erkenne Entity-Rolle mit Priorität: hints > domain mapping."""
    # Höchste Priorität: Keyword hints (spezifischer)
    for hint, role_str in ENTITY_ID_ROLE_HINTS.items():
        if hint in name_lower:
            try:
                return EntityRole(role_str), 0.95, "auto"
            except ValueError:
                pass

    # Fallback: Domain Mapping
    role_str = DOMAIN_TO_ROLE.get(domain)
    if role_str:
        try:
            return EntityRole(role_str), 0.8, "auto"
        except ValueError:
            pass

    return EntityRole.OTHER, 0.5, "auto"


def _detect_tags(
    domain: str, name_lower: str, full_lower: str, entity_state: Any
) -> tuple[str, ...]:
    """Erkenne semantische Tags für eine Entity."""
    tags: set[str] = set()

    # Indoor / Outdoor
    if domain in _INDOOR_DOMAINS:
        tags.add("indoor")
    elif domain in _OUTDOOR_DOMAINS:
        tags.add("outdoor")
    else:
        # Keyword-basiert
        outdoor_keywords = ("outdoor", "garden", "terrace", "balcony", "garage",
                            "aussen", "außen", "garten", "terrass")
        if any(kw in full_lower for kw in outdoor_keywords):
            tags.add("outdoor")
        else:
            tags.add("indoor")

    # Critical
    if domain in _CRITICAL_DOMAINS:
        tags.add("critical")
    elif any(kw in full_lower for kw in ("alarm", "smoke", "gas", "sicherheit")):
        tags.add("critical")

    # Ambient
    if domain in _AMBIENT_DOMAINS and "critical" not in tags:
        tags.add("ambient")

    # Domänen-basierte Tags
    if domain == "light":
        tags.add("lighting")
    if domain in ("climate", "fan"):
        tags.add("climate_control")
    if domain in ("lock", "camera", "alarm", "smoke", "binary_sensor"):
        tags.add("security")
    if domain in ("media_player", "tv"):
        tags.add("entertainment")
    if domain in ("sensor", "switch") and any(kw in name_lower for kw in ("power", "energie", "energy", "verbrauch")):
        tags.add("energy_management")
    if domain in ("binary_sensor", "person", "device_tracker"):
        if any(kw in name_lower for kw in ("motion", "presence", "praesenz", "bewegung")):
            tags.add("presence_detection")

    # Keyword-basierte Tag-Erkennung aus entity_id
    for keyword, tag in _ENTITY_ID_TAG_KEYWORDS.items():
        if keyword in name_lower and tag not in tags:
            # Normalisiere Tag-Namen
            if tag == "licht":
                tags.add("lighting")
            elif tag in ("climate", "klima", "heiz"):
                tags.add("climate_control")
            elif tag in ("camera", "kamera"):
                tags.add("security")
            elif tag in ("music", "musik"):
                tags.add("entertainment")
            elif tag in ("energy", "energie"):
                tags.add("energy_management")
            elif tag in ("motion", "bewegung", "praesenz"):
                tags.add("presence_detection")
            elif tag == "ambient":
                tags.add("ambient")

    return tuple(sorted(tags))


def _resolve_module_bucket(
    domain: str, name_lower: str, full_lower: str, tags: tuple[str, ...]
) -> str:
    """Löse den Hub-Modul-Bucket für eine Entity auf."""
    # Prüfe explicit tag → module mapping
    for tag in tags:
        module = _TAG_TO_MODULE_BUCKET.get(tag)
        if module:
            return module

    # Fallback: domain mapping
    module = _DOMAIN_TO_MODULE_BUCKET.get(domain)
    if module:
        return module

    # Spezielle Musik/TV Logik aus entity_id
    if any(kw in full_lower for kw in ("tv", "television", "fernseher", "chromecast")):
        return "tv"
    if any(kw in full_lower for kw in ("volume", "lautstärk", "lautstaerk")):
        return "volume"
    if any(kw in full_lower for kw in ("playlist", "musik", "music", "sonos", "speak")):
        return "musik"

    return "other"


def _detect_zone_type_hint(full_lower: str) -> Optional[str]:
    """Leite ZoneType-Hint aus entity_id keywords ab."""
    mapping = {
        "wohn": "living",
        "living": "living",
        "bad": "bath",
        "bath": "bath",
        "küche": "kitchen",
        "kche": "kitchen",
        "kitchen": "kitchen",
        "büro": "office",
        "buero": "office",
        "office": "office",
        "flur": "hallway",
        "hallway": "hallway",
        "schlaf": "bedroom",
        "bedroom": "bedroom",
        "mira": "room_mira",
        "paul": "room_paul",
        "terrass": "terrace",
        "terrace": "terrace",
        "balkon": "terrace",
        "balcony": "terrace",
        "loggia": "terrace",
        "patio": "terrace",
        "deck": "terrace",
        "outside": "outside",
        "garten": "outside",
        "garden": "outside",
        "garage": "outside",
    }
    for keyword, zone_type in mapping.items():
        if keyword in full_lower:
            return zone_type
    return None


# ── Backward-Compatible Helpers (für bestehenden Code) ───────────────────────


def detect_entity_role(entity_id: str) -> str:
    """Detektiere Entity-Rolle (delegiert an classify_entity)."""
    return classify_entity(entity_id).role.value


def detect_entity_tags(entity_id: str) -> List[str]:
    """Detektiere Entity-Tags (delegiert an classify_entity)."""
    return list(classify_entity(entity_id).tags)


__all__ = [
    "EntityClassification",
    "EntityRole",
    "EntityTag",
    "classify_entity",
    "detect_entity_role",
    "detect_entity_tags",
]
