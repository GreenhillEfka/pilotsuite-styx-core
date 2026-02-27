"""Unified mood data models for PilotSuite Styx.

Central type definitions shared across engine, service, orchestrator, and API.
Combines discrete mood states with continuous mood dimensions.

Architecture:
    MoodState (enum) — 6 discrete states
    MoodDimensions — continuous scores (comfort, frugality, joy, energy, stress)
    ZoneMoodProfile — complete mood profile for a zone
    MoodTransition — state transition event
    EntityDependency — entity-to-mood-dimension mapping
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now_utc().isoformat()


class MoodState(str, Enum):
    """Discrete mood states for zone-based automation."""

    AWAY = "away"
    NIGHT = "night"
    RELAX = "relax"
    FOCUS = "focus"
    ACTIVE = "active"
    NEUTRAL = "neutral"

    @classmethod
    def from_str(cls, value: str) -> "MoodState":
        try:
            return cls(value.lower().strip())
        except ValueError:
            return cls.NEUTRAL


class MoodDimensionName(str, Enum):
    """Named continuous mood dimensions."""

    COMFORT = "comfort"
    FRUGALITY = "frugality"
    JOY = "joy"
    ENERGY = "energy"
    STRESS = "stress"


class EntityRole(str, Enum):
    """Role an entity plays in mood inference."""

    MOTION = "motion"
    ILLUMINANCE = "illuminance"
    MEDIA = "media"
    CLIMATE = "climate"
    PRESENCE = "presence"
    ENERGY_METER = "energy_meter"
    WEATHER = "weather"
    CALENDAR = "calendar"
    OVERRIDE = "override"


@dataclass(frozen=True)
class EntityDependency:
    """Maps an entity to its role in mood inference.

    Defines which mood dimensions an entity influences and with what weight.
    """

    entity_id: str
    role: EntityRole
    zone_id: str
    dimensions: tuple[MoodDimensionName, ...] = ()
    weight: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "role": self.role.value,
            "zone_id": self.zone_id,
            "dimensions": [d.value for d in self.dimensions],
            "weight": self.weight,
        }


@dataclass
class MoodDimensions:
    """Continuous mood dimensions (all 0.0–1.0)."""

    comfort: float = 0.5
    frugality: float = 0.5
    joy: float = 0.5
    energy: float = 0.5
    stress: float = 0.0

    def clamp(self) -> "MoodDimensions":
        """Clamp all values to [0, 1]."""
        self.comfort = max(0.0, min(1.0, self.comfort))
        self.frugality = max(0.0, min(1.0, self.frugality))
        self.joy = max(0.0, min(1.0, self.joy))
        self.energy = max(0.0, min(1.0, self.energy))
        self.stress = max(0.0, min(1.0, self.stress))
        return self

    def ema_blend(self, other: "MoodDimensions", alpha: float = 0.3) -> "MoodDimensions":
        """Exponential moving average blend: self * (1 - alpha) + other * alpha."""
        return MoodDimensions(
            comfort=self.comfort * (1 - alpha) + other.comfort * alpha,
            frugality=self.frugality * (1 - alpha) + other.frugality * alpha,
            joy=self.joy * (1 - alpha) + other.joy * alpha,
            energy=self.energy * (1 - alpha) + other.energy * alpha,
            stress=self.stress * (1 - alpha) + other.stress * alpha,
        ).clamp()

    def to_dict(self) -> Dict[str, float]:
        return {
            "comfort": round(self.comfort, 3),
            "frugality": round(self.frugality, 3),
            "joy": round(self.joy, 3),
            "energy": round(self.energy, 3),
            "stress": round(self.stress, 3),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MoodDimensions":
        def _safe_float(val: Any, default: float) -> float:
            try:
                return float(val)
            except (ValueError, TypeError):
                return default

        return cls(
            comfort=_safe_float(data.get("comfort", 0.5), 0.5),
            frugality=_safe_float(data.get("frugality", 0.5), 0.5),
            joy=_safe_float(data.get("joy", 0.5), 0.5),
            energy=_safe_float(data.get("energy", 0.5), 0.5),
            stress=_safe_float(data.get("stress", 0.0), 0.0),
        ).clamp()

    @property
    def dominant_dimension(self) -> MoodDimensionName:
        """Return the dimension with the highest deviation from neutral."""
        deviations = {
            MoodDimensionName.COMFORT: abs(self.comfort - 0.5),
            MoodDimensionName.FRUGALITY: abs(self.frugality - 0.5),
            MoodDimensionName.JOY: abs(self.joy - 0.5),
            MoodDimensionName.ENERGY: abs(self.energy - 0.5),
            MoodDimensionName.STRESS: abs(self.stress - 0.0),
        }
        return max(deviations, key=deviations.get)


@dataclass
class ZoneMoodProfile:
    """Complete mood profile for a single zone.

    Combines discrete mood state with continuous dimensions, confidence,
    metadata, and entity dependency tracking.
    """

    zone_id: str
    state: MoodState = MoodState.NEUTRAL
    dimensions: MoodDimensions = field(default_factory=MoodDimensions)
    confidence: float = 0.0
    reasons: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=_now_utc)

    # Sensor context
    motion_recent: bool = False
    ambient_dark: bool = False
    media_playing: bool = False
    quiet_hours: bool = False
    user_override: bool = False
    media_primary: Optional[str] = None
    time_of_day: str = "afternoon"
    occupancy_level: str = "low"

    # Entity dependencies that contributed to this profile
    contributing_entities: List[str] = field(default_factory=list)

    # Softmax probabilities for all states
    state_probabilities: Dict[str, float] = field(default_factory=dict)

    # ── Backwards compatibility (MoodResult migration) ─────────────
    @property
    def mood(self) -> MoodState:
        """Alias for ``state`` — used by orchestrator/actions (old MoodResult API)."""
        return self.state

    @property
    def features(self) -> "ZoneMoodProfile":
        """Return self as the feature container (old MoodResult.features compat)."""
        return self

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "state": self.state.value,
            "dimensions": self.dimensions.to_dict(),
            "confidence": round(self.confidence, 3),
            "reasons": self.reasons,
            "timestamp": self.timestamp.isoformat(),
            "motion_recent": self.motion_recent,
            "ambient_dark": self.ambient_dark,
            "media_playing": self.media_playing,
            "quiet_hours": self.quiet_hours,
            "user_override": self.user_override,
            "media_primary": self.media_primary,
            "time_of_day": self.time_of_day,
            "occupancy_level": self.occupancy_level,
            "contributing_entities": self.contributing_entities,
            "state_probabilities": {
                k: round(v, 3) for k, v in self.state_probabilities.items()
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ZoneMoodProfile":
        dims = MoodDimensions.from_dict(data.get("dimensions", {}))
        ts_raw = data.get("timestamp")
        if isinstance(ts_raw, str):
            try:
                ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                ts = _now_utc()
        elif isinstance(ts_raw, (int, float)):
            ts = datetime.fromtimestamp(ts_raw, tz=timezone.utc)
        else:
            ts = _now_utc()

        try:
            confidence = float(data.get("confidence", 0.0))
        except (ValueError, TypeError):
            confidence = 0.0

        return cls(
            zone_id=str(data.get("zone_id", "")),
            state=MoodState.from_str(str(data.get("state", "neutral"))),
            dimensions=dims,
            confidence=confidence,
            reasons=list(data.get("reasons", [])),
            timestamp=ts,
            motion_recent=bool(data.get("motion_recent", False)),
            ambient_dark=bool(data.get("ambient_dark", False)),
            media_playing=bool(data.get("media_playing", False)),
            quiet_hours=bool(data.get("quiet_hours", False)),
            user_override=bool(data.get("user_override", False)),
            media_primary=data.get("media_primary"),
            time_of_day=str(data.get("time_of_day", "afternoon")),
            occupancy_level=str(data.get("occupancy_level", "low")),
            contributing_entities=list(data.get("contributing_entities", [])),
            state_probabilities=dict(data.get("state_probabilities", {})),
        )


@dataclass
class MoodTransition:
    """Records a mood state transition event."""

    zone_id: str
    from_state: MoodState
    to_state: MoodState
    from_dimensions: MoodDimensions
    to_dimensions: MoodDimensions
    confidence: float
    trigger_reason: str
    timestamp: datetime = field(default_factory=_now_utc)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "from_state": self.from_state.value,
            "to_state": self.to_state.value,
            "from_dimensions": self.from_dimensions.to_dict(),
            "to_dimensions": self.to_dimensions.to_dict(),
            "confidence": round(self.confidence, 3),
            "trigger_reason": self.trigger_reason,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ZoneConfig:
    """Configuration for a single zone's mood inference."""

    name: str
    zone_id: str = ""
    motion_entities: List[str] = field(default_factory=list)
    light_entities: List[str] = field(default_factory=list)
    media_entities: List[str] = field(default_factory=list)
    climate_entities: List[str] = field(default_factory=list)
    presence_entities: List[str] = field(default_factory=list)
    illuminance_entity: Optional[str] = None
    energy_entities: List[str] = field(default_factory=list)

    # Thresholds
    motion_recent_minutes: int = 5
    dark_lux_threshold: float = 40.0
    away_no_motion_minutes: int = 30
    quiet_hours_start: str = "22:30"
    quiet_hours_end: str = "07:00"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ZoneConfig":
        return cls(
            name=str(data.get("name", "")),
            zone_id=str(data.get("zone_id", data.get("name", ""))),
            motion_entities=list(data.get("motion_entities", [])),
            light_entities=list(data.get("light_entities", [])),
            media_entities=list(data.get("media_entities", [])),
            climate_entities=list(data.get("climate_entities", [])),
            presence_entities=list(data.get("presence_entities", [])),
            illuminance_entity=data.get("illuminance_entity"),
            energy_entities=list(data.get("energy_entities", [])),
            motion_recent_minutes=int(data.get("motion_recent_minutes", 5)),
            dark_lux_threshold=float(data.get("dark_lux_threshold", 40.0)),
            away_no_motion_minutes=int(data.get("away_no_motion_minutes", 30)),
            quiet_hours_start=str(data.get("quiet_hours_start", "22:30")),
            quiet_hours_end=str(data.get("quiet_hours_end", "07:00")),
        )

    def get_all_entity_ids(self) -> List[str]:
        """Return all entity IDs referenced by this zone config."""
        entities = []
        entities.extend(self.motion_entities)
        entities.extend(self.light_entities)
        entities.extend(self.media_entities)
        entities.extend(self.climate_entities)
        entities.extend(self.presence_entities)
        entities.extend(self.energy_entities)
        if self.illuminance_entity:
            entities.append(self.illuminance_entity)
        return entities

    def build_dependencies(self) -> List[EntityDependency]:
        """Build entity dependency list from this zone config."""
        deps: List[EntityDependency] = []
        zone = self.zone_id or self.name

        for eid in self.motion_entities:
            deps.append(EntityDependency(
                entity_id=eid, role=EntityRole.MOTION, zone_id=zone,
                dimensions=(MoodDimensionName.ENERGY, MoodDimensionName.STRESS),
            ))
        for eid in self.light_entities:
            deps.append(EntityDependency(
                entity_id=eid, role=EntityRole.ILLUMINANCE, zone_id=zone,
                dimensions=(MoodDimensionName.COMFORT,),
            ))
        for eid in self.media_entities:
            deps.append(EntityDependency(
                entity_id=eid, role=EntityRole.MEDIA, zone_id=zone,
                dimensions=(MoodDimensionName.JOY, MoodDimensionName.COMFORT),
            ))
        for eid in self.climate_entities:
            deps.append(EntityDependency(
                entity_id=eid, role=EntityRole.CLIMATE, zone_id=zone,
                dimensions=(MoodDimensionName.COMFORT, MoodDimensionName.FRUGALITY),
            ))
        for eid in self.presence_entities:
            deps.append(EntityDependency(
                entity_id=eid, role=EntityRole.PRESENCE, zone_id=zone,
                dimensions=(MoodDimensionName.ENERGY,),
            ))
        if self.illuminance_entity:
            deps.append(EntityDependency(
                entity_id=self.illuminance_entity, role=EntityRole.ILLUMINANCE,
                zone_id=zone,
                dimensions=(MoodDimensionName.COMFORT, MoodDimensionName.ENERGY),
            ))
        for eid in self.energy_entities:
            deps.append(EntityDependency(
                entity_id=eid, role=EntityRole.ENERGY_METER, zone_id=zone,
                dimensions=(MoodDimensionName.FRUGALITY,),
            ))
        return deps


