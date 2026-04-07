"""Cross-Module Configuration Layer.

Zentrale Konfigurationsschicht für module-übergreifende Abhängigkeiten.
Vermeidet redundante Konfigurationen und erkennt Konflikte automatisch.

Modules: habitus, sonos, wecker, mood, praesenz, licht, heiz

Usage:
    from copilot_core.config.cross_module import CrossModuleConfig
    
    config = CrossModuleConfig(hass)
    await config.load()
    
    # Get unified zone config
    zone = config.get_zone("wohnbereich")
    zone.sonos_room      # "Wohnzimmer"
    zone.light_entities  # ["light.wohnzimmer", ...]
    
    # Check for conflicts
    conflicts = config.detect_conflicts()
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry, entity_registry

_LOGGER = logging.getLogger(__name__)

# Storage key for persistence
STORAGE_KEY = "copilot_core.cross_module_config"
STORAGE_VERSION = 1


@dataclass
class SonosConfig:
    """Sonos configuration for a zone."""
    room_name: str = ""
    favorite: str = ""
    uri: str = ""
    volume_default: int = 30
    volume_ramp_start: int = 10
    volume_ramp_end: int = 40
    volume_ramp_minutes: int = 5
    follow_enabled: bool = True
    musikwolke_enabled: bool = False


@dataclass
class LightConfig:
    """Light configuration for a zone."""
    entities: List[str] = field(default_factory=list)
    brightness_default: int = 80
    color_temp_kelvin: int = 4000
    ramp_minutes: int = 10
    sunrise_enabled: bool = True
    sunset_enabled: bool = True


@dataclass
class PresenceConfig:
    """Presence tracking configuration for a zone."""
    motion_entities: List[str] = field(default_factory=list)
    person_entities: List[str] = field(default_factory=list)
    illuminance_entity: str = ""
    min_dwell_time_seconds: int = 600
    auto_away_delay_seconds: int = 300


@dataclass
class AlarmConfig:
    """Alarm (Wecker) configuration for a zone."""
    enabled: bool = True
    default_time_hhmm: str = "07:00"
    repeat: str = "weekdays"  # once, daily, weekdays, weekends, custom
    custom_days: List[int] = field(default_factory=list)  # 0=Mon..6=Sun
    snooze_minutes: int = 9
    auto_dismiss_minutes: int = 30


@dataclass
class MoodConfig:
    """Mood inference configuration for a zone."""
    enabled: bool = True
    media_entities: List[str] = field(default_factory=list)
    min_dwell_time_seconds: int = 600
    action_cooldown_seconds: int = 120
    polling_interval_seconds: int = 300
    character_weighting: bool = True


@dataclass
class ZoneConfig:
    """Unified zone configuration aggregating all module configs."""
    zone_id: str
    zone_name: str = ""
    area_id: str = ""
    
    # Module-specific configs
    sonos: SonosConfig = field(default_factory=SonosConfig)
    light: LightConfig = field(default_factory=LightConfig)
    presence: PresenceConfig = field(default_factory=PresenceConfig)
    alarm: AlarmConfig = field(default_factory=AlarmConfig)
    mood: MoodConfig = field(default_factory=MoodConfig)
    
    # Metadata
    created_at: str = ""
    updated_at: str = ""
    
    # Smart defaults applied
    defaults_applied: bool = False


@dataclass
class Conflict:
    """A detected configuration conflict."""
    conflict_id: str
    severity: str  # "error", "warning", "info"
    modules: List[str]
    description: str
    resolution: str = ""
    affected_entities: List[str] = field(default_factory=list)


class CrossModuleConfig:
    """Central configuration layer for cross-module integration.
    
    Responsibilities:
    1. Unified zone registry (single source of truth)
    2. Auto-discovery of module overlaps
    3. Conflict detection and resolution suggestions
    4. Smart defaults for common integrations
    5. Persistence and migration
    """
    
    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass
        self._zones: Dict[str, ZoneConfig] = {}
        self._conflicts: List[Conflict] = []
        self._loaded = False
        self._store: Any = None
    
    async def load(self) -> None:
        """Load configuration from storage and auto-discover zones."""
        from homeassistant.helpers.storage import Store
        
        self._store = Store(self._hass, STORAGE_VERSION, STORAGE_KEY)
        
        # Try to load persisted config
        data = await self._store.async_load()
        if data:
            await self._load_from_data(data)
            _LOGGER.info("Loaded cross-module config: %d zones", len(self._zones))
        else:
            _LOGGER.info("No persisted config found, will auto-discover")
        
        # Auto-discover zones from HA
        await self._auto_discover_zones()
        
        # Apply smart defaults
        self._apply_smart_defaults()
        
        # Detect conflicts
        await self._detect_conflicts()
        
        self._loaded = True
    
    async def save(self) -> None:
        """Persist configuration to storage."""
        if not self._store:
            _LOGGER.warning("Cannot save: storage not initialized")
            return
        
        data = self._to_data()
        await self._store.async_save(data)
        _LOGGER.debug("Saved cross-module config: %d zones", len(self._zones))
    
    async def reload(self) -> None:
        """Reload configuration from storage."""
        self._loaded = False
        await self.load()
    
    # ── Zone Management ───────────────────────────────────────────────
    
    def get_zone(self, zone_id: str) -> Optional[ZoneConfig]:
        """Get unified zone configuration."""
        return self._zones.get(zone_id)
    
    def get_all_zones(self) -> List[ZoneConfig]:
        """Get all zone configurations."""
        return list(self._zones.values())
    
    def set_zone(self, zone: ZoneConfig) -> None:
        """Set or update a zone configuration."""
        zone.updated_at = datetime.now(timezone.utc).isoformat()
        self._zones[zone.zone_id] = zone
        _LOGGER.debug("Updated zone config: %s", zone.zone_id)
    
    def remove_zone(self, zone_id: str) -> bool:
        """Remove a zone configuration."""
        if zone_id in self._zones:
            del self._zones[zone_id]
            _LOGGER.debug("Removed zone config: %s", zone_id)
            return True
        return False
    
    # ── Conflict Detection ────────────────────────────────────────────
    
    def get_conflicts(self) -> List[Conflict]:
        """Get all detected conflicts."""
        return list(self._conflicts)
    
    def get_conflicts_for_zone(self, zone_id: str) -> List[Conflict]:
        """Get conflicts affecting a specific zone."""
        return [
            c for c in self._conflicts
            if zone_id in c.affected_entities
        ]
    
    async def detect_conflicts(self) -> List[Conflict]:
        """Run conflict detection and return results."""
        await self._detect_conflicts()
        return self._conflicts
    
    async def _detect_conflicts(self) -> None:
        """Detect configuration conflicts across modules."""
        self._conflicts = []
        
        # 1. Sonos room mapping conflicts
        await self._check_sonos_conflicts()
        
        # 2. Light entity conflicts
        await self._check_light_conflicts()
        
        # 3. Motion/presence entity conflicts
        await self._check_presence_conflicts()
        
        # 4. Module-specific conflicts
        await self._check_module_conflicts()
        
        if self._conflicts:
            _LOGGER.warning("Detected %d cross-module conflicts", len(self._conflicts))
        else:
            _LOGGER.debug("No cross-module conflicts detected")
    
    async def _check_sonos_conflicts(self) -> None:
        """Check for Sonos room mapping conflicts."""
        room_to_zones: Dict[str, List[str]] = {}
        
        for zone_id, zone in self._zones.items():
            room = zone.sonos.room_name
            if room:
                room_to_zones.setdefault(room, []).append(zone_id)
        
        for room, zones in room_to_zones.items():
            if len(zones) > 1:
                self._conflicts.append(Conflict(
                    conflict_id=f"sonos_room_{room}",
                    severity="warning",
                    modules=["sonos", "wecker", "mood"],
                    description=f"Sonos room '{room}' mapped to multiple zones: {zones}",
                    resolution="Assign unique Sonos rooms or explicitly share room across zones",
                    affected_entities=zones,
                ))
    
    async def _check_light_conflicts(self) -> None:
        """Check for light entity conflicts."""
        entity_to_zones: Dict[str, List[str]] = {}
        
        for zone_id, zone in self._zones.items():
            for entity in zone.light.entities:
                entity_to_zones.setdefault(entity, []).append(zone_id)
        
        for entity, zones in entity_to_zones.items():
            if len(zones) > 1:
                self._conflicts.append(Conflict(
                    conflict_id=f"light_entity_{entity}",
                    severity="info",
                    modules=["licht", "wecker", "mood"],
                    description=f"Light entity '{entity}' used in multiple zones: {zones}",
                    resolution="This may be intentional (shared lighting). Verify zone boundaries.",
                    affected_entities=[entity],
                ))
    
    async def _check_presence_conflicts(self) -> None:
        """Check for presence/motion entity conflicts."""
        entity_to_zones: Dict[str, List[str]] = {}
        
        for zone_id, zone in self._zones.items():
            for entity in zone.presence.motion_entities:
                entity_to_zones.setdefault(entity, []).append(zone_id)
        
        for entity, zones in entity_to_zones.items():
            if len(zones) > 1:
                self._conflicts.append(Conflict(
                    conflict_id=f"motion_entity_{entity}",
                    severity="warning",
                    modules=["praesenz", "habitus", "mood"],
                    description=f"Motion entity '{entity}' tracked in multiple zones: {zones}",
                    resolution="Motion sensors covering multiple zones should be intentional. Consider zone boundaries.",
                    affected_entities=[entity],
                ))
    
    async def _check_module_conflicts(self) -> None:
        """Check for module-specific conflicts."""
        for zone_id, zone in self._zones.items():
            # Wecker without Sonos
            if zone.alarm.enabled and not zone.sonos.room_name:
                self._conflicts.append(Conflict(
                    conflict_id=f"wecker_no_sonos_{zone_id}",
                    severity="warning",
                    modules=["wecker", "sonos"],
                    description=f"Alarm enabled for zone '{zone_id}' but no Sonos room configured",
                    resolution="Configure Sonos room or disable alarm for this zone",
                    affected_entities=[zone_id],
                ))
            
            # Mood without motion sensors
            if zone.mood.enabled and not zone.presence.motion_entities:
                self._conflicts.append(Conflict(
                    conflict_id=f"mood_no_motion_{zone_id}",
                    severity="warning",
                    modules=["mood", "praesenz"],
                    description=f"Mood inference enabled for zone '{zone_id}' but no motion sensors",
                    resolution="Add motion sensors or disable mood inference",
                    affected_entities=[zone_id],
                ))
    
    # ── Smart Defaults ────────────────────────────────────────────────
    
    def _apply_smart_defaults(self) -> None:
        """Apply smart defaults based on detected patterns."""
        for zone_id, zone in self._zones.items():
            if zone.defaults_applied:
                continue
            
            # Default: Enable mood if motion sensors exist
            if zone.presence.motion_entities and not zone.mood.enabled:
                zone.mood.enabled = True
                _LOGGER.debug("Applied smart default: enabled mood for %s", zone_id)
            
            # Default: Enable alarm if Sonos room exists
            if zone.sonos.room_name and not zone.alarm.enabled:
                zone.alarm.enabled = True
                _LOGGER.debug("Applied smart default: enabled alarm for %s", zone_id)
            
            # Default: Link light entities to alarm if not set
            if zone.alarm.enabled and zone.light.entities and not zone.alarm.enabled:
                # Already enabled above, but ensure light ramp is configured
                pass
            
            zone.defaults_applied = True
    
    # ── Auto-Discovery ────────────────────────────────────────────────
    
    async def _auto_discover_zones(self) -> None:
        """Auto-discover zones from Home Assistant registries."""
        area_reg = area_registry.async_get(self._hass)
        entity_reg = entity_registry.async_get(self._hass)
        
        # Get all areas as potential zones
        for area in area_reg.areas.values():
            zone_id = f"area_{area.id}"
            
            if zone_id not in self._zones:
                zone = ZoneConfig(
                    zone_id=zone_id,
                    zone_name=area.name,
                    area_id=area.id,
                    created_at=datetime.now(timezone.utc).isoformat(),
                    updated_at=datetime.now(timezone.utc).isoformat(),
                )
                self._zones[zone_id] = zone
            
            # Discover entities for this area
            await self._discover_zone_entities(zone, entity_reg)
    
    async def _discover_zone_entities(
        self, 
        zone: ZoneConfig, 
        entity_reg: entity_registry.EntityRegistry
    ) -> None:
        """Discover entities belonging to a zone."""
        entities = entity_registry.async_entries_for_area(entity_reg, zone.area_id)
        
        for entity in entities:
            domain = entity.entity_id.split(".")[0]
            
            # Sonos media players
            if domain == "media_player" and "sonos" in entity.entity_id.lower():
                if not zone.sonos.room_name:
                    zone.sonos.room_name = entity.original_name or entity.entity_id
                    _LOGGER.debug("Discovered Sonos room: %s", zone.sonos.room_name)
            
            # Lights
            elif domain == "light":
                if entity.entity_id not in zone.light.entities:
                    zone.light.entities.append(entity.entity_id)
            
            # Motion sensors
            elif domain == "binary_sensor" and "motion" in entity.entity_id.lower():
                if entity.entity_id not in zone.presence.motion_entities:
                    zone.presence.motion_entities.append(entity.entity_id)
            
            # Person entities
            elif domain == "person":
                if entity.entity_id not in zone.presence.person_entities:
                    zone.presence.person_entities.append(entity.entity_id)
            
            # Illuminance sensors
            elif domain == "sensor" and "illuminance" in entity.entity_id.lower():
                if not zone.presence.illuminance_entity:
                    zone.presence.illuminance_entity = entity.entity_id
            
            # Media players (for mood)
            elif domain == "media_player":
                if entity.entity_id not in zone.mood.media_entities:
                    zone.mood.media_entities.append(entity.entity_id)
    
    # ── Persistence ───────────────────────────────────────────────────
    
    async def _load_from_data(self, data: Dict[str, Any]) -> None:
        """Load configuration from persisted data."""
        zones_data = data.get("zones", [])
        
        for zone_data in zones_data:
            zone = self._zone_from_data(zone_data)
            if zone:
                self._zones[zone.zone_id] = zone
    
    def _zone_from_data(self, data: Dict[str, Any]) -> Optional[ZoneConfig]:
        """Create ZoneConfig from data dict."""
        try:
            zone_id = data.get("zone_id")
            if not zone_id:
                return None
            
            sonos_data = data.get("sonos", {})
            light_data = data.get("light", {})
            presence_data = data.get("presence", {})
            alarm_data = data.get("alarm", {})
            mood_data = data.get("mood", {})
            
            return ZoneConfig(
                zone_id=zone_id,
                zone_name=data.get("zone_name", ""),
                area_id=data.get("area_id", ""),
                sonos=SonosConfig(**sonos_data) if sonos_data else SonosConfig(),
                light=LightConfig(**light_data) if light_data else LightConfig(),
                presence=PresenceConfig(**presence_data) if presence_data else PresenceConfig(),
                alarm=AlarmConfig(**alarm_data) if alarm_data else AlarmConfig(),
                mood=MoodConfig(**mood_data) if mood_data else MoodConfig(),
                created_at=data.get("created_at", ""),
                updated_at=data.get("updated_at", ""),
                defaults_applied=data.get("defaults_applied", False),
            )
        except Exception as e:
            _LOGGER.warning("Failed to load zone from data: %s", e)
            return None
    
    def _to_data(self) -> Dict[str, Any]:
        """Convert configuration to persistable data."""
        zones_data = []
        
        for zone in self._zones.values():
            zone_data = {
                "zone_id": zone.zone_id,
                "zone_name": zone.zone_name,
                "area_id": zone.area_id,
                "sonos": {
                    "room_name": zone.sonos.room_name,
                    "favorite": zone.sonos.favorite,
                    "uri": zone.sonos.uri,
                    "volume_default": zone.sonos.volume_default,
                    "volume_ramp_start": zone.sonos.volume_ramp_start,
                    "volume_ramp_end": zone.sonos.volume_ramp_end,
                    "volume_ramp_minutes": zone.sonos.volume_ramp_minutes,
                    "follow_enabled": zone.sonos.follow_enabled,
                    "musikwolke_enabled": zone.sonos.musikwolke_enabled,
                },
                "light": {
                    "entities": zone.light.entities,
                    "brightness_default": zone.light.brightness_default,
                    "color_temp_kelvin": zone.light.color_temp_kelvin,
                    "ramp_minutes": zone.light.ramp_minutes,
                    "sunrise_enabled": zone.light.sunrise_enabled,
                    "sunset_enabled": zone.light.sunset_enabled,
                },
                "presence": {
                    "motion_entities": zone.presence.motion_entities,
                    "person_entities": zone.presence.person_entities,
                    "illuminance_entity": zone.presence.illuminance_entity,
                    "min_dwell_time_seconds": zone.presence.min_dwell_time_seconds,
                    "auto_away_delay_seconds": zone.presence.auto_away_delay_seconds,
                },
                "alarm": {
                    "enabled": zone.alarm.enabled,
                    "default_time_hhmm": zone.alarm.default_time_hhmm,
                    "repeat": zone.alarm.repeat,
                    "custom_days": zone.alarm.custom_days,
                    "snooze_minutes": zone.alarm.snooze_minutes,
                    "auto_dismiss_minutes": zone.alarm.auto_dismiss_minutes,
                },
                "mood": {
                    "enabled": zone.mood.enabled,
                    "media_entities": zone.mood.media_entities,
                    "min_dwell_time_seconds": zone.mood.min_dwell_time_seconds,
                    "action_cooldown_seconds": zone.mood.action_cooldown_seconds,
                    "polling_interval_seconds": zone.mood.polling_interval_seconds,
                    "character_weighting": zone.mood.character_weighting,
                },
                "created_at": zone.created_at,
                "updated_at": zone.updated_at,
                "defaults_applied": zone.defaults_applied,
            }
            zones_data.append(zone_data)
        
        return {
            "zones": zones_data,
            "updated": datetime.now(timezone.utc).isoformat(),
            "version": STORAGE_VERSION,
        }
    
    # ── Integration Helpers ───────────────────────────────────────────
    
    def get_sonos_room_for_zone(self, zone_id: str) -> Optional[str]:
        """Get Sonos room name for a zone (helper for sonos_module)."""
        zone = self._zones.get(zone_id)
        return zone.sonos.room_name if zone else None
    
    def get_light_entities_for_zone(self, zone_id: str) -> List[str]:
        """Get light entities for a zone (helper for licht_module/wecker)."""
        zone = self._zones.get(zone_id)
        return zone.light.entities if zone else []
    
    def get_motion_entities_for_zone(self, zone_id: str) -> List[str]:
        """Get motion entities for a zone (helper for praesenz/mood)."""
        zone = self._zones.get(zone_id)
        return zone.presence.motion_entities if zone else []
    
    def is_zone_occupied(self, zone_id: str) -> bool:
        """Check if zone has presence (helper for habitus/mood)."""
        zone = self._zones.get(zone_id)
        if not zone:
            return False
        # This would need runtime state - placeholder for integration
        return len(zone.presence.person_entities) > 0


# ── Module Integration ────────────────────────────────────────────────

async def async_get_cross_module_config(hass: HomeAssistant) -> CrossModuleConfig:
    """Get or create cross-module config instance."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    
    if "cross_module_config" not in hass.data[DOMAIN]:
        config = CrossModuleConfig(hass)
        await config.load()
        hass.data[DOMAIN]["cross_module_config"] = config
    else:
        config = hass.data[DOMAIN]["cross_module_config"]
    
    return config


# Domain constant (should match copilot_ha)
DOMAIN = "copilot_core"
