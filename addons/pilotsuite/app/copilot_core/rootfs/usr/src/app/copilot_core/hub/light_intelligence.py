"""Light Intelligence — Sun Position, Brightness, Threshold Control, Mood Scenes (v6.5.0).

Features:
- Sun position tracking (elevation, azimuth, phase)
- Outdoor/indoor brightness averaging per zone
- Normalized illumination ratio (indoor/outdoor)
- Threshold controller with cloud resilience (moving average filter)
- Mood scene presets with automatic suggestions
- Dimming curves for time-of-day transitions
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


# ── Data models ─────────────────────────────────────────────────────────────


@dataclass
class SunPosition:
    """Current sun position."""

    elevation: float = 0.0  # degrees above horizon (-90 to 90)
    azimuth: float = 0.0  # degrees from north (0-360)
    phase: str = "day"  # night, dawn, sunrise, day, sunset, dusk
    solar_noon: bool = False
    daylight_hours: float = 0.0


@dataclass
class BrightnessReading:
    """A brightness sensor reading."""

    entity_id: str
    value_lux: float
    zone_id: str = ""
    location: str = "indoor"  # indoor, outdoor
    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))


@dataclass
class ZoneBrightness:
    """Brightness summary for a zone."""

    zone_id: str
    zone_name: str = ""
    avg_indoor_lux: float = 0.0
    avg_outdoor_lux: float = 0.0
    illumination_ratio: float = 0.0  # 0-1, indoor/outdoor normalized
    illumination_pct: float = 0.0  # 0-100%
    threshold_met: bool = True
    min_brightness_lux: float = 0.0
    target_brightness_lux: float = 300.0
    needs_light: bool = False
    suggested_dimming_pct: int = 0  # 0-100, 0=off


@dataclass
class MoodScene:
    """A mood/lighting scene preset."""

    scene_id: str
    name: str
    name_de: str
    description_de: str
    brightness_pct: int  # 0-100
    color_temp_k: int  # Kelvin (2700=warm, 6500=daylight)
    applicable_phases: list[str] = field(default_factory=list)
    applicable_hours: tuple[int, int] = (0, 24)
    icon: str = "mdi:lightbulb"


@dataclass
class LightDashboard:
    """Complete light intelligence dashboard."""

    sun: SunPosition = field(default_factory=SunPosition)
    global_outdoor_lux: float = 0.0
    zones: list[dict[str, Any]] = field(default_factory=list)
    active_scene: str | None = None
    suggested_scene: str | None = None
    suggested_scene_name: str | None = None
    cloud_filter_active: bool = False
    scenes: list[dict[str, Any]] = field(default_factory=list)


# ── Predefined Mood Scenes ─────────────────────────────────────────────────

_MOOD_SCENES: list[MoodScene] = [
    MoodScene("energize", "Energize", "Energiegeladen",
              "Helles, kühles Licht für aktive Phasen",
              brightness_pct=100, color_temp_k=5000,
              applicable_phases=["day", "sunrise"], applicable_hours=(6, 12),
              icon="mdi:white-balance-sunny"),
    MoodScene("focus", "Focus", "Konzentration",
              "Neutrales Licht zum Arbeiten",
              brightness_pct=90, color_temp_k=4500,
              applicable_phases=["day"], applicable_hours=(8, 18),
              icon="mdi:head-lightbulb"),
    MoodScene("relax", "Relax", "Entspannung",
              "Warmes, gedimmtes Licht zum Entspannen",
              brightness_pct=50, color_temp_k=2700,
              applicable_phases=["sunset", "dusk", "night"], applicable_hours=(18, 23),
              icon="mdi:sofa"),
    MoodScene("cozy", "Cozy Evening", "Gemütlicher Abend",
              "Warmes Licht für gemütliche Abendstunden",
              brightness_pct=40, color_temp_k=2500,
              applicable_phases=["dusk", "night"], applicable_hours=(19, 23),
              icon="mdi:candle"),
    MoodScene("night_light", "Night Light", "Nachtlicht",
              "Minimales Licht für nächtliche Orientierung",
              brightness_pct=5, color_temp_k=2200,
              applicable_phases=["night"], applicable_hours=(22, 6),
              icon="mdi:weather-night"),
    MoodScene("morning", "Morning Glow", "Morgenstimmung",
              "Sanft ansteigendes Licht am Morgen",
              brightness_pct=60, color_temp_k=3500,
              applicable_phases=["dawn", "sunrise"], applicable_hours=(5, 9),
              icon="mdi:weather-sunset-up"),
    MoodScene("dim", "Dimmed", "Gedimmt",
              "Leicht gedimmtes Licht bei ausreichend Tageslicht",
              brightness_pct=30, color_temp_k=3000,
              applicable_phases=["day", "sunset"], applicable_hours=(12, 20),
              icon="mdi:brightness-4"),
    MoodScene("off", "Lights Off", "Aus",
              "Kein künstliches Licht (genug Tageslicht)",
              brightness_pct=0, color_temp_k=0,
              applicable_phases=["day"], applicable_hours=(8, 18),
              icon="mdi:lightbulb-off"),
]


# ── Cloud resilience filter parameters ──────────────────────────────────────

_CLOUD_FILTER_WINDOW = 10  # moving average over N readings
_CLOUD_HYSTERESIS_PCT = 15  # % change needed before switching
_MIN_OUTDOOR_LUX_DAY = 100  # below this it's considered dark regardless


# ── Engine ──────────────────────────────────────────────────────────────────


class LightIntelligenceEngine:
    """Light intelligence engine with sun tracking, brightness control, and mood scenes."""

    def __init__(self, latitude: float = 50.0, longitude: float = 10.0) -> None:
        self._latitude = latitude
        self._longitude = longitude
        self._sun = SunPosition()

        # Brightness tracking
        self._outdoor_sensors: dict[str, deque] = defaultdict(lambda: deque(maxlen=_CLOUD_FILTER_WINDOW))
        self._indoor_sensors: dict[str, deque] = defaultdict(lambda: deque(maxlen=_CLOUD_FILTER_WINDOW))
        self._sensor_zones: dict[str, str] = {}  # entity_id -> zone_id
        self._sensor_locations: dict[str, str] = {}  # entity_id -> indoor/outdoor

        # Zone configuration
        self._zone_targets: dict[str, float] = {}  # zone_id -> target_lux
        self._zone_mins: dict[str, float] = {}  # zone_id -> min_lux
        self._zone_names: dict[str, str] = {}

        # Scene management
        self._active_scene: str | None = None
        self._zone_scenes: dict[str, str] = {}  # zone_id -> scene_id

        # Cloud filter state
        self._last_outdoor_avg: float = 0.0
        self._light_state_stable: bool = True

    # ── Sun position ────────────────────────────────────────────────────

    def update_sun(self, elevation: float, azimuth: float) -> SunPosition:
        """Update sun position from HA sun entity."""
        self._sun.elevation = elevation
        self._sun.azimuth = azimuth
        self._sun.phase = self._classify_phase(elevation)
        self._sun.solar_noon = 170 <= azimuth <= 190 and elevation > 0
        return self._sun

    def get_sun(self) -> SunPosition:
        """Get current sun position."""
        return self._sun

    @staticmethod
    def _classify_phase(elevation: float) -> str:
        """Classify sun phase from elevation angle."""
        if elevation > 6:
            return "day"
        elif elevation > 0:
            return "sunrise"  # or sunset depending on time
        elif elevation > -6:
            return "dawn"  # civil twilight (or dusk)
        elif elevation > -12:
            return "dusk"  # nautical twilight
        else:
            return "night"

    # ── Brightness tracking ─────────────────────────────────────────────

    def register_sensor(self, entity_id: str, zone_id: str = "",
                        location: str = "indoor") -> None:
        """Register a brightness sensor."""
        self._sensor_zones[entity_id] = zone_id
        self._sensor_locations[entity_id] = location

    def configure_zone(self, zone_id: str, name: str = "",
                       target_lux: float = 300.0,
                       min_lux: float = 100.0) -> None:
        """Configure zone brightness thresholds."""
        self._zone_targets[zone_id] = target_lux
        self._zone_mins[zone_id] = min_lux
        if name:
            self._zone_names[zone_id] = name

    def update_brightness(self, entity_id: str, lux: float) -> None:
        """Update brightness reading from a sensor."""
        location = self._sensor_locations.get(entity_id, "indoor")
        if location == "outdoor":
            self._outdoor_sensors[entity_id].append(lux)
        else:
            self._indoor_sensors[entity_id].append(lux)

    def update_brightness_batch(self, readings: list[dict[str, Any]]) -> int:
        """Batch update brightness readings.

        Each dict: {"entity_id": str, "lux": float}
        """
        count = 0
        for r in readings:
            eid = r.get("entity_id", "")
            lux = r.get("lux")
            if eid and lux is not None:
                self.update_brightness(eid, float(lux))
                count += 1
        return count

    # ── Brightness calculations ─────────────────────────────────────────

    def get_outdoor_brightness(self) -> float:
        """Get filtered outdoor brightness (cloud-resilient moving average)."""
        all_values = []
        for sensor_buffer in self._outdoor_sensors.values():
            if sensor_buffer:
                all_values.extend(sensor_buffer)

        if not all_values:
            return 0.0

        avg = sum(all_values) / len(all_values)

        # Cloud resilience: if change from last stable value < hysteresis, keep stable
        if self._last_outdoor_avg > 0:
            change_pct = abs(avg - self._last_outdoor_avg) / self._last_outdoor_avg * 100
            if change_pct < _CLOUD_HYSTERESIS_PCT:
                self._light_state_stable = True
                return self._last_outdoor_avg
            else:
                self._light_state_stable = False

        self._last_outdoor_avg = avg
        return avg

    def get_zone_brightness(self, zone_id: str) -> ZoneBrightness:
        """Get brightness analysis for a zone."""
        target = self._zone_targets.get(zone_id, 300.0)
        min_lux = self._zone_mins.get(zone_id, 100.0)
        name = self._zone_names.get(zone_id, zone_id)

        # Collect indoor readings for this zone
        indoor_values = []
        for eid, zone in self._sensor_zones.items():
            if zone == zone_id and self._sensor_locations.get(eid) == "indoor":
                buf = self._indoor_sensors.get(eid)
                if buf:
                    indoor_values.append(sum(buf) / len(buf))

        avg_indoor = sum(indoor_values) / len(indoor_values) if indoor_values else 0.0
        avg_outdoor = self.get_outdoor_brightness()

        # Normalized illumination ratio
        illumination_ratio = 0.0
        if avg_outdoor > 0:
            illumination_ratio = min(1.0, avg_indoor / max(avg_outdoor, 1.0))

        illumination_pct = illumination_ratio * 100

        # Does the zone need light?
        needs_light = avg_indoor < min_lux
        threshold_met = avg_indoor >= min_lux

        # Suggested dimming: how much artificial light is needed
        if needs_light and target > 0:
            deficit = target - avg_indoor
            suggested_dimming = min(100, max(0, int(deficit / target * 100)))
        else:
            suggested_dimming = 0

        return ZoneBrightness(
            zone_id=zone_id,
            zone_name=name,
            avg_indoor_lux=round(avg_indoor, 1),
            avg_outdoor_lux=round(avg_outdoor, 1),
            illumination_ratio=round(illumination_ratio, 3),
            illumination_pct=round(illumination_pct, 1),
            threshold_met=threshold_met,
            min_brightness_lux=min_lux,
            target_brightness_lux=target,
            needs_light=needs_light,
            suggested_dimming_pct=suggested_dimming,
        )

    # ── Scene suggestions ───────────────────────────────────────────────

    def suggest_scene(self, hour: int | None = None) -> MoodScene | None:
        """Suggest a mood scene based on current conditions."""
        if hour is None:
            hour = datetime.now(tz=timezone.utc).hour

        phase = self._sun.phase
        outdoor = self.get_outdoor_brightness()

        best_scene = None
        best_score = -1

        for scene in _MOOD_SCENES:
            score = 0

            # Phase match
            if phase in scene.applicable_phases:
                score += 3

            # Hour match
            start_h, end_h = scene.applicable_hours
            if start_h <= end_h:
                if start_h <= hour < end_h:
                    score += 2
            else:  # wraps around midnight
                if hour >= start_h or hour < end_h:
                    score += 2

            # Special: if very bright outside and it's daytime, suggest "off"
            if outdoor > 10000 and phase == "day" and scene.scene_id == "off":
                score += 5
            # If dark outside and nighttime, suggest cozy/night_light
            elif outdoor < _MIN_OUTDOOR_LUX_DAY and phase == "night":
                if scene.scene_id in ("cozy", "night_light"):
                    score += 4
            # Evening dim
            elif outdoor < 1000 and phase in ("sunset", "dusk"):
                if scene.scene_id in ("relax", "cozy"):
                    score += 4

            if score > best_score:
                best_score = score
                best_scene = scene

        return best_scene

    def get_scenes(self) -> list[dict[str, Any]]:
        """Get all available mood scenes."""
        return [
            {
                "scene_id": s.scene_id,
                "name": s.name,
                "name_de": s.name_de,
                "description_de": s.description_de,
                "brightness_pct": s.brightness_pct,
                "color_temp_k": s.color_temp_k,
                "icon": s.icon,
            }
            for s in _MOOD_SCENES
        ]

    def set_active_scene(self, scene_id: str, zone_id: str | None = None) -> bool:
        """Set active scene (globally or per zone)."""
        valid_ids = {s.scene_id for s in _MOOD_SCENES}
        if scene_id not in valid_ids:
            return False
        if zone_id:
            self._zone_scenes[zone_id] = scene_id
        else:
            self._active_scene = scene_id
        return True

    # ── Dashboard ───────────────────────────────────────────────────────

    def get_dashboard(self) -> LightDashboard:
        """Get complete light intelligence dashboard."""
        outdoor = self.get_outdoor_brightness()
        zones = []

        # Collect all configured zones
        all_zones = set(self._zone_targets.keys()) | set(self._sensor_zones.values())
        all_zones.discard("")

        for zid in sorted(all_zones):
            zb = self.get_zone_brightness(zid)
            zones.append({
                "zone_id": zb.zone_id,
                "zone_name": zb.zone_name,
                "avg_indoor_lux": zb.avg_indoor_lux,
                "avg_outdoor_lux": zb.avg_outdoor_lux,
                "illumination_pct": zb.illumination_pct,
                "threshold_met": zb.threshold_met,
                "needs_light": zb.needs_light,
                "suggested_dimming_pct": zb.suggested_dimming_pct,
                "active_scene": self._zone_scenes.get(zid, self._active_scene),
            })

        suggested = self.suggest_scene()

        return LightDashboard(
            sun=self._sun,
            global_outdoor_lux=round(outdoor, 1),
            zones=zones,
            active_scene=self._active_scene,
            suggested_scene=suggested.scene_id if suggested else None,
            suggested_scene_name=suggested.name_de if suggested else None,
            cloud_filter_active=not self._light_state_stable,
            scenes=self.get_scenes(),
        )