@dataclass
class MoodSystemConfig:
    """Global mood system configuration."""

    zones: Dict[str, ZoneConfig] = field(default_factory=dict)
    min_dwell_time_seconds: int = 600
    action_cooldown_seconds: int = 120
    ema_alpha: float = 0.3
    softmax_temperature: float = 1.0
    half_life_seconds: float = 900.0
    neutral_threshold: float = 0.15
    history_retention_days: int = 30
    max_history_entries: int = 50_000
    save_throttle_seconds: int = 60

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zones": {k: v.to_dict() for k, v in self.zones.items()},
            "min_dwell_time_seconds": self.min_dwell_time_seconds,
            "action_cooldown_seconds": self.action_cooldown_seconds,
            "ema_alpha": self.ema_alpha,
            "softmax_temperature": self.softmax_temperature,
            "half_life_seconds": self.half_life_seconds,
            "neutral_threshold": self.neutral_threshold,
            "history_retention_days": self.history_retention_days,
            "max_history_entries": self.max_history_entries,
            "save_throttle_seconds": self.save_throttle_seconds,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MoodSystemConfig":
        zones_raw = data.get("zones", {})
        zones = {}
        if isinstance(zones_raw, dict):
            for k, v in zones_raw.items():
                zones[k] = ZoneConfig.from_dict(v) if isinstance(v, dict) else v
        return cls(
            zones=zones,
            min_dwell_time_seconds=int(data.get("min_dwell_time_seconds", 600)),
            action_cooldown_seconds=int(data.get("action_cooldown_seconds", 120)),
            ema_alpha=float(data.get("ema_alpha", 0.3)),
            softmax_temperature=float(data.get("softmax_temperature", 1.0)),
            half_life_seconds=float(data.get("half_life_seconds", 900.0)),
            neutral_threshold=float(data.get("neutral_threshold", 0.15)),
            history_retention_days=int(data.get("history_retention_days", 30)),
            max_history_entries=int(data.get("max_history_entries", 50_000)),
            save_throttle_seconds=int(data.get("save_throttle_seconds", 60)),
        )
