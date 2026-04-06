"""Zone Automation Controller — Presence-Based Light & Musikwolke (v1.0.0).

Unified per-zone automation engine combining:
- Presence-dependent light control with configurable delay, brightness target,
  hysteresis dampening, and override switch
- Presence-dependent Musikwolke (music follows user) with timing config
- Entity management (add/remove entities to/from zones)
- Tag-based entity classification with role assignment

Key design (state-of-the-art patterns):
- Hysteresis / Dead-band: prevents rapid on/off toggling from sensor noise
  (e.g., if threshold=200lux, on_threshold=180, off_threshold=220)
- Cloud-transient filtering: short outdoor brightness dips (cloud passing)
  are ignored via moving-average + hysteresis (from LightIntelligenceEngine)
- Presence delay: configurable seconds before lights trigger (mmWave+PIR fusion)
- Raumausleuchtung (0-100%): normalized indoor/outdoor brightness target
- Override switch: manual enable/disable of all automations per zone
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field, asdict
from typing import Any

from copilot_core.hub.zone_modules import ZoneModuleRegistry
from copilot_core.hub.zone_modules.base import ZoneModuleConfig
from copilot_core.homeassistant.habitus_zones import ZoneType

logger = logging.getLogger(__name__)

# Canonical zone type whitelist used across Core and HA contract layer.
_ALLOWED_ZONE_TYPES = {item.value for item in ZoneType}
DEFAULT_ZONE_TYPE = "living"


def _normalize_zone_type(zone_type: str) -> str:
    """Normalize and validate zone type against canonical ZoneType enum."""
    normalized = (zone_type or "").strip().lower()
    return normalized if normalized in _ALLOWED_ZONE_TYPES else ""


# Ensure all modules are registered
ZoneModuleRegistry.ensure_loaded()


# ── Data models ──────────────────────────────────────────────────────────────


@dataclass
class ZoneLightConfig:
    """Per-zone light automation configuration."""

    enabled: bool = True  # Override switch: enable/disable light automation
    presence_delay_s: int = 5  # Seconds of presence before lights turn on (slider: 0-120)
    absence_delay_s: int = 120  # Seconds after last presence before lights turn off (slider: 0-600)
    brightness_target_pct: int = 80  # Raumausleuchtung target (slider: 0-100%)
    brightness_min_pct: int = 0  # Minimum brightness when on (slider: 0-100%)
    dampening_band_pct: int = 10  # Hysteresis dead-band (slider: 0-50%)
    lux_indoor_target: float = 300.0  # Target indoor lux level
    lux_outdoor_compensation: bool = True  # Relative indoor/outdoor brightness
    color_temp_auto: bool = True  # Circadian color temperature
    color_temp_k: int = 4000  # Manual color temp if auto=False (2200-6500)
    mood_aware_enabled: bool = True  # Apply mood-based brightness/color adjustments


@dataclass
class ZoneMusicConfig:
    """Per-zone Musikwolke automation configuration."""

    enabled: bool = True  # Override switch: enable/disable music automation
    presence_auto_play: bool = False  # Auto-play music on zone entry
    presence_delay_s: int = 10  # Seconds of presence before music starts (slider: 0-120)
    absence_pause_s: int = 300  # Seconds after absence before pausing (slider: 0-600)
    follow_mode: bool = True  # Music follows user between zones
    default_volume_pct: int = 30  # Default playback volume (slider: 0-100)
    fade_duration_s: int = 3  # Cross-fade duration when following
    favorite_name: str = ""  # Preselected favorite (Sonos favorite name) for this zone
    favorite_uri: str = ""  # Optional URI for custom station/playlist
    crossfade_enabled: bool = True  # Enable smooth cross-fade between zones


AUTOMATION_MODES = ("off", "learning", "autonomy")

# ── Mood Adjustment Profiles ─────────────────────────────────────────────────
# Maps mood state names to lighting adjustment parameters.
# brightness_factor: multiplier for base brightness (0.0-1.0)
# color_temp_k: recommended color temperature in Kelvin
# transition_s: seconds for smooth transition

MOOD_ADJUSTMENTS: dict[str, dict[str, float | int]] = {
    "relax": {"brightness_factor": 0.6, "color_temp_k": 2700, "transition_s": 5},
    "focus": {"brightness_factor": 0.9, "color_temp_k": 4500, "transition_s": 2},
    "active": {"brightness_factor": 1.0, "color_temp_k": 5000, "transition_s": 1},
    "sleep": {"brightness_factor": 0.1, "color_temp_k": 2200, "transition_s": 10},
    "away": {"brightness_factor": 0.0, "color_temp_k": 3000, "transition_s": 1},
    "alert": {"brightness_factor": 1.0, "color_temp_k": 6500, "transition_s": 0.5},
    "social": {"brightness_factor": 0.8, "color_temp_k": 3500, "transition_s": 3},
    "recovery": {"brightness_factor": 0.4, "color_temp_k": 2500, "transition_s": 8},
    # Mood engine states mapped to profiles
    "night": {"brightness_factor": 0.1, "color_temp_k": 2200, "transition_s": 10},
    "stress": {"brightness_factor": 0.7, "color_temp_k": 3500, "transition_s": 3},
    "neutral": {"brightness_factor": 1.0, "color_temp_k": 4000, "transition_s": 2},
}

# Default adjustment when mood is unknown or not in the profiles dict
_DEFAULT_MOOD_ADJUSTMENT: dict[str, float | int] = {
    "brightness_factor": 1.0,
    "color_temp_k": 4000,
    "transition_s": 2,
}


def get_mood_adjustment(mood_state: str) -> dict[str, float | int]:
    """Return mood adjustment profile for the given mood state.

    Falls back to neutral defaults for unknown mood states.
    """
    return MOOD_ADJUSTMENTS.get(mood_state.lower().strip(), _DEFAULT_MOOD_ADJUSTMENT)


@dataclass
class ZoneAutomationConfig:
    """Complete automation configuration for a zone.

    Supports both legacy (light/music dataclasses) and new module system.
    The `modules` dict holds ZoneModuleConfig instances keyed by MODULE_ID.
    Legacy `light` and `music` properties provide backward compatibility.
    """

    zone_id: str
    zone_name: str = ""
    zone_type: str = DEFAULT_ZONE_TYPE
    enabled_modules: set[str] = field(default_factory=set)
    ha_entities: list[dict[str, Any]] = field(default_factory=list)
    automation_mode: str = "learning"  # off | learning | autonomy
    light: ZoneLightConfig = field(default_factory=ZoneLightConfig)
    music: ZoneMusicConfig = field(default_factory=ZoneMusicConfig)
    modules: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.modules:
            self.modules = ZoneModuleRegistry.create_defaults()
        # Backward-compatible mirror for older callers still reading cfg._ha_entities
        self._ha_entities = list(self.ha_entities)

    def to_dict(self) -> dict[str, Any]:
        result = {
            "zone_id": self.zone_id,
            "zone_name": self.zone_name,
            "zone_type": self.zone_type,
            "enabled_modules": sorted(self.enabled_modules),
            "ha_entities": list(self.ha_entities),
            "automation_mode": self.automation_mode,
            # Legacy keys for backward compatibility
            "light": asdict(self.light),
            "music": asdict(self.music),
            # New module system
            "modules": {
                mid: mod.to_dict()
                for mid, mod in self.modules.items()
            },
        }
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ZoneAutomationConfig":
        light_data = data.get("light", {})
        music_data = data.get("music", {})
        mode = data.get("automation_mode", "learning")
        if mode not in AUTOMATION_MODES:
            mode = "learning"

        # Load modules from "modules" dict if present
        modules_data = data.get("modules", {})
        modules = ZoneModuleRegistry.from_dict(modules_data)

        return cls(
            zone_id=data.get("zone_id", ""),
            zone_name=data.get("zone_name", ""),
            zone_type=_normalize_zone_type(data.get("zone_type", "")) or DEFAULT_ZONE_TYPE,
            enabled_modules=set(data.get("enabled_modules", [])),
            ha_entities=list(data.get("ha_entities", [])),
            automation_mode=mode,
            light=ZoneLightConfig(**{k: v for k, v in light_data.items() if k in ZoneLightConfig.__dataclass_fields__}),
            music=ZoneMusicConfig(**{k: v for k, v in music_data.items() if k in ZoneMusicConfig.__dataclass_fields__}),
            modules=modules,
        )


@dataclass
class ZonePresenceState:
    """Runtime presence state for a zone."""

    occupied: bool = False
    last_detected_ts: float = 0.0  # time.monotonic()
    last_cleared_ts: float = 0.0
    presence_confirmed: bool = False  # After delay
    absence_confirmed: bool = False

    # Light state
    lights_on: bool = False
    current_brightness_pct: int = 0
    dampened_brightness_pct: int = 0  # After hysteresis applied

    # Music state
    music_playing: bool = False
    music_triggered_at: float = 0.0


@dataclass
class ZoneEntityAssignment:
    """Entity assigned to a zone with role and tags."""

    entity_id: str
    zone_id: str
    role: str  # lights, motion, media, climate, sensors, cover, other
    tags: list[str] = field(default_factory=list)
    display_name: str = ""
    added_at: float = field(default_factory=time.time)
    source: str = "manual"  # manual, auto_discovery, import


# ── Tag definitions ──────────────────────────────────────────────────────────

ENTITY_ROLES = [
    "lights", "motion", "media", "climate", "sensors",
    "cover", "lock", "door", "window", "energy", "other",
]

TAG_DEFINITIONS: dict[str, dict[str, str]] = {
    "licht": {"name_de": "Licht", "color": "#fbbf24", "icon": "mdi:lightbulb", "role": "lights", "canonical": "aicp.role.licht"},
    "praesenz": {"name_de": "Praesenz", "color": "#a78bfa", "icon": "mdi:motion-sensor", "role": "motion", "canonical": "aicp.role.praesenz"},
    "bewegung": {"name_de": "Bewegung", "color": "#c084fc", "icon": "mdi:run", "role": "motion", "canonical": "aicp.role.bewegung"},
    "medien": {"name_de": "Medien", "color": "#60a5fa", "icon": "mdi:speaker", "role": "media", "canonical": "aicp.role.medien"},
    "klima": {"name_de": "Klima", "color": "#34d399", "icon": "mdi:thermometer", "role": "climate", "canonical": "aicp.role.klima"},
    "sensor": {"name_de": "Sensor", "color": "#f472b6", "icon": "mdi:chip", "role": "sensors", "canonical": "aicp.role.sensor"},
    "rollladen": {"name_de": "Rollladen", "color": "#fb923c", "icon": "mdi:blinds", "role": "cover", "canonical": "aicp.role.rollladen"},
    "schloss": {"name_de": "Schloss", "color": "#f87171", "icon": "mdi:lock", "role": "lock", "canonical": "aicp.role.schloss"},
    "tuer": {"name_de": "Tuer", "color": "#fbbf24", "icon": "mdi:door", "role": "door", "canonical": "aicp.role.tuer"},
    "fenster": {"name_de": "Fenster", "color": "#22d3ee", "icon": "mdi:window-open", "role": "window", "canonical": "aicp.role.fenster"},
    "energie": {"name_de": "Energie", "color": "#4ade80", "icon": "mdi:flash", "role": "energy", "canonical": "aicp.role.energie"},
    "sicherheit": {"name_de": "Sicherheit", "color": "#ef4444", "icon": "mdi:shield", "role": "other", "canonical": "aicp.role.sicherheit"},
    "styx": {"name_de": "Styx", "color": "#8b5cf6", "icon": "mdi:robot", "role": "other", "canonical": "aicp.role.styx"},
}

# Mapping from canonical tag IDs (tags.yaml) to short tag names (zone_automation)
CANONICAL_TO_SHORT: dict[str, str] = {
    info["canonical"]: short for short, info in TAG_DEFINITIONS.items()
}
SHORT_TO_CANONICAL: dict[str, str] = {
    short: info["canonical"] for short, info in TAG_DEFINITIONS.items()
}

# Auto-detect role from entity_id domain
DOMAIN_TO_ROLE: dict[str, str] = {
    "light": "lights",
    "binary_sensor": "motion",  # refined by entity_id keywords
    "sensor": "sensors",
    "media_player": "media",
    "climate": "climate",
    "cover": "cover",
    "lock": "lock",
    "fan": "climate",
    "switch": "other",
    "input_boolean": "other",
}

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
}


def detect_entity_role(entity_id: str) -> str:
    """Auto-detect entity role from its domain and ID keywords."""
    parts = entity_id.split(".")
    domain = parts[0] if parts else ""
    name = parts[1] if len(parts) > 1 else ""

    # Check name hints first (more specific)
    name_lower = name.lower()
    for hint, role in ENTITY_ID_ROLE_HINTS.items():
        if hint in name_lower:
            return role

    return DOMAIN_TO_ROLE.get(domain, "other")


def detect_entity_tags(entity_id: str) -> list[str]:
    """Auto-detect tags from entity_id."""
    tags = []
    name = entity_id.split(".")[-1].lower() if "." in entity_id else entity_id.lower()

    for tag_id, info in TAG_DEFINITIONS.items():
        if tag_id in name:
            tags.append(tag_id)

    # Domain-based tags
    domain = entity_id.split(".")[0] if "." in entity_id else ""
    domain_tag_map = {
        "light": "licht",
        "media_player": "medien",
        "climate": "klima",
        "cover": "rollladen",
        "lock": "schloss",
        "sensor": "sensor",
    }
    dt = domain_tag_map.get(domain)
    if dt and dt not in tags:
        tags.append(dt)

    return tags


# ── Engine ───────────────────────────────────────────────────────────────────


class ZoneAutomationController:
    """Per-zone automation engine combining presence, light, and music control."""

    def __init__(self) -> None:
        # Per-zone configurations
        self._configs: dict[str, ZoneAutomationConfig] = {}

        # Runtime state per zone
        self._states: dict[str, ZonePresenceState] = {}

        # Entity assignments per zone: zone_id -> list[ZoneEntityAssignment]
        self._entity_assignments: dict[str, list[ZoneEntityAssignment]] = {}
        self._entity_assignments_revision: int = 0
        self._zone_entity_revisions: dict[str, int] = {}
        self._zone_entity_updated_at: dict[str, float] = {}

        # Optional MusikwolkeBridge for executing music actions
        self._music_bridge: Any | None = None

        # Per-zone mood state (mood name string, default "neutral")
        self._zone_moods: dict[str, str] = {}

    def _touch_entity_assignments(self, zone_id: str) -> None:
        """Update revision + timestamp counters for entity assignments.

        `zone_entity_revisions` mirrors the global revision value so consumers can
        safely do `changed_since` comparisons with the same revision counter.
        """
        self._entity_assignments_revision += 1
        self._zone_entity_revisions[zone_id] = self._entity_assignments_revision
        self._zone_entity_updated_at[zone_id] = time.time()

    def _normalize_entity_tags(self, tags: list[str] | None) -> list[str]:
        """Normalize tag lists to deterministic unique order."""
        if tags is None:
            return []

        normalized = []
        for raw in tags:
            tag = str(raw).strip()
            if tag and tag not in normalized:
                normalized.append(tag)
        return normalized

    def set_music_bridge(self, bridge: Any) -> None:
        """Attach a MusikwolkeBridge to auto-execute music actions."""
        self._music_bridge = bridge

    # ── Mood management ─────────────────────────────────────────────────

    def set_mood(self, zone_id: str, mood_state: str) -> dict[str, Any]:
        """Set the current mood for a zone.

        Args:
            zone_id: Zone identifier.
            mood_state: Mood state name (e.g., 'relax', 'focus', 'active').

        Returns:
            Dict with applied mood adjustment profile.
        """
        mood_key = mood_state.lower().strip()
        self._zone_moods[zone_id] = mood_key
        adjustment = get_mood_adjustment(mood_key)
        known = mood_key in MOOD_ADJUSTMENTS
        logger.info(
            "Zone '%s' mood set to '%s' (known=%s, brightness_factor=%.1f, color_temp_k=%d)",
            zone_id, mood_key, known,
            adjustment["brightness_factor"], adjustment["color_temp_k"],
        )
        return {
            "zone_id": zone_id,
            "mood": mood_key,
            "known_profile": known,
            "adjustment": adjustment,
        }

    def get_mood(self, zone_id: str) -> str:
        """Get the current mood for a zone (default: 'neutral')."""
        return self._zone_moods.get(zone_id, "neutral")

    def get_mood_adjustment_for_zone(self, zone_id: str) -> dict[str, float | int]:
        """Get the active mood adjustment profile for a zone."""
        return get_mood_adjustment(self.get_mood(zone_id))

    # ── Configuration ────────────────────────────────────────────────────

    def get_zone_config(self, zone_id: str) -> ZoneAutomationConfig:
        """Get or create zone automation config."""
        if zone_id not in self._configs:
            self._configs[zone_id] = ZoneAutomationConfig(zone_id=zone_id)
        return self._configs[zone_id]

    def set_zone_config(self, zone_id: str, config_data: dict[str, Any]) -> ZoneAutomationConfig:
        """Update zone automation config from dict (partial updates supported)."""
        current = self.get_zone_config(zone_id)

        if "zone_name" in config_data:
            current.zone_name = str(config_data["zone_name"] or "").strip()

        if "zone_type" in config_data:
            normalized = _normalize_zone_type(config_data.get("zone_type", ""))
            if normalized:
                current.zone_type = normalized

        if "enabled_modules" in config_data and isinstance(config_data["enabled_modules"], (list, set, tuple)):
            current.enabled_modules = {
                str(module_id).strip()
                for module_id in config_data["enabled_modules"]
                if str(module_id).strip()
            }

        if "ha_entities" in config_data and isinstance(config_data["ha_entities"], list):
            current.ha_entities = [str(entity_id).strip() for entity_id in config_data["ha_entities"] if str(entity_id).strip()]
            current._ha_entities = list(current.ha_entities)

        if "automation_mode" in config_data:
            mode = config_data["automation_mode"]
            if mode in AUTOMATION_MODES:
                current.automation_mode = mode

        # Update light config
        if "light" in config_data:
            lc = config_data["light"]
            for key, val in lc.items():
                if hasattr(current.light, key):
                    setattr(current.light, key, val)

        # Update music config
        if "music" in config_data:
            mc = config_data["music"]
            for key, val in mc.items():
                if hasattr(current.music, key):
                    setattr(current.music, key, val)

        # Update module configs
        if "modules" in config_data:
            for mid, mod_data in config_data["modules"].items():
                if mid in current.modules and isinstance(mod_data, dict):
                    mod = current.modules[mid]
                    for spec in mod.get_field_specs():
                        if spec.key in mod_data:
                            setattr(mod, spec.key, mod_data[spec.key])

        return current

    def delete_zone(self, zone_id: str) -> bool:
        """Delete a zone config and all runtime/assignment state."""
        removed = self._configs.pop(zone_id, None)
        if removed is None:
            return False

        self._states.pop(zone_id, None)
        self._entity_assignments.pop(zone_id, None)
        self._zone_moods.pop(zone_id, None)
        return True

    def get_all_configs(self) -> dict[str, dict[str, Any]]:
        """Get all zone configurations."""
        return {zid: cfg.to_dict() for zid, cfg in self._configs.items()}

    def sync_habitus_zones(self, zones: list[dict[str, Any]],
                           clear_missing: bool = False) -> dict[str, Any]:
        """Sync HA area/zone topology into HubZoneEngine and ZoneAutomationController.

        This is the canonical HA→Core zone sync point.  It:
        1. Registers each zone as a Room (using area_id) + Zone in HubZoneEngine
           so zone_editor and habitus_zones APIs return them immediately.
        2. Creates ZoneAutomationConfig entries for any new zones.
        3. Optionally removes zones not present in the payload.

        Args:
            zones: list of zone specs from HA. Each dict may contain:
                - zone_id (str): unique zone/area identifier
                - name (str): display name
                - area_id (str): HA area id (used as room_id)
                - entities (list[str]): entity_ids belonging to this zone
                - icon (str): Material Design icon
                - priority (int): matching priority
            clear_missing: if True, delete zones not in the payload.

        Returns:
            dict with keys: synced, created, deleted, habitus_zones,
                            ha_zones, entity_zone_map
        """
        result = {
            "synced": 0,
            "created": 0,
            "deleted": 0,
            "habitus_zones": [],
            "ha_zones": [],
            "entity_zone_map": {},
        }

        # Lazy-import HubZoneEngine only when called
        try:
            from copilot_core.hub.habitus_zones import HabitusZoneEngine
        except ImportError:
            logger.warning("HubZoneEngine not available — skipping habitus sync")
            return result

        # Get or create singleton HubZoneEngine
        # We store a reference on self so it survives across calls in the same process
        if not hasattr(self, "_hub_zones"):
            self._hub_zones = HabitusZoneEngine()
            logger.info("Created HubZoneEngine singleton for zone sync")

        hub = self._hub_zones
        seen_ids = set()

        for spec in zones:
            zid = str(spec.get("zone_id") or spec.get("area_id") or "").strip()
            if not zid:
                continue
            seen_ids.add(zid)

            name = str(spec.get("name") or zid).strip()
            area_id = str(spec.get("area_id") or zid).strip()
            entities = spec.get("entities") or []
            icon = str(spec.get("icon") or "mdi:home-floor-1").strip()
            priority = int(spec.get("priority") or 0)

            is_new_config = zid not in self._configs
            if is_new_config:
                self.get_zone_config(zid)  # creates default ZoneAutomationConfig
                result["created"] += 1

            config_updates: dict[str, Any] = {}
            normalized_zone_type = _normalize_zone_type(spec.get("zone_type"))
            if normalized_zone_type:
                config_updates["zone_type"] = normalized_zone_type
            if "enabled_modules" in spec:
                raw_modules = spec.get("enabled_modules")
                if isinstance(raw_modules, (list, set, tuple)):
                    config_updates["enabled_modules"] = {
                        str(module_id).strip()
                        for module_id in raw_modules
                        if str(module_id).strip()
                    }
            if config_updates:
                self.set_zone_config(zid, config_updates)

            # ── Register in HubZoneEngine ─────────────────────────────
            room = hub._rooms.get(area_id)
            if room is None:
                hub.register_room(
                    room_id=area_id,
                    name=name,
                    area_id=area_id,
                    entities=list(entities),
                    icon=icon or "mdi:door",
                )
                logger.debug("Registered room %s in HubZoneEngine", area_id)

            zone = hub._zones.get(zid)
            if zone is None:
                hub.create_zone(
                    zone_id=zid,
                    name=name,
                    room_ids=[area_id],
                    icon=icon or "mdi:home-floor-1",
                    priority=priority,
                )
                logger.info("Created HubZone '%s' via sync", zid)

            # Update room entities from HA payload
            hub.update_room_entities(area_id, list(entities))

            # Build entity→zone map for HA response
            for eid in entities:
                result["entity_zone_map"][eid] = zid

            # Build ha_zones response entry
            result["ha_zones"].append({
                "zone_id": zid,
                "name": name,
                "area_id": area_id,
                "icon": icon,
                "priority": priority,
                "entity_count": len(entities),
            })

            result["synced"] += 1

        # ── Clear missing zones ─────────────────────────────────────
        if clear_missing:
            all_habitus_ids = set(hub._zones.keys())
            to_delete = all_habitus_ids - seen_ids
            for zid in to_delete:
                try:
                    hub.delete_zone(zid)
                    result["deleted"] += 1
                    logger.info("Deleted missing HubZone '%s'", zid)
                except Exception:
                    pass

        # Return HubZoneEngine overview
        try:
            overview = hub.get_overview()
            result["habitus_zones"] = overview.zones if overview else []
        except Exception:
            logger.debug("Could not get hub overview (may be empty)")

        logger.info("sync_habitus_zones: synced=%d created=%d deleted=%d",
                    result["synced"], result["created"], result["deleted"])
        return result


    # ── Presence events ──────────────────────────────────────────────────

    def _get_state(self, zone_id: str) -> ZonePresenceState:
        if zone_id not in self._states:
            self._states[zone_id] = ZonePresenceState()
        return self._states[zone_id]

    def set_automation_mode(self, zone_id: str, mode: str) -> bool:
        """Set automation mode for a zone (off/learning/autonomy)."""
        if mode not in AUTOMATION_MODES:
            return False
        config = self.get_zone_config(zone_id)
        config.automation_mode = mode
        logger.info("Zone '%s' automation mode → %s", zone_id, mode)
        return True

    def get_automation_mode(self, zone_id: str) -> str:
        """Get current automation mode for a zone."""
        return self.get_zone_config(zone_id).automation_mode

    def on_presence_detected(self, zone_id: str) -> dict[str, Any]:
        """Handle presence detection in a zone.

        Returns dict of actions to take (light_on, music_start, etc.)
        Respects automation_mode: off=no actions, learning=record only, autonomy=full.
        """
        config = self.get_zone_config(zone_id)
        state = self._get_state(zone_id)
        now = time.monotonic()
        actions: dict[str, Any] = {"zone_id": zone_id}

        state.occupied = True
        if state.last_detected_ts == 0.0:
            state.last_detected_ts = now
        state.absence_confirmed = False

        actions["automation_mode"] = config.automation_mode

        # Mode: off — just record state, no actions
        if config.automation_mode == "off":
            return actions

        # Check if presence delay has passed
        elapsed = now - state.last_detected_ts
        presence_delay = config.light.presence_delay_s

        if elapsed >= presence_delay:
            state.presence_confirmed = True

            # Mode: learning — record confirmed presence but don't trigger
            if config.automation_mode == "learning":
                actions["learning_event"] = "presence_confirmed"
                return actions

            # Mode: autonomy — full automation
            # Light automation
            if config.light.enabled and not state.lights_on:
                target = self._compute_target_brightness(zone_id, config)
                actions["light_on"] = True
                actions["brightness_pct"] = target
                actions["color_temp_k"] = self._compute_mood_color_temp(zone_id, config)
                actions["color_temp_auto"] = config.light.color_temp_auto
                actions["transition_s"] = self._get_mood_transition(zone_id, config)
                actions["mood"] = self.get_mood(zone_id)
                state.lights_on = True
                state.current_brightness_pct = target
                state.dampened_brightness_pct = target

            # Music automation
            if config.music.enabled and config.music.presence_auto_play:
                music_delay = config.music.presence_delay_s
                if elapsed >= music_delay and not state.music_playing:
                    actions["music_start"] = True
                    actions["music_volume_pct"] = config.music.default_volume_pct
                    actions["music_follow"] = config.music.follow_mode
                    state.music_playing = True
                    state.music_triggered_at = now

        # Auto-execute music actions via MusikwolkeBridge if wired
        if self._music_bridge and (actions.get("music_start") or actions.get("music_follow")):
            try:
                self._music_bridge.execute_actions(actions)
            except Exception:
                logger.exception("MusikwolkeBridge.execute_actions failed for zone '%s'", zone_id)

        return actions
    def on_presence_cleared(self, zone_id: str) -> dict[str, Any]:
        """Handle presence cleared in a zone.

        Returns dict of actions to take (light_off, music_pause, etc.)
        """
        config = self.get_zone_config(zone_id)
        state = self._get_state(zone_id)
        now = time.monotonic()
        actions: dict[str, Any] = {"zone_id": zone_id}

        state.occupied = False
        if state.last_cleared_ts == 0.0 or state.last_detected_ts > state.last_cleared_ts:
            state.last_cleared_ts = now
        state.presence_confirmed = False

        actions["automation_mode"] = config.automation_mode

        # Mode: off or learning — record state only, no automation actions
        if config.automation_mode in ("off", "learning"):
            if config.automation_mode == "learning":
                actions["learning_event"] = "presence_cleared"
            return actions

        # Mode: autonomy — check absence delay and trigger actions
        elapsed = now - state.last_cleared_ts

        # Light off after absence delay
        if config.light.enabled and state.lights_on:
            if elapsed >= config.light.absence_delay_s:
                actions["light_off"] = True
                state.lights_on = False
                state.current_brightness_pct = 0
                state.absence_confirmed = True

        # Music pause after absence delay
        if config.music.enabled and state.music_playing:
            if elapsed >= config.music.absence_pause_s:
                actions["music_pause"] = True
                actions["music_fade_s"] = config.music.fade_duration_s
                state.music_playing = False

        # Auto-execute music pause via MusikwolkeBridge if wired
        if self._music_bridge and actions.get("music_pause"):
            try:
                self._music_bridge.execute_actions(actions)
            except Exception:
                logger.exception("MusikwolkeBridge.execute_actions (pause) failed for zone '%s'", zone_id)

        return actions

    def update_brightness(self, zone_id: str, current_indoor_lux: float,
                          current_outdoor_lux: float) -> dict[str, Any]:
        """Update brightness and compute dampened target.

        Applies hysteresis dead-band to prevent rapid toggling.
        Returns adjustment actions if brightness should change.
        """
        config = self.get_zone_config(zone_id)
        state = self._get_state(zone_id)

        if not config.light.enabled or not state.lights_on:
            return {"zone_id": zone_id, "adjust": False}

        # Compute raw target brightness
        raw_target = self._compute_target_brightness(
            zone_id, config, current_indoor_lux, current_outdoor_lux
        )

        # Apply hysteresis dampening
        band = config.light.dampening_band_pct
        current = state.dampened_brightness_pct
        diff = abs(raw_target - current)

        if diff <= band:
            # Within dead-band: no change
            return {"zone_id": zone_id, "adjust": False, "dampened": True}

        # Outside dead-band: adjust
        state.dampened_brightness_pct = raw_target
        state.current_brightness_pct = raw_target

        result: dict[str, Any] = {
            "zone_id": zone_id,
            "adjust": True,
            "brightness_pct": raw_target,
            "raw_target": raw_target,
            "previous": current,
        }

        # Include mood-aware color temp and transition when enabled
        if config.light.mood_aware_enabled:
            result["color_temp_k"] = self._compute_mood_color_temp(zone_id, config)
            result["transition_s"] = self._get_mood_transition(zone_id, config)
            result["mood"] = self.get_mood(zone_id)

        return result

    def _compute_target_brightness(self, zone_id: str, config: ZoneAutomationConfig,
                                   indoor_lux: float = 0.0,
                                   outdoor_lux: float = 0.0) -> int:
        """Compute target brightness percentage considering indoor/outdoor compensation and mood."""
        target_pct = config.light.brightness_target_pct

        if config.light.lux_outdoor_compensation and outdoor_lux > 0 and indoor_lux >= 0:
            # Raumausleuchtung: compute how much artificial light is needed
            target_lux = config.light.lux_indoor_target
            deficit = max(0, target_lux - indoor_lux)
            if target_lux > 0:
                compensation_pct = int(deficit / target_lux * 100)
                # Blend user target with compensation
                target_pct = min(100, max(config.light.brightness_min_pct,
                                          int(target_pct * compensation_pct / 100)))

        base_brightness = max(config.light.brightness_min_pct, min(100, target_pct))

        # Apply mood-based brightness factor when mood_aware_enabled
        if config.light.mood_aware_enabled:
            adjustment = self.get_mood_adjustment_for_zone(zone_id)
            brightness_factor = float(adjustment["brightness_factor"])
            base_brightness = int(base_brightness * brightness_factor)
            base_brightness = max(0, min(100, base_brightness))

        return base_brightness

    def _compute_mood_color_temp(self, zone_id: str, config: ZoneAutomationConfig) -> int:
        """Compute blended color temperature from zone config and mood profile.

        When mood_aware_enabled, blends zone's configured color_temp_k with
        the mood profile's recommended color_temp_k (50/50 average).
        When mood_aware is disabled, returns the zone's configured color temp.
        """
        zone_temp = config.light.color_temp_k
        if not config.light.mood_aware_enabled:
            return zone_temp
        adjustment = self.get_mood_adjustment_for_zone(zone_id)
        mood_temp = int(adjustment["color_temp_k"])
        blended = (zone_temp + mood_temp) // 2
        # Clamp to valid color temperature range
        return max(2200, min(6500, blended))

    def _get_mood_transition(self, zone_id: str, config: ZoneAutomationConfig) -> float:
        """Get mood-recommended transition duration in seconds."""
        if not config.light.mood_aware_enabled:
            return 0.0
        adjustment = self.get_mood_adjustment_for_zone(zone_id)
        return float(adjustment["transition_s"])

    # ── Zone state query ─────────────────────────────────────────────────

    def get_zone_state(self, zone_id: str) -> dict[str, Any]:
        """Get runtime state for a zone (includes mood info)."""
        config = self.get_zone_config(zone_id)
        state = self._get_state(zone_id)
        mood = self.get_mood(zone_id)
        adjustment = self.get_mood_adjustment_for_zone(zone_id)
        return {
            "zone_id": zone_id,
            "config": config.to_dict(),
            "state": {
                "occupied": state.occupied,
                "presence_confirmed": state.presence_confirmed,
                "automation_mode": config.automation_mode,
                "lights_on": state.lights_on,
                "current_brightness_pct": state.current_brightness_pct,
                "dampened_brightness_pct": state.dampened_brightness_pct,
                "music_playing": state.music_playing,
                "current_mood": mood,
                "mood_brightness_factor": float(adjustment["brightness_factor"]),
                "mood_color_temp": int(adjustment["color_temp_k"]),
            },
        }

    def get_all_states(self) -> list[dict[str, Any]]:
        """Get all zone states."""
        all_zones = set(self._configs.keys()) | set(self._states.keys())
        return [self.get_zone_state(zid) for zid in sorted(all_zones)]

    def get_dashboard(self) -> dict[str, Any]:
        """Full automation dashboard."""
        states = self.get_all_states()
        active_lights = sum(1 for s in states if s["state"]["lights_on"])
        active_music = sum(1 for s in states if s["state"]["music_playing"])
        occupied = sum(1 for s in states if s["state"]["occupied"])
        return {
            "zones": states,
            "summary": {
                "total_zones": len(states),
                "occupied_zones": occupied,
                "active_lights": active_lights,
                "active_music": active_music,
            },
        }

    # ── Entity management ────────────────────────────────────────────────

    def add_entity(self, zone_id: str, entity_id: str,
                   role: str | None = None, tags: list[str] | None = None,
                   display_name: str = "", source: str = "manual") -> ZoneEntityAssignment:
        """Add an entity to a zone with auto-detected role and tags."""
        if role is None:
            role = detect_entity_role(entity_id)

        normalized_tags = self._normalize_entity_tags(detect_entity_tags(entity_id) if tags is None else tags)

        assignment = ZoneEntityAssignment(
            entity_id=entity_id,
            zone_id=zone_id,
            role=role,
            tags=normalized_tags,
            display_name=display_name or entity_id.split(".")[-1].replace("_", " ").title(),
            source=source,
        )

        if zone_id not in self._entity_assignments:
            self._entity_assignments[zone_id] = []

        for existing in self._entity_assignments[zone_id]:
            if existing.entity_id == entity_id:
                if (
                    existing.role == assignment.role
                    and existing.tags == assignment.tags
                    and existing.display_name == assignment.display_name
                    and existing.source == assignment.source
                ):
                    return existing
                existing.role = assignment.role
                existing.tags = assignment.tags
                existing.display_name = assignment.display_name
                existing.source = assignment.source
                self._touch_entity_assignments(zone_id)
                return existing

        self._entity_assignments[zone_id].append(assignment)
        self._touch_entity_assignments(zone_id)
        return assignment

    def sync_entities_from_topology(self, zone_id: str, entities: list[Any]) -> list[ZoneEntityAssignment]:
        """Replace zone assignments from a synced HA topology payload."""
        synced: list[ZoneEntityAssignment] = []
        seen: set[str] = set()

        for item in entities or []:
            entity_id = ""
            role: str | None = None
            tags: list[str] | None = None
            display_name = ""

            if isinstance(item, str):
                entity_id = item.strip()
            elif isinstance(item, dict):
                entity_id = str(item.get("entity_id", "")).strip()
                candidate_role = str(item.get("role", "")).strip()
                role = candidate_role or None
                candidate_tags = item.get("tags")
                if isinstance(candidate_tags, list):
                    tags = [str(tag).strip() for tag in candidate_tags if str(tag).strip()]
                display_name = str(
                    item.get("display_name")
                    or item.get("friendly_name")
                    or item.get("name")
                    or ""
                ).strip()
            else:
                entity_id = str(item).strip()

            if not entity_id or entity_id in seen:
                continue

            seen.add(entity_id)
            synced.append(
                ZoneEntityAssignment(
                    entity_id=entity_id,
                    zone_id=zone_id,
                    role=role or detect_entity_role(entity_id),
                    tags=tags or detect_entity_tags(entity_id),
                    display_name=display_name or entity_id.split(".")[-1].replace("_", " ").title(),
                    source="ha_sync",
                )
            )

        self._entity_assignments[zone_id] = synced
        return list(synced)

    def remove_entity(self, zone_id: str, entity_id: str) -> bool:
        """Remove an entity from a zone."""
        if zone_id not in self._entity_assignments:
            return False
        before = len(self._entity_assignments[zone_id])
        self._entity_assignments[zone_id] = [
            a for a in self._entity_assignments[zone_id]
            if a.entity_id != entity_id
        ]
        removed = len(self._entity_assignments[zone_id]) < before
        if removed:
            self._touch_entity_assignments(zone_id)
        return removed

    def get_zone_entities(self, zone_id: str) -> list[dict[str, Any]]:
        """Get all entities assigned to a zone."""
        assignments = self._entity_assignments.get(zone_id, [])
        return [asdict(a) for a in assignments]

    def get_zone_entities_by_role(self, zone_id: str) -> dict[str, list[dict[str, Any]]]:
        """Get zone entities grouped by role."""
        assignments = self._entity_assignments.get(zone_id, [])
        by_role: dict[str, list[dict[str, Any]]] = {}
        for a in assignments:
            by_role.setdefault(a.role, []).append(asdict(a))
        return by_role

    def update_entity_tags(self, zone_id: str, entity_id: str,
                           tags: list[str]) -> bool:
        """Update tags for an entity in a zone."""
        normalized_tags = self._normalize_entity_tags(tags)
        assignments = self._entity_assignments.get(zone_id, [])
        for a in assignments:
            if a.entity_id == entity_id:
                if a.tags == normalized_tags:
                    return True
                a.tags = normalized_tags
                self._touch_entity_assignments(zone_id)
                return True
        return False

    def update_entity_role(self, zone_id: str, entity_id: str,
                           role: str) -> bool:
        """Update role for an entity in a zone."""
        if role not in ENTITY_ROLES:
            return False
        assignments = self._entity_assignments.get(zone_id, [])
        for a in assignments:
            if a.entity_id == entity_id:
                if a.role == role:
                    return True
                a.role = role
                self._touch_entity_assignments(zone_id)
                return True
        return False

    def get_all_entities(self) -> dict[str, list[dict[str, Any]]]:
        """Get all entity assignments across all zones."""
        return {
            zid: [asdict(a) for a in assignments]
            for zid, assignments in self._entity_assignments.items()
        }

    def get_zone_entities_read_model(self, zone_id: str, *, compact: bool = False) -> dict[str, Any]:
        """Return a deterministic read-model payload for entity assignments in one zone."""
        zone_config = self.get_zone_config(zone_id)
        assignments = self._entity_assignments.get(zone_id, [])

        sorted_assignments = sorted(assignments, key=lambda a: (a.role, a.entity_id))
        by_role: dict[str, list[dict[str, Any]]] = {}
        source_counts: dict[str, int] = {}

        serialized = [asdict(a) for a in sorted_assignments]
        for assignment in serialized:
            by_role.setdefault(assignment["role"], []).append(assignment)
            source = assignment.get("source", "manual")
            source_counts[source] = source_counts.get(source, 0) + 1

        model = {
            "zone_id": zone_id,
            "zone_name": zone_config.zone_name,
            "entity_count": len(serialized),
            "role_count": {role: len(entities) for role, entities in by_role.items()},
            "source_count": source_counts,
            "revision": self._zone_entity_revisions.get(zone_id, 0),
            "updated_at": self._zone_entity_updated_at.get(zone_id, 0.0),
            "compact": compact,
        }

        if compact:
            return model

        model["entities"] = serialized
        model["entities_by_role"] = by_role
        return model

    def _compact_zone_payloads(self, zones: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Return a compact deterministic zone payload for transport-sensitive consumers."""
        compact_zones: list[dict[str, Any]] = []
        for zone in zones:
            compact_zones.append({
                "zone_id": zone["zone_id"],
                "zone_name": zone["zone_name"],
                "revision": zone["revision"],
                "updated_at": zone["updated_at"],
                "entity_count": zone["entity_count"],
                "role_count": zone.get("role_count", {}),
                "source_count": zone.get("source_count", {}),
            })
        return compact_zones

    def get_all_entities_read_model(
        self, *,
        since_revision: int | None = None,
        deltas: bool = False,
        compact: bool = False,
    ) -> dict[str, Any]:
        """Return a deterministic read-model for all zone entity assignments.

        If `since_revision` is set and `deltas=True`, only zones whose entity
        assignment revision is newer than `since_revision` are returned.

        If `compact=True`, entity lists are removed and each zone is reduced to
        deterministic metadata and counters for lower payload consumers.
        """
        zone_ids = sorted(set(self._configs.keys()) | set(self._entity_assignments.keys()))
        all_zones = [self.get_zone_entities_read_model(zid) for zid in zone_ids]
        all_entity_count = sum(z["entity_count"] for z in all_zones)
        max_updated_at = max((zone["updated_at"] for zone in all_zones), default=0.0)

        summary = {
            "zone_count": len(all_zones),
            "entity_count": all_entity_count,
            "revision": self._entity_assignments_revision,
            "updated_at": max_updated_at,
            "compact": compact,
        }

        if since_revision is not None and deltas:
            changed_zones = [
                zone for zone in all_zones if zone["revision"] > since_revision
            ]
            payload_zones = self._compact_zone_payloads(changed_zones) if compact else changed_zones
            return {
                "zones": payload_zones,
                "summary": {
                    **summary,
                    "returned_zone_count": len(payload_zones),
                    "returned_entity_count": sum(zone["entity_count"] for zone in changed_zones),
                    "delta_from_revision": since_revision,
                    "delta_to_revision": self._entity_assignments_revision,
                },
                "delta": {
                    "enabled": True,
                    "zone_ids": [zone["zone_id"] for zone in changed_zones],
                },
            }

        payload_zones = self._compact_zone_payloads(all_zones) if compact else all_zones
        return {
            "zones": payload_zones,
            "summary": summary,
        }

    def import_from_example_config(self, zone_entities: dict[str, dict[str, list[str]]]) -> int:
        """Import entities from example config format.

        Args:
            zone_entities: Dict[zone_id, Dict[role, List[entity_id]]]

        Returns:
            Number of entities imported.
        """
        count = 0
        for zone_id, roles in zone_entities.items():
            for role, entity_ids in roles.items():
                for eid in entity_ids:
                    self.add_entity(zone_id, eid, role=role, source="import")
                    count += 1
        return count

    def get_tag_definitions(self) -> dict[str, dict[str, str]]:
        """Get all available tag definitions."""
        return TAG_DEFINITIONS.copy()

    def get_role_definitions(self) -> list[str]:
        """Get all available entity roles."""
        return ENTITY_ROLES.copy()

    def search_entities(self, query: str) -> list[dict[str, Any]]:
        """Search entities across all zones by entity_id, name, role, or tag."""
        query_lower = query.lower()
        results = []
        for zone_id, assignments in self._entity_assignments.items():
            for a in assignments:
                if (query_lower in a.entity_id.lower()
                        or query_lower in a.display_name.lower()
                        or query_lower in a.role.lower()
                        or any(query_lower in t for t in a.tags)):
                    d = asdict(a)
                    d["zone_id"] = zone_id
                    results.append(d)
        return results

    # ── Periodic evaluation ──────────────────────────────────────────────

    def evaluate_all_zones(self) -> dict[str, Any]:
        """Evaluate all zones and return actions + state snapshot.

        Called periodically (e.g., every 30-60s) to:
        - Check absence timeouts (auto-off lights/music after presence clears)
        - Produce a snapshot for webhook push to HA
        """
        now = time.monotonic()
        results: list[dict[str, Any]] = []

        for zone_id in list(self._configs.keys()):
            config = self._configs[zone_id]
            state = self._get_state(zone_id)

            zone_result: dict[str, Any] = {"zone_id": zone_id, "actions": []}

            # Check absence timeout: lights
            if (state.lights_on and not state.occupied
                    and state.absence_confirmed
                    and config.light.enabled
                    and config.automation_mode == "autonomy"):
                # Already handled by on_presence_cleared; this is a safety net
                zone_result["state"] = "absence_confirmed"

            # Check absence timeout: music
            if (state.music_playing and not state.occupied
                    and state.absence_confirmed
                    and config.music.enabled
                    and config.automation_mode == "autonomy"):
                zone_result["state"] = "absence_confirmed"

            mood = self.get_mood(zone_id)
            adjustment = self.get_mood_adjustment_for_zone(zone_id)
            zone_result["snapshot"] = {
                "occupied": state.occupied,
                "lights_on": state.lights_on,
                "brightness_pct": state.current_brightness_pct,
                "music_playing": state.music_playing,
                "automation_mode": config.automation_mode,
                "current_mood": mood,
                "mood_brightness_factor": float(adjustment["brightness_factor"]),
                "mood_color_temp": int(adjustment["color_temp_k"]),
            }
            results.append(zone_result)

        dashboard = self.get_dashboard()
        return {
            "zones": results,
            "summary": dashboard["summary"],
            "evaluated_at": time.time(),
        }


class ZoneAutomationHub:
    """Compatibility facade for legacy integration tests."""

    def __init__(self, event_bus: Any = None, zone_registry: Any = None):
        self.event_bus = event_bus
        self.zone_registry = zone_registry
        self._zone_states: Dict[str, str] = {}

    def update_zone_state(self, zone_id: str, state: str) -> None:
        self._zone_states[zone_id] = state
        if self.event_bus and hasattr(self.event_bus, "emit"):
            self.event_bus.emit("zone_state_updated", {"zone_id": zone_id, "state": state})
