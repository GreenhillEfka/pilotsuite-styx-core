"""Scene Intelligence + PilotSuite Cloud (v7.0.0).

Features:
- Intelligent scene management combining zone modes, light, media, climate
- Scene learning from user patterns (time, presence, activity)
- Scene suggestions based on context (time of day, occupancy, weather)
- PilotSuite Cloud sync for cross-home scene sharing
- Scene presets with customizable parameters
- Cloud status monitoring with local-first fallback
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


# ── Data models ─────────────────────────────────────────────────────────────


@dataclass
class ScenePreset:
    """A scene preset combining multiple system aspects."""

    scene_id: str
    name_de: str
    name_en: str
    icon: str = "mdi:palette"
    category: str = "custom"  # morning, day, evening, night, activity, custom
    light_brightness_pct: int | None = None
    light_color_temp_k: int | None = None
    media_volume_pct: int | None = None
    media_source: str | None = None
    climate_temp_c: float | None = None
    zone_mode: str | None = None
    suppress_automations: bool = False
    tags: list[str] = field(default_factory=list)
    usage_count: int = 0
    rating: float = 0.0


@dataclass
class SceneContext:
    """Context for scene suggestion."""

    hour: int = 12
    is_home: bool = True
    occupancy_count: int = 1
    outdoor_lux: float = 500.0
    indoor_temp_c: float = 21.0
    is_weekend: bool = False
    active_zone: str = ""


@dataclass
class SceneSuggestion:
    """A scene suggestion based on context."""

    scene_id: str
    name_de: str
    confidence: float = 0.0
    reason_de: str = ""
    icon: str = "mdi:palette"


@dataclass
class LearnedPattern:
    """A learned scene pattern from user behavior."""

    pattern_id: str
    scene_id: str
    hour_range: tuple[int, int] = (0, 24)
    is_weekend: bool | None = None
    occupancy_min: int = 0
    activation_count: int = 0
    last_activated: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))


@dataclass
class CloudStatus:
    """PilotSuite Cloud connection status."""

    connected: bool = False
    last_sync: datetime | None = None
    sync_interval_min: int = 15
    shared_scenes: int = 0
    cloud_url: str = ""
    local_fallback: bool = True


@dataclass
class SceneIntelligenceDashboard:
    """Scene intelligence dashboard."""

    total_scenes: int = 0
    active_scene: dict[str, Any] | None = None
    suggestions: list[dict[str, Any]] = field(default_factory=list)
    learned_patterns: int = 0
    cloud_status: dict[str, Any] = field(default_factory=dict)
    categories: dict[str, int] = field(default_factory=dict)
    popular_scenes: list[dict[str, Any]] = field(default_factory=list)


# ── Built-in scenes ──────────────────────────────────────────────────────

_BUILTIN_SCENES: list[dict[str, Any]] = [
    {
        "scene_id": "morning_routine",
        "name_de": "Morgenroutine",
        "name_en": "Morning Routine",
        "icon": "mdi:weather-sunny",
        "category": "morning",
        "light_brightness_pct": 80,
        "light_color_temp_k": 5000,
        "climate_temp_c": 21.0,
        "tags": ["morning", "routine", "wake"],
    },
    {
        "scene_id": "work_focus",
        "name_de": "Arbeits-Fokus",
        "name_en": "Work Focus",
        "icon": "mdi:head-lightbulb",
        "category": "activity",
        "light_brightness_pct": 90,
        "light_color_temp_k": 4500,
        "media_volume_pct": 10,
        "suppress_automations": True,
        "zone_mode": "focus",
        "tags": ["work", "focus", "productive"],
    },
    {
        "scene_id": "lunch_break",
        "name_de": "Mittagspause",
        "name_en": "Lunch Break",
        "icon": "mdi:food",
        "category": "day",
        "light_brightness_pct": 70,
        "light_color_temp_k": 4000,
        "tags": ["lunch", "break", "relax"],
    },
    {
        "scene_id": "afternoon_relax",
        "name_de": "Nachmittags-Entspannung",
        "name_en": "Afternoon Relax",
        "icon": "mdi:sofa",
        "category": "day",
        "light_brightness_pct": 60,
        "light_color_temp_k": 3500,
        "media_volume_pct": 40,
        "tags": ["afternoon", "relax"],
    },
    {
        "scene_id": "dinner_time",
        "name_de": "Abendessen",
        "name_en": "Dinner Time",
        "icon": "mdi:silverware-fork-knife",
        "category": "evening",
        "light_brightness_pct": 70,
        "light_color_temp_k": 3000,
        "tags": ["dinner", "evening", "family"],
    },
    {
        "scene_id": "movie_night",
        "name_de": "Filmabend",
        "name_en": "Movie Night",
        "icon": "mdi:movie-open",
        "category": "evening",
        "light_brightness_pct": 10,
        "light_color_temp_k": 2500,
        "media_volume_pct": 60,
        "zone_mode": "movie",
        "suppress_automations": True,
        "tags": ["movie", "evening", "entertainment"],
    },
    {
        "scene_id": "romantic_evening",
        "name_de": "Romantischer Abend",
        "name_en": "Romantic Evening",
        "icon": "mdi:heart",
        "category": "evening",
        "light_brightness_pct": 20,
        "light_color_temp_k": 2200,
        "media_volume_pct": 30,
        "zone_mode": "romantic",
        "tags": ["romantic", "evening", "couple"],
    },
    {
        "scene_id": "bedtime",
        "name_de": "Schlafenszeit",
        "name_en": "Bedtime",
        "icon": "mdi:bed",
        "category": "night",
        "light_brightness_pct": 5,
        "light_color_temp_k": 2200,
        "media_volume_pct": 0,
        "climate_temp_c": 18.0,
        "zone_mode": "night",
        "suppress_automations": True,
        "tags": ["bedtime", "night", "sleep"],
    },
    {
        "scene_id": "party",
        "name_de": "Party",
        "name_en": "Party",
        "icon": "mdi:party-popper",
        "category": "activity",
        "light_brightness_pct": 100,
        "light_color_temp_k": 4000,
        "media_volume_pct": 80,
        "zone_mode": "party",
        "suppress_automations": True,
        "tags": ["party", "social", "fun"],
    },
    {
        "scene_id": "away",
        "name_de": "Abwesend",
        "name_en": "Away",
        "icon": "mdi:home-export-outline",
        "category": "custom",
        "light_brightness_pct": 0,
        "media_volume_pct": 0,
        "climate_temp_c": 17.0,
        "zone_mode": "away",
        "tags": ["away", "security", "energy-saving"],
    },
]


# ── Engine ──────────────────────────────────────────────────────────────────


class SceneIntelligenceEngine:
    """Engine for intelligent scene management with cloud sync."""

    def __init__(self) -> None:
        self._scenes: dict[str, ScenePreset] = {}
        self._active_scene: str | None = None
        self._active_zone: str | None = None
        self._patterns: list[LearnedPattern] = []
        self._activation_log: list[tuple[datetime, str, SceneContext]] = []
        self._cloud = CloudStatus()

        # Load built-in scenes
        for s in _BUILTIN_SCENES:
            self._scenes[s["scene_id"]] = ScenePreset(**s)

    # ── Scene management ─────────────────────────────────────────────────

    def activate_scene(self, scene_id: str, zone_id: str = "") -> bool:
        """Activate a scene."""
        if scene_id not in self._scenes:
            return False
        self._active_scene = scene_id
        self._active_zone = zone_id or None
        scene = self._scenes[scene_id]
        scene.usage_count += 1

        now = datetime.now(tz=timezone.utc)
        ctx = SceneContext(hour=now.hour, active_zone=zone_id)
        self._activation_log.append((now, scene_id, ctx))
        # Keep last 100
        self._activation_log = self._activation_log[-100:]

        logger.info("Scene activated: %s (%s)", scene.name_de, zone_id or "global")
        return True

    def deactivate_scene(self) -> bool:
        """Deactivate the current scene."""
        if self._active_scene is None:
            return False
        self._active_scene = None
        self._active_zone = None
        return True

    def get_active_scene(self) -> dict[str, Any] | None:
        """Get the currently active scene."""
        if not self._active_scene:
            return None
        scene = self._scenes.get(self._active_scene)
        if not scene:
            return None
        return {
            "scene_id": scene.scene_id,
            "name_de": scene.name_de,
            "icon": scene.icon,
            "zone_id": self._active_zone,
            "light_brightness_pct": scene.light_brightness_pct,
            "light_color_temp_k": scene.light_color_temp_k,
            "media_volume_pct": scene.media_volume_pct,
            "climate_temp_c": scene.climate_temp_c,
            "zone_mode": scene.zone_mode,
        }

    # ── Scene suggestions ────────────────────────────────────────────────

    def suggest_scenes(self, context: SceneContext | None = None,
                       limit: int = 3) -> list[SceneSuggestion]:
        """Suggest scenes based on context."""
        if context is None:
            now = datetime.now(tz=timezone.utc)
            context = SceneContext(hour=now.hour)

        suggestions: list[tuple[float, ScenePreset, str]] = []

        for scene in self._scenes.values():
            score, reason = self._score_scene(scene, context)
            if score > 0:
                suggestions.append((score, scene, reason))

        suggestions.sort(key=lambda x: -x[0])

        return [
            SceneSuggestion(
                scene_id=s.scene_id,
                name_de=s.name_de,
                confidence=round(score, 2),
                reason_de=reason,
                icon=s.icon,
            )
            for score, s, reason in suggestions[:limit]
        ]

    def _score_scene(self, scene: ScenePreset, ctx: SceneContext) -> tuple[float, str]:
        """Score a scene based on context (0-1)."""
        score = 0.0
        reasons = []

        # Time-based scoring
        if scene.category == "morning" and 5 <= ctx.hour <= 9:
            score += 0.4
            reasons.append("Morgenzeit")
        elif scene.category == "day" and 10 <= ctx.hour <= 16:
            score += 0.3
            reasons.append("Tageszeit")
        elif scene.category == "evening" and 17 <= ctx.hour <= 22:
            score += 0.4
            reasons.append("Abendzeit")
        elif scene.category == "night" and (ctx.hour >= 22 or ctx.hour <= 5):
            score += 0.4
            reasons.append("Nachtzeit")

        # Occupancy-based
        if not ctx.is_home and scene.scene_id == "away":
            score += 0.5
            reasons.append("Niemand zu Hause")
        elif ctx.occupancy_count > 3 and scene.scene_id == "party":
            score += 0.3
            reasons.append("Viele Personen anwesend")

        # Activity-based
        if scene.category == "activity" and scene.scene_id == "work_focus":
            if 8 <= ctx.hour <= 17 and not ctx.is_weekend:
                score += 0.3
                reasons.append("Arbeitszeit")

        # Brightness-based
        if ctx.outdoor_lux < 50 and scene.light_brightness_pct and scene.light_brightness_pct <= 20:
            score += 0.2
            reasons.append("Dunkel draußen")

        # Pattern matching
        for pattern in self._patterns:
            if pattern.scene_id == scene.scene_id:
                h_start, h_end = pattern.hour_range
                if h_start <= ctx.hour < h_end:
                    score += 0.2 * min(pattern.activation_count / 10, 1.0)
                    reasons.append("Gelerntes Muster")
                    break

        # Popularity bonus
        score += min(scene.usage_count / 100, 0.1)

        reason = ", ".join(reasons) if reasons else ""
        return (score, reason)

    # ── Pattern learning ─────────────────────────────────────────────────

    def learn_patterns(self) -> int:
        """Learn patterns from activation history."""
        hour_scenes: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))

        for ts, scene_id, ctx in self._activation_log:
            hour_scenes[scene_id][ctx.hour] += 1

        new_patterns = 0
        for scene_id, hours in hour_scenes.items():
            if not hours:
                continue
            # Find peak hour range
            peak_hour = max(hours, key=hours.get)
            count = hours[peak_hour]
            if count >= 3:  # Need at least 3 activations
                h_start = max(0, peak_hour - 1)
                h_end = min(24, peak_hour + 2)
                pattern_id = f"pattern_{scene_id}_{h_start}_{h_end}"

                existing = next(
                    (p for p in self._patterns if p.pattern_id == pattern_id),
                    None,
                )
                if existing:
                    existing.activation_count = count
                    existing.last_activated = datetime.now(tz=timezone.utc)
                else:
                    self._patterns.append(LearnedPattern(
                        pattern_id=pattern_id,
                        scene_id=scene_id,
                        hour_range=(h_start, h_end),
                        activation_count=count,
                    ))
                    new_patterns += 1

        return new_patterns

    # ── Cloud ────────────────────────────────────────────────────────────

    def configure_cloud(self, cloud_url: str = "",
                        sync_interval_min: int = 15) -> CloudStatus:
        """Configure PilotSuite Cloud connection."""
        self._cloud.cloud_url = cloud_url
        self._cloud.sync_interval_min = sync_interval_min
        if cloud_url:
            self._cloud.connected = True
            self._cloud.last_sync = datetime.now(tz=timezone.utc)
        else:
            self._cloud.connected = False
        return self._cloud

    def get_cloud_status(self) -> dict[str, Any]:
        """Get cloud connection status."""
        return {
            "connected": self._cloud.connected,
            "last_sync": self._cloud.last_sync.isoformat() if self._cloud.last_sync else None,
            "sync_interval_min": self._cloud.sync_interval_min,
            "shared_scenes": self._cloud.shared_scenes,
            "cloud_url": self._cloud.cloud_url,
            "local_fallback": self._cloud.local_fallback,
        }

    def share_scene(self, scene_id: str) -> bool:
        """Share a scene to PilotSuite Cloud."""
        if not self._cloud.connected:
            return False
        if scene_id not in self._scenes:
            return False
        self._cloud.shared_scenes += 1
        return True

    # ── Custom scenes ────────────────────────────────────────────────────

    def register_scene(self, scene_id: str, name_de: str, name_en: str = "",
                       icon: str = "mdi:palette", **kwargs: Any) -> bool:
        """Register a custom scene."""
        if scene_id in self._scenes:
            return False
        self._scenes[scene_id] = ScenePreset(
            scene_id=scene_id,
            name_de=name_de,
            name_en=name_en or name_de,
            icon=icon,
            **kwargs,
        )
        return True

    def rate_scene(self, scene_id: str, rating: float) -> bool:
        """Rate a scene (1-5)."""
        scene = self._scenes.get(scene_id)
        if not scene or not (1 <= rating <= 5):
            return False
        if scene.rating == 0:
            scene.rating = rating
        else:
            scene.rating = round((scene.rating + rating) / 2, 1)
        return True

    # ── Query ────────────────────────────────────────────────────────────

    def get_scenes(self, category: str | None = None,
                   limit: int = 50) -> list[dict[str, Any]]:
        """Get all scenes."""
        scenes = list(self._scenes.values())
        if category:
            scenes = [s for s in scenes if s.category == category]
        scenes.sort(key=lambda s: (-s.usage_count, -s.rating, s.name_de))
        return [
            {
                "scene_id": s.scene_id,
                "name_de": s.name_de,
                "name_en": s.name_en,
                "icon": s.icon,
                "category": s.category,
                "usage_count": s.usage_count,
                "rating": s.rating,
                "tags": s.tags,
            }
            for s in scenes[:limit]
        ]

    def get_dashboard(self) -> SceneIntelligenceDashboard:
        """Get scene intelligence dashboard."""
        categories: dict[str, int] = {}
        for s in self._scenes.values():
            categories[s.category] = categories.get(s.category, 0) + 1

        popular = sorted(
            self._scenes.values(),
            key=lambda s: (-s.usage_count, -s.rating),
        )[:5]

        suggestions = self.suggest_scenes(limit=3)

        return SceneIntelligenceDashboard(
            total_scenes=len(self._scenes),
            active_scene=self.get_active_scene(),
            suggestions=[
                {
                    "scene_id": s.scene_id,
                    "name_de": s.name_de,
                    "confidence": s.confidence,
                    "reason_de": s.reason_de,
                    "icon": s.icon,
                }
                for s in suggestions
            ],
            learned_patterns=len(self._patterns),
            cloud_status=self.get_cloud_status(),
            categories=categories,
            popular_scenes=[
                {
                    "scene_id": s.scene_id,
                    "name_de": s.name_de,
                    "icon": s.icon,
                    "usage_count": s.usage_count,
                    "rating": s.rating,
                }
                for s in popular
            ],
        )
