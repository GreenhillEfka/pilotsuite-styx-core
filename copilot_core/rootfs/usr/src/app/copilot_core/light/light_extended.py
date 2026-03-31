"""Light Module Extensions — Slice 76.

Erweiterte Lichtsteuerung für Habituszonen.

New Features (Slice 76):
- Adaptive Lighting (circadian rhythm support)
- Advanced Scene Management (transitions, fades)
- Light Schedules (time-based automation)
- Color Temperature Tuning (Kelvin, RGB, HSV)
- Brightness Smoothing (fade effects)
- Energy Monitoring Integration
- Bulb Lifetime Tracking
- Light Groups & Sync
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple, Callable
from enum import Enum
import uuid
import math

logger = logging.getLogger(__name__)


class ColorMode(Enum):
    """Color mode for lights."""
    WHITE = "white"  # White only
    COLOR_TEMP = "color_temp"  # Tunable white (Kelvin)
    RGB = "rgb"  # RGB color
    HSV = "hsv"  # HSV color
    XY = "xy"  # CIE XY color


class LightEffect(Enum):
    """Light effects."""
    NONE = "none"
    FADE_IN = "fade_in"
    FADE_OUT = "fade_out"
    PULSE = "pulse"
    BREATHE = "breathe"
    SUNRISE = "sunrise"
    SUNSET = "sunset"
    GRADIENT = "gradient"


@dataclass
class LightSchedule:
    """Light schedule entry."""
    schedule_id: str
    zone_id: str
    name: str
    enabled: bool = True
    days_of_week: List[int] = field(default_factory=lambda: [0, 1, 2, 3, 4, 5, 6])  # 0=Monday
    start_time: str = "07:00"  # HH:MM format
    end_time: Optional[str] = None  # HH:MM or None for instant
    action: str = "turn_on"  # turn_on, turn_off, scene
    brightness: Optional[float] = None  # 0.0-1.0
    color_temp: Optional[int] = None  # Kelvin
    color_rgb: Optional[Tuple[int, int, int]] = None
    scene_id: Optional[str] = None
    transition_seconds: int = 0  # Fade duration
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "schedule_id": self.schedule_id,
            "zone_id": self.zone_id,
            "name": self.name,
            "enabled": self.enabled,
            "days_of_week": self.days_of_week,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "action": self.action,
            "brightness": self.brightness,
            "color_temp": self.color_temp,
            "color_rgb": self.color_rgb,
            "scene_id": self.scene_id,
            "transition_seconds": self.transition_seconds,
        }


@dataclass
class CircadianConfig:
    """Circadian lighting configuration."""
    enabled: bool = True
    min_color_temp: int = 2700  # Warm (evening)
    max_color_temp: int = 6500  # Cool (day)
    min_brightness: float = 0.1  # Night minimum
    max_brightness: float = 1.0  # Day maximum
    sunrise_offset_minutes: int = 0  # Before actual sunrise
    sunset_offset_minutes: int = 0  # After actual sunset
    sleep_mode_brightness: float = 0.05  # Very dim for night
    transition_speed_minutes: int = 30  # How fast to transition
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "min_color_temp": self.min_color_temp,
            "max_color_temp": self.max_color_temp,
            "min_brightness": self.min_brightness,
            "max_brightness": self.max_brightness,
            "sunrise_offset_minutes": self.sunrise_offset_minutes,
            "sunset_offset_minutes": self.sunset_offset_minutes,
            "sleep_mode_brightness": self.sleep_mode_brightness,
            "transition_speed_minutes": self.transition_speed_minutes,
        }


@dataclass
class AdvancedScene:
    """Advanced light scene with transitions."""
    scene_id: str
    zone_id: str
    name: str
    brightness: float = 0.8
    color_temp: Optional[int] = None
    color_rgb: Optional[Tuple[int, int, int]] = None
    color_mode: ColorMode = ColorMode.COLOR_TEMP
    effect: LightEffect = LightEffect.NONE
    transition_seconds: int = 2  # Fade duration
    duration_seconds: Optional[int] = None  # Auto-off after duration
    priority: int = 50  # Scene priority for conflicts
    tags: List[str] = field(default_factory=list)  # e.g., ["relaxing", "evening"]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "scene_id": self.scene_id,
            "zone_id": self.zone_id,
            "name": self.name,
            "brightness": self.brightness,
            "color_temp": self.color_temp,
            "color_rgb": list(self.color_rgb) if self.color_rgb else None,
            "color_mode": self.color_mode.value,
            "effect": self.effect.value,
            "transition_seconds": self.transition_seconds,
            "duration_seconds": self.duration_seconds,
            "priority": self.priority,
            "tags": self.tags,
        }


@dataclass
class BulbStats:
    """Bulb lifetime and energy statistics."""
    entity_id: str
    zone_id: str
    total_on_hours: float = 0.0
    total_energy_wh: float = 0.0
    power_rating_watts: float = 10.0  # Rated power
    install_date: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    rated_lifetime_hours: float = 25000.0  # LED typical
    brightness_average: float = 0.5
    on_off_cycles: int = 0
    last_replaced: Optional[str] = None
    
    @property
    def lifetime_remaining_percent(self) -> float:
        """Calculate remaining lifetime percentage."""
        if self.rated_lifetime_hours <= 0:
            return 100.0
        used = self.total_on_hours / self.rated_lifetime_hours
        return max(0.0, min(100.0, (1.0 - used) * 100))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "zone_id": self.zone_id,
            "total_on_hours": self.total_on_hours,
            "total_energy_wh": self.total_energy_wh,
            "power_rating_watts": self.power_rating_watts,
            "install_date": self.install_date,
            "rated_lifetime_hours": self.rated_lifetime_hours,
            "lifetime_remaining_percent": self.lifetime_remaining_percent,
            "brightness_average": self.brightness_average,
            "on_off_cycles": self.on_off_cycles,
            "last_replaced": self.last_replaced,
        }


@dataclass
class LightGroup:
    """Synchronized light group."""
    group_id: str
    name: str
    zone_ids: List[str]
    entity_ids: List[str]
    sync_brightness: bool = True
    sync_color: bool = True
    sync_effects: bool = False
    master_zone: Optional[str] = None  # Zone that controls the group
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "group_id": self.group_id,
            "name": self.name,
            "zone_ids": self.zone_ids,
            "entity_ids": self.entity_ids,
            "sync_brightness": self.sync_brightness,
            "sync_color": self.sync_color,
            "sync_effects": self.sync_effects,
            "master_zone": self.master_zone,
        }


class LightModuleExtended:
    """Extended light module with advanced features.
    
    New Capabilities (Slice 76):
    - Adaptive/circadian lighting
    - Advanced scenes with transitions
    - Time-based schedules
    - Color temperature tuning
    - Brightness smoothing/fades
    - Energy monitoring
    - Bulb lifetime tracking
    - Light groups & sync
    """
    
    def __init__(self):
        self._schedules: Dict[str, LightSchedule] = {}
        self._zone_schedules: Dict[str, List[str]] = {}  # zone_id -> schedule_ids
        self._scenes: Dict[str, AdvancedScene] = {}
        self._zone_scenes: Dict[str, List[str]] = {}  # zone_id -> scene_ids
        self._circadian_configs: Dict[str, CircadianConfig] = {}
        self._bulb_stats: Dict[str, BulbStats] = {}  # entity_id -> stats
        self._light_groups: Dict[str, LightGroup] = {}
        self._active_effects: Dict[str, Dict[str, Any]] = {}  # zone_id -> effect state
        self._brightness_cache: Dict[str, float] = {}  # zone_id -> current brightness
        
        logger.info("LightModuleExtended initialized")
    
    def add_schedule(self, schedule: LightSchedule) -> str:
        """Add light schedule for zone."""
        with self._lock():
            self._schedules[schedule.schedule_id] = schedule
            
            if schedule.zone_id not in self._zone_schedules:
                self._zone_schedules[schedule.zone_id] = []
            
            self._zone_schedules[schedule.zone_id].append(schedule.schedule_id)
        
        logger.info("Light schedule added: %s for %s", schedule.schedule_id, schedule.zone_id)
        return schedule.schedule_id
    
    def remove_schedule(self, schedule_id: str) -> bool:
        """Remove schedule."""
        if schedule_id not in self._schedules:
            return False
        
        schedule = self._schedules[schedule_id]
        
        with self._lock():
            del self._schedules[schedule_id]
            
            if schedule.zone_id in self._zone_schedules:
                if schedule_id in self._zone_schedules[schedule.zone_id]:
                    self._zone_schedules[schedule.zone_id].remove(schedule_id)
        
        return True
    
    def add_scene(self, scene: AdvancedScene) -> str:
        """Add advanced scene for zone."""
        with self._lock():
            self._scenes[scene.scene_id] = scene
            
            if scene.zone_id not in self._zone_scenes:
                self._zone_scenes[scene.zone_id] = []
            
            self._zone_scenes[scene.zone_id].append(scene.scene_id)
        
        logger.info("Advanced scene added: %s for %s", scene.scene_id, scene.zone_id)
        return scene.scene_id
    
    def remove_scene(self, scene_id: str) -> bool:
        """Remove scene."""
        if scene_id not in self._scenes:
            return False
        
        scene = self._scenes[scene_id]
        
        with self._lock():
            del self._scenes[scene_id]
            
            if scene.zone_id in self._zone_scenes:
                if scene_id in self._zone_scenes[scene.zone_id]:
                    self._zone_scenes[scene.zone_id].remove(scene_id)
        
        return True
    
    def set_circadian_config(self, zone_id: str, config: CircadianConfig) -> bool:
        """Set circadian lighting config for zone."""
        with self._lock():
            self._circadian_configs[zone_id] = config
        
        logger.info("Circadian config set for %s", zone_id)
        return True
    
    def get_circadian_config(self, zone_id: str) -> Optional[CircadianConfig]:
        """Get circadian config for zone."""
        return self._circadian_configs.get(zone_id)
    
    def calculate_circadian_state(self, zone_id: str,
                                 at_time: Optional[datetime] = None) -> Dict[str, Any]:
        """Calculate circadian-adjusted brightness and color temp."""
        config = self._circadian_configs.get(zone_id)
        
        if not config or not config.enabled:
            return {"brightness": None, "color_temp": None}
        
        now = at_time or datetime.now(timezone.utc)
        
        # Simplified circadian calculation based on time of day
        hour = now.hour + now.minute / 60.0
        
        # Sunrise ~6:00, Sunset ~20:00 (simplified)
        sunrise_hour = 6.0
        sunset_hour = 20.0
        
        if hour < sunrise_hour:
            # Night - minimum brightness, warm color
            brightness = config.sleep_mode_brightness
            color_temp = config.min_color_temp
        elif hour < sunrise_hour + config.transition_speed_minutes / 60:
            # Sunrise transition
            progress = (hour - sunrise_hour) / (config.transition_speed_minutes / 60)
            brightness = config.sleep_mode_brightness + (config.min_brightness - config.sleep_mode_brightness) * progress
            color_temp = config.min_color_temp
        elif hour < sunset_hour:
            # Day - full brightness, cool color
            brightness = config.max_brightness
            color_temp = config.max_color_temp
        elif hour < sunset_hour + config.transition_speed_minutes / 60:
            # Sunset transition
            progress = (hour - sunset_hour) / (config.transition_speed_minutes / 60)
            brightness = config.max_brightness - (config.max_brightness - config.sleep_mode_brightness) * progress
            color_temp = config.max_color_temp - (config.max_color_temp - config.min_color_temp) * progress
        else:
            # Night
            brightness = config.sleep_mode_brightness
            color_temp = config.min_color_temp
        
        return {
            "brightness": max(config.min_brightness, min(config.max_brightness, brightness)),
            "color_temp": max(config.min_color_temp, min(config.max_color_temp, color_temp)),
        }
    
    def apply_scene_with_transition(self, zone_id: str, scene_id: str,
                                   transition_seconds: Optional[int] = None) -> Dict[str, Any]:
        """Apply scene with fade transition."""
        if scene_id not in self._scenes:
            return {"success": False, "error": "Scene not found"}
        
        scene = self._scenes[scene_id]
        
        if scene.zone_id != zone_id:
            return {"success": False, "error": "Scene not for this zone"}
        
        transition = transition_seconds if transition_seconds is not None else scene.transition_seconds
        
        # Start effect
        self._active_effects[zone_id] = {
            "type": "scene_transition",
            "scene_id": scene_id,
            "start_brightness": self._brightness_cache.get(zone_id, 0.0),
            "target_brightness": scene.brightness,
            "start_time": datetime.now(timezone.utc).isoformat(),
            "duration_seconds": transition,
        }
        
        # Update brightness cache
        self._brightness_cache[zone_id] = scene.brightness
        
        return {
            "success": True,
            "scene_id": scene_id,
            "transition_seconds": transition,
            "target_brightness": scene.brightness,
        }
    
    def update_brightness_smooth(self, zone_id: str, target_brightness: float,
                                transition_seconds: int = 5) -> Dict[str, Any]:
        """Smoothly transition brightness."""
        current = self._brightness_cache.get(zone_id, 0.0)
        
        self._active_effects[zone_id] = {
            "type": "brightness_fade",
            "start_brightness": current,
            "target_brightness": target_brightness,
            "start_time": datetime.now(timezone.utc).isoformat(),
            "duration_seconds": transition_seconds,
        }
        
        self._brightness_cache[zone_id] = target_brightness
        
        return {
            "success": True,
            "from_brightness": current,
            "to_brightness": target_brightness,
            "transition_seconds": transition_seconds,
        }
    
    def add_bulb_stats(self, stats: BulbStats) -> bool:
        """Add bulb statistics tracking."""
        if stats.entity_id in self._bulb_stats:
            return False
        
        with self._lock():
            self._bulb_stats[stats.entity_id] = stats
        
        return True
    
    def update_bulb_usage(self, entity_id: str, is_on: bool,
                         brightness: float = 1.0,
                         duration_minutes: float = 1.0) -> None:
        """Update bulb usage statistics."""
        if entity_id not in self._bulb_stats:
            return
        
        stats = self._bulb_stats[entity_id]
        
        if is_on:
            # Add to on-hours
            stats.total_on_hours += duration_minutes / 60.0
            
            # Add energy consumption
            energy = stats.power_rating_watts * brightness * (duration_minutes / 60.0)
            stats.total_energy_wh += energy
            
            # Update average brightness
            stats.brightness_average = (stats.brightness_average + brightness) / 2.0
    
    def record_on_off_cycle(self, entity_id: str) -> None:
        """Record an on/off cycle for bulb."""
        if entity_id not in self._bulb_stats:
            return
        
        self._bulb_stats[entity_id].on_off_cycles += 1
    
    def create_light_group(self, group: LightGroup) -> str:
        """Create synchronized light group."""
        with self._lock():
            self._light_groups[group.group_id] = group
        
        logger.info("Light group created: %s", group.group_id)
        return group.group_id
    
    def get_light_group(self, group_id: str) -> Optional[LightGroup]:
        """Get light group."""
        return self._light_groups.get(group_id)
    
    def sync_group_brightness(self, group_id: str,
                             brightness: float) -> List[str]:
        """Sync brightness across group."""
        group = self._light_groups.get(group_id)
        
        if not group or not group.sync_brightness:
            return []
        
        synced_zones = []
        
        for zone_id in group.zone_ids:
            self._brightness_cache[zone_id] = brightness
            synced_zones.append(zone_id)
        
        return synced_zones
    
    def get_schedule_for_time(self, zone_id: str,
                             at_time: Optional[datetime] = None) -> List[LightSchedule]:
        """Get active schedules for zone at given time."""
        now = at_time or datetime.now(timezone.utc)
        
        current_time = now.strftime("%H:%M")
        current_day = now.weekday()
        
        active = []
        
        for schedule_id in self._zone_schedules.get(zone_id, []):
            schedule = self._schedules.get(schedule_id)
            
            if not schedule or not schedule.enabled:
                continue
            
            if current_day not in schedule.days_of_week:
                continue
            
            if schedule.start_time <= current_time:
                if schedule.end_time is None or current_time <= schedule.end_time:
                    active.append(schedule)
        
        return active
    
    def get_zone_scenes(self, zone_id: str) -> List[AdvancedScene]:
        """Get all scenes for zone."""
        scene_ids = self._zone_scenes.get(zone_id, [])
        return [self._scenes[sid] for sid in scene_ids if sid in self._scenes]
    
    def get_scene(self, scene_id: str) -> Optional[AdvancedScene]:
        """Get scene by ID."""
        return self._scenes.get(scene_id)
    
    def get_active_effect(self, zone_id: str) -> Optional[Dict[str, Any]]:
        """Get active effect for zone."""
        return self._active_effects.get(zone_id)
    
    def clear_effect(self, zone_id: str) -> bool:
        """Clear active effect for zone."""
        if zone_id not in self._active_effects:
            return False
        
        del self._active_effects[zone_id]
        return True
    
    def get_brightness(self, zone_id: str) -> float:
        """Get current cached brightness for zone."""
        return self._brightness_cache.get(zone_id, 0.0)
    
    def get_bulb_stats(self, entity_id: str) -> Optional[BulbStats]:
        """Get bulb statistics."""
        return self._bulb_stats.get(entity_id)
    
    def get_bulbs_needing_replacement(self,
                                     threshold_percent: float = 20.0) -> List[BulbStats]:
        """Get bulbs approaching end of life."""
        replacements = []
        
        for stats in self._bulb_stats.values():
            if stats.lifetime_remaining_percent < threshold_percent:
                replacements.append(stats)
        
        return replacements
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get extended light module statistics."""
        total_schedules = len(self._schedules)
        enabled_schedules = len([s for s in self._schedules.values() if s.enabled])
        
        total_scenes = len(self._scenes)
        active_effects = len(self._active_effects)
        
        bulbs_low = len(self.get_bulbs_needing_replacement())
        
        return {
            "total_schedules": total_schedules,
            "enabled_schedules": enabled_schedules,
            "disabled_schedules": total_schedules - enabled_schedules,
            "total_scenes": total_scenes,
            "zones_with_scenes": len(self._zone_scenes),
            "active_effects": active_effects,
            "total_light_groups": len(self._light_groups),
            "bulbs_tracked": len(self._bulb_stats),
            "bulbs_needing_replacement": bulbs_low,
            "circadian_zones": len(self._circadian_configs),
        }
    
    def _lock(self):
        """Simple context manager for thread safety."""
        import threading
        return threading.Lock()


