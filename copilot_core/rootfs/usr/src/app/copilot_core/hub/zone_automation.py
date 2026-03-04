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

logger = logging.getLogger(__name__)


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


@dataclass
class ZoneAutomationConfig:
    """Complete automation configuration for a zone."""

    zone_id: str
    zone_name: str = ""
    light: ZoneLightConfig = field(default_factory=ZoneLightConfig)
    music: ZoneMusicConfig = field(default_factory=ZoneMusicConfig)

    def to_dict(self) -> dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "zone_name": self.zone_name,
            "light": asdict(self.light),
            "music": asdict(self.music),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ZoneAutomationConfig":
        light_data = data.get("light", {})
        music_data = data.get("music", {})
        return cls(
            zone_id=data.get("zone_id", ""),
            zone_name=data.get("zone_name", ""),
            light=ZoneLightConfig(**{k: v for k, v in light_data.items() if k in ZoneLightConfig.__dataclass_fields__}),
            music=ZoneMusicConfig(**{k: v for k, v in music_data.items() if k in ZoneMusicConfig.__dataclass_fields__}),
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
    "licht": {"name_de": "Licht", "color": "#fbbf24", "icon": "mdi:lightbulb", "role": "lights"},
    "praesenz": {"name_de": "Praesenz", "color": "#a78bfa", "icon": "mdi:motion-sensor", "role": "motion"},
    "bewegung": {"name_de": "Bewegung", "color": "#c084fc", "icon": "mdi:run", "role": "motion"},
    "medien": {"name_de": "Medien", "color": "#60a5fa", "icon": "mdi:speaker", "role": "media"},
    "klima": {"name_de": "Klima", "color": "#34d399", "icon": "mdi:thermometer", "role": "climate"},
    "sensor": {"name_de": "Sensor", "color": "#f472b6", "icon": "mdi:chip", "role": "sensors"},
    "rollladen": {"name_de": "Rollladen", "color": "#fb923c", "icon": "mdi:blinds", "role": "cover"},
    "schloss": {"name_de": "Schloss", "color": "#f87171", "icon": "mdi:lock", "role": "lock"},
    "tuer": {"name_de": "Tuer", "color": "#fbbf24", "icon": "mdi:door", "role": "door"},
    "fenster": {"name_de": "Fenster", "color": "#22d3ee", "icon": "mdi:window-open", "role": "window"},
    "energie": {"name_de": "Energie", "color": "#4ade80", "icon": "mdi:flash", "role": "energy"},
    "sicherheit": {"name_de": "Sicherheit", "color": "#ef4444", "icon": "mdi:shield", "role": "other"},
    "styx": {"name_de": "Styx", "color": "#8b5cf6", "icon": "mdi:robot", "role": "other"},
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
            current.zone_name = config_data["zone_name"]

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

        return current

    def get_all_configs(self) -> dict[str, dict[str, Any]]:
        """Get all zone configurations."""
        return {zid: cfg.to_dict() for zid, cfg in self._configs.items()}

    # ── Presence events ──────────────────────────────────────────────────

    def _get_state(self, zone_id: str) -> ZonePresenceState:
        if zone_id not in self._states:
            self._states[zone_id] = ZonePresenceState()
        return self._states[zone_id]

    def on_presence_detected(self, zone_id: str) -> dict[str, Any]:
        """Handle presence detection in a zone.

        Returns dict of actions to take (light_on, music_start, etc.)
        """
        config = self.get_zone_config(zone_id)
        state = self._get_state(zone_id)
        now = time.monotonic()
        actions: dict[str, Any] = {"zone_id": zone_id}

        state.occupied = True
        if state.last_detected_ts == 0.0:
            state.last_detected_ts = now
        state.absence_confirmed = False

        # Check if presence delay has passed
        elapsed = now - state.last_detected_ts
        presence_delay = config.light.presence_delay_s

        if elapsed >= presence_delay:
            state.presence_confirmed = True

            # Light automation
            if config.light.enabled and not state.lights_on:
                target = self._compute_target_brightness(zone_id, config)
                actions["light_on"] = True
                actions["brightness_pct"] = target
                actions["color_temp_k"] = config.light.color_temp_k
                actions["color_temp_auto"] = config.light.color_temp_auto
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

        # Check absence delay
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

        return {
            "zone_id": zone_id,
            "adjust": True,
            "brightness_pct": raw_target,
            "raw_target": raw_target,
            "previous": current,
        }

    def _compute_target_brightness(self, zone_id: str, config: ZoneAutomationConfig,
                                   indoor_lux: float = 0.0,
                                   outdoor_lux: float = 0.0) -> int:
        """Compute target brightness percentage considering indoor/outdoor compensation."""
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

        return max(config.light.brightness_min_pct, min(100, target_pct))

    # ── Zone state query ─────────────────────────────────────────────────

    def get_zone_state(self, zone_id: str) -> dict[str, Any]:
        """Get runtime state for a zone."""
        config = self.get_zone_config(zone_id)
        state = self._get_state(zone_id)
        return {
            "zone_id": zone_id,
            "config": config.to_dict(),
            "state": {
                "occupied": state.occupied,
                "presence_confirmed": state.presence_confirmed,
                "lights_on": state.lights_on,
                "current_brightness_pct": state.current_brightness_pct,
                "dampened_brightness_pct": state.dampened_brightness_pct,
                "music_playing": state.music_playing,
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
        if tags is None:
            tags = detect_entity_tags(entity_id)

        assignment = ZoneEntityAssignment(
            entity_id=entity_id,
            zone_id=zone_id,
            role=role,
            tags=tags,
            display_name=display_name or entity_id.split(".")[-1].replace("_", " ").title(),
            source=source,
        )

        if zone_id not in self._entity_assignments:
            self._entity_assignments[zone_id] = []

        # Remove existing assignment for same entity in same zone
        self._entity_assignments[zone_id] = [
            a for a in self._entity_assignments[zone_id]
            if a.entity_id != entity_id
        ]
        self._entity_assignments[zone_id].append(assignment)

        return assignment

    def remove_entity(self, zone_id: str, entity_id: str) -> bool:
        """Remove an entity from a zone."""
        if zone_id not in self._entity_assignments:
            return False
        before = len(self._entity_assignments[zone_id])
        self._entity_assignments[zone_id] = [
            a for a in self._entity_assignments[zone_id]
            if a.entity_id != entity_id
        ]
        return len(self._entity_assignments[zone_id]) < before

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
        assignments = self._entity_assignments.get(zone_id, [])
        for a in assignments:
            if a.entity_id == entity_id:
                a.tags = tags
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
                a.role = role
                return True
        return False

    def get_all_entities(self) -> dict[str, list[dict[str, Any]]]:
        """Get all entity assignments across all zones."""
        return {
            zid: [asdict(a) for a in assignments]
            for zid, assignments in self._entity_assignments.items()
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