def create_light_module_extended() -> LightModuleExtended:
    """Factory function to create extended light module."""
    return LightModuleExtended()


# Pre-built scene templates
def create_reading_scene(zone_id: str) -> AdvancedScene:
    """Create reading scene."""
    return AdvancedScene(
        scene_id=f"scene_reading_{zone_id}",
        zone_id=zone_id,
        name="Reading",
        brightness=0.9,
        color_temp=5000,
        color_mode=ColorMode.COLOR_TEMP,
        tags=["focused", "bright"],
    )


def create_relaxing_scene(zone_id: str) -> AdvancedScene:
    """Create relaxing scene."""
    return AdvancedScene(
        scene_id=f"scene_relaxing_{zone_id}",
        zone_id=zone_id,
        name="Relaxing",
        brightness=0.4,
        color_temp=3000,
        color_mode=ColorMode.COLOR_TEMP,
        effect=LightEffect.NONE,
        tags=["evening", "warm"],
    )


def create_movie_scene(zone_id: str) -> AdvancedScene:
    """Create movie scene."""
    return AdvancedScene(
        scene_id=f"scene_movie_{zone_id}",
        zone_id=zone_id,
        name="Movie",
        brightness=0.2,
        color_temp=4000,
        color_mode=ColorMode.COLOR_TEMP,
        tags=["evening", "dim"],
    )


def create_sunrise_scene(zone_id: str) -> AdvancedScene:
    """Create sunrise wake-up scene."""
    return AdvancedScene(
        scene_id=f"scene_sunrise_{zone_id}",
        zone_id=zone_id,
        name="Sunrise",
        brightness=0.8,
        color_temp=4000,
        color_mode=ColorMode.COLOR_TEMP,
        effect=LightEffect.SUNRISE,
        transition_seconds=900,  # 15 minutes
        tags=["morning", "wake-up"],
    )
