"""Unified Mood Inference Engine v3.0 — PilotSuite Styx.

Combines discrete mood state inference (Softmax + EMA hysteresis) with
continuous mood dimensions (comfort, frugality, joy, energy, stress).

Mathematical models:
- Sigmoid activation functions for smooth, bounded feature scoring
- Softmax mood selection for probabilistic multi-class decision
- Exponential Moving Average (EMA) for hysteresis smoothing
- Gaussian comfort curves (log-space, optimal 100–400 lux)
- Circadian energy modulation (sine wave, peak at solar noon)

References:
- Softmax: Bridle (1990) — probabilistic interpretation of neural outputs
- EMA smoothing: Roberts (1959) — exponential weighted moving average
- Sigmoid activation: Verhulst (1845) — logistic function
"""
from __future__ import annotations

import logging
import math
from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .models import (
    EntityDependency,
    MoodDimensions,
    MoodState,
    MoodSystemConfig,
    MoodTransition,
    ZoneConfig,
    ZoneMoodProfile,
)

_LOGGER = logging.getLogger(__name__)

# Maximum transition history per zone
_MAX_TRANSITION_HISTORY = 50


class UnifiedMoodEngine:
    """Core mood inference engine (v3.0).

    Produces a ``ZoneMoodProfile`` for each zone containing:
    - Discrete mood state (AWAY/NIGHT/RELAX/FOCUS/ACTIVE/NEUTRAL)
    - Continuous dimensions (comfort/frugality/joy/energy/stress)
    - Softmax probabilities for all states
    - Confidence score
    - Contributing entity list
    """

    def __init__(self, config: MoodSystemConfig):
        self.config = config
        self._profiles: Dict[str, ZoneMoodProfile] = {}
        self._dwell_start: Dict[str, datetime] = {}
        self._transition_history: Dict[str, deque] = {}

    # ── Public API ──────────────────────────────────────────────────────

    def infer_zone(
        self,
        zone_name: str,
        sensor_data: Dict[str, Any],
        *,
        now: Optional[datetime] = None,
    ) -> ZoneMoodProfile:
        """Run complete mood inference for a zone.

        Args:
            zone_name: Zone identifier (must exist in config.zones).
            sensor_data: Flat dict of entity_id → {state, attributes, last_changed}.
            now: Override current time (for testing).

        Returns:
            ZoneMoodProfile with discrete state + continuous dimensions.
        """
        if zone_name not in self.config.zones:
            _LOGGER.warning("Unknown zone %s, returning neutral profile", zone_name)
            return ZoneMoodProfile(zone_id=zone_name)

        now = now or datetime.now(timezone.utc)
        zone_cfg = self.config.zones[zone_name]

        # Step 1 — Extract features from sensor data
        features = self._extract_features(zone_cfg, sensor_data, now)

        # Step 2 — Compute continuous mood dimensions
        dimensions = self._compute_dimensions(zone_cfg, features, sensor_data, now)

        # Step 3 — Compute discrete state scores → softmax
        raw_scores, state_reasons = self._compute_state_scores(
            zone_cfg, features, dimensions, now
        )
        probabilities = self._softmax(raw_scores, self.config.softmax_temperature)

        # Step 4 — Select winning state
        new_state = max(probabilities, key=probabilities.get)
        raw_confidence = probabilities[new_state]

        # Step 5 — EMA hysteresis + dwell-time gating
        state, confidence, reasons = self._apply_hysteresis(
            zone_name, new_state, raw_confidence, state_reasons, now
        )

        # Step 6 — Blend dimensions with previous via EMA
        prev_profile = self._profiles.get(zone_name)
        if prev_profile:
            dimensions = prev_profile.dimensions.ema_blend(
                dimensions, alpha=self.config.ema_alpha
            )

        # Step 7 — Build contributing entity list
        contributing = self._get_contributing_entities(zone_cfg, sensor_data)

        profile = ZoneMoodProfile(
            zone_id=zone_cfg.zone_id or zone_name,
            state=state,
            dimensions=dimensions,
            confidence=round(confidence, 3),
            reasons=reasons,
            timestamp=now,
            motion_recent=features["motion_recent"],
            ambient_dark=features["ambient_dark"],
            media_playing=features["media_playing"],
            quiet_hours=features["quiet_hours"],
            user_override=features["user_override"],
            media_primary=features.get("media_primary"),
            time_of_day=features["time_of_day"],
            occupancy_level=features["occupancy_level"],
            contributing_entities=contributing,
            state_probabilities={s.value: round(p, 3) for s, p in probabilities.items()},
        )

        # Record transition if state changed
        if prev_profile and prev_profile.state != state:
            transition = MoodTransition(
                zone_id=zone_name,
                from_state=prev_profile.state,
                to_state=state,
                from_dimensions=prev_profile.dimensions,
                to_dimensions=dimensions,
                confidence=confidence,
                trigger_reason="; ".join(reasons[:3]),
                timestamp=now,
            )
            history = self._transition_history.setdefault(
                zone_name, deque(maxlen=_MAX_TRANSITION_HISTORY)
            )
            history.append(transition)

        self._profiles[zone_name] = profile
        return profile

    def get_profile(self, zone_name: str) -> Optional[ZoneMoodProfile]:
        """Get current mood profile for a zone."""
        return self._profiles.get(zone_name)

    def get_all_profiles(self) -> Dict[str, ZoneMoodProfile]:
        """Get all current zone mood profiles."""
        return dict(self._profiles)

    def get_transitions(self, zone_name: str, limit: int = 20) -> List[MoodTransition]:
        """Get recent mood transitions for a zone."""
        history = self._transition_history.get(zone_name, deque())
        items = list(history)
        return items[-limit:]

    def list_zones(self) -> List[str]:
        """Get list of configured zones."""
        return list(self.config.zones.keys())

    def add_zone(self, zone_name: str, zone_config: ZoneConfig) -> None:
        """Add or update a zone configuration at runtime."""
        self.config.zones[zone_name] = zone_config

    def remove_zone(self, zone_name: str) -> bool:
        """Remove a zone. Returns True if the zone existed."""
        existed = zone_name in self.config.zones
        self.config.zones.pop(zone_name, None)
        self._profiles.pop(zone_name, None)
        self._dwell_start.pop(zone_name, None)
        self._transition_history.pop(zone_name, None)
        return existed

    # ── Backwards-compatible two-step API (orchestrator compat) ──────

    def compute_zone_features(
        self, zone_name: str, sensor_data: Dict[str, Any]
    ) -> ZoneMoodProfile:
        """Compatibility stub: extract features into a *partial* ZoneMoodProfile.

        The old ``MoodEngine`` had a separate ``compute_zone_features`` followed
        by ``infer_mood``.  The new engine does everything in ``infer_zone``.
        This method returns a profile with features populated so callers that
        still use the two-step flow keep working.
        """
        return self.infer_zone(zone_name, sensor_data)

    def infer_mood(
        self, zone_name: str, features: ZoneMoodProfile
    ) -> ZoneMoodProfile:
        """Compatibility stub: return the profile unchanged.

        ``compute_zone_features`` already produced a complete profile via
        ``infer_zone``, so there is nothing more to do here.
        """
        return features

    def get_entity_dependencies(self, zone_name: str) -> List[EntityDependency]:
        """Get all entity dependencies for a zone."""
        zone_cfg = self.config.zones.get(zone_name)
        if not zone_cfg:
            return []
        return zone_cfg.build_dependencies()

    def get_all_entity_dependencies(self) -> Dict[str, List[EntityDependency]]:
        """Get entity dependencies for all zones."""
        return {
            zone_name: zone_cfg.build_dependencies()
            for zone_name, zone_cfg in self.config.zones.items()
        }

    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics across all zones."""
        profiles = list(self._profiles.values())
        if not profiles:
            return {
                "zones": 0,
                "average_comfort": 0.5,
                "average_frugality": 0.5,
                "average_joy": 0.5,
                "average_energy": 0.5,
                "average_stress": 0.0,
                "state_distribution": {},
                "zones_with_media": 0,
            }

        n = len(profiles)
        state_counts: Dict[str, int] = {}
        for p in profiles:
            state_counts[p.state.value] = state_counts.get(p.state.value, 0) + 1

        return {
            "zones": n,
            "average_comfort": round(sum(p.dimensions.comfort for p in profiles) / n, 3),
            "average_frugality": round(sum(p.dimensions.frugality for p in profiles) / n, 3),
            "average_joy": round(sum(p.dimensions.joy for p in profiles) / n, 3),
            "average_energy": round(sum(p.dimensions.energy for p in profiles) / n, 3),
            "average_stress": round(sum(p.dimensions.stress for p in profiles) / n, 3),
            "state_distribution": state_counts,
            "zones_with_media": sum(1 for p in profiles if p.media_playing),
            "zone_profiles": {p.zone_id: p.to_dict() for p in profiles},
        }

    # ── Feature Extraction ──────────────────────────────────────────────

    def _extract_features(
        self,
        zone_cfg: ZoneConfig,
        sensor_data: Dict[str, Any],
        now: datetime,
    ) -> Dict[str, Any]:
        """Extract boolean and categorical features from raw sensor data."""
        features: Dict[str, Any] = {
            "motion_recent": False,
            "ambient_dark": False,
            "media_playing": False,
            "quiet_hours": False,
            "user_override": False,
            "media_primary": None,
            "illuminance_value": None,
            "last_motion_ts": None,
            "motion_entities": {},
            "time_of_day": self._classify_time_of_day(now),
            "occupancy_level": "low",
        }

        # ── Motion analysis
        latest_motion: Optional[datetime] = None
        any_motion = False
        active_count = 0
        motion_states: Dict[str, bool] = {}

        for entity_id in zone_cfg.motion_entities:
            state = _get_state_str(sensor_data, entity_id)
            is_on = state in ("on", "true", "1")
            motion_states[entity_id] = is_on
            if is_on:
                any_motion = True
                active_count += 1
                ts = _parse_last_changed(sensor_data, entity_id)
                if ts and (latest_motion is None or ts > latest_motion):
                    latest_motion = ts

        features["motion_entities"] = motion_states
        features["last_motion_ts"] = latest_motion

        if latest_motion:
            age_min = (now - latest_motion).total_seconds() / 60
            features["motion_recent"] = age_min <= zone_cfg.motion_recent_minutes
        else:
            features["motion_recent"] = any_motion

        # Occupancy from motion density
        total_motion = max(1, len(zone_cfg.motion_entities))
        motion_ratio = active_count / total_motion
        if motion_ratio > 0.7:
            features["occupancy_level"] = "high"
        elif motion_ratio > 0.3:
            features["occupancy_level"] = "medium"
        else:
            features["occupancy_level"] = "low"

        # ── Illuminance
        if zone_cfg.illuminance_entity:
            lux_str = _get_state_str(sensor_data, zone_cfg.illuminance_entity)
            try:
                lux = float(lux_str)
                features["illuminance_value"] = lux
                features["ambient_dark"] = lux < zone_cfg.dark_lux_threshold
            except (ValueError, TypeError):
                features["ambient_dark"] = self._is_night_hours(now, zone_cfg)
        else:
            features["ambient_dark"] = self._is_night_hours(now, zone_cfg)

        # ── Media
        for entity_id in zone_cfg.media_entities:
            state = _get_state_str(sensor_data, entity_id)
            if state in ("playing", "on"):
                features["media_playing"] = True
                attrs = _get_attrs(sensor_data, entity_id)
                features["media_primary"] = attrs.get(
                    "media_title", attrs.get("friendly_name", entity_id)
                )
                break

        # ── Quiet hours
        features["quiet_hours"] = self._is_quiet_hours(now, zone_cfg)

        # ── User override
        override_entity = f"input_boolean.mood_manual_override_{zone_cfg.name}"
        if override_entity in sensor_data:
            override_state = _get_state_str(sensor_data, override_entity)
            features["user_override"] = override_state in ("on", "true", "1")

        return features

    # ── Continuous Dimensions ───────────────────────────────────────────

    def _compute_dimensions(
        self,
        zone_cfg: ZoneConfig,
        features: Dict[str, Any],
        sensor_data: Dict[str, Any],
        now: datetime,
    ) -> MoodDimensions:
        """Compute continuous mood dimensions from features + sensor data."""

        # ── Comfort (0..1): lux Gaussian + media + time-of-day ──
        comfort_signals: list[float] = []

        lux_val = features.get("illuminance_value")
        if lux_val is not None and lux_val > 0:
            lux = max(1.0, lux_val)
            log_ratio = math.log(lux / 200.0)
            lux_comfort = math.exp(-0.5 * (log_ratio / 0.7) ** 2)
            comfort_signals.append(lux_comfort)

        if features["media_playing"]:
            comfort_signals.append(0.7)

        if features["quiet_hours"]:
            comfort_signals.append(0.3)
        else:
            comfort_signals.append(0.6)

        # Climate: if we have climate entities, check comfort
        for eid in zone_cfg.climate_entities:
            temp_str = _get_attr(sensor_data, eid, "current_temperature")
            if temp_str:
                try:
                    temp = float(temp_str)
                    # Gaussian comfort around 21°C with σ=3
                    temp_comfort = math.exp(-0.5 * ((temp - 21.0) / 3.0) ** 2)
                    comfort_signals.append(temp_comfort)
                except (ValueError, TypeError):
                    pass

        if comfort_signals:
            log_sum = sum(math.log(max(0.01, s)) for s in comfort_signals)
            comfort = math.exp(log_sum / len(comfort_signals))
        else:
            comfort = 0.5

        # ── Frugality (0..1): time-based + energy usage ──
        tod = features["time_of_day"]
        frugality_by_time = {
            "morning": 0.4,
            "afternoon": 0.5,
            "evening": 0.3,
            "night": 0.7,
        }
        frugality = frugality_by_time.get(tod, 0.5)

        # If many lights on → reduce frugality
        lights_on = 0
        for eid in zone_cfg.light_entities:
            if _get_state_str(sensor_data, eid) in ("on", "true"):
                lights_on += 1
        if lights_on > 2:
            frugality *= 0.7

        # ── Joy (0..1): media + occupancy ──
        joy = 0.2  # baseline
        if features["media_playing"]:
            joy += 0.5
        if features["occupancy_level"] == "high":
            joy += 0.2
        elif features["occupancy_level"] == "medium":
            joy += 0.1
        if tod == "evening":
            joy += 0.1
        joy = min(1.0, joy)

        # ── Energy (0..1): circadian + motion + light ──
        now_hour = now.hour + now.minute / 60.0
        if 5.0 <= now_hour <= 23.0:
            circadian = math.sin(math.pi * (now_hour - 5.0) / 18.0)
            circadian = max(0.0, circadian)
        else:
            circadian = 0.0

        energy_raw = 0.3 * circadian
        if features["motion_recent"]:
            energy_raw += 0.4
        if not features["ambient_dark"]:
            energy_raw += 0.2
        if features["quiet_hours"]:
            energy_raw -= 0.3

        energy = _sigmoid(energy_raw, k=6.0, x0=0.35)

        # ── Stress (0..1): multi-sensor activation ──
        motion_states = features.get("motion_entities", {})
        active_motion = sum(1 for v in motion_states.values() if v)
        total_motion = max(1, len(motion_states))
        motion_ratio = active_motion / total_motion

        stress_raw = _sigmoid(motion_ratio, k=10.0, x0=0.6)
        if features["ambient_dark"] and features["motion_recent"]:
            stress_raw += 0.3
        if motion_ratio > 0.8 and total_motion > 2:
            stress_raw += 0.2

        stress = _sigmoid(stress_raw, k=4.0, x0=0.5)

        return MoodDimensions(
            comfort=comfort,
            frugality=frugality,
            joy=joy,
            energy=energy,
            stress=stress,
        ).clamp()

    # ── Discrete State Scoring ──────────────────────────────────────────

    def _compute_state_scores(
        self,
        zone_cfg: ZoneConfig,
        features: Dict[str, Any],
        dims: MoodDimensions,
        now: datetime,
    ) -> tuple[Dict[MoodState, float], List[str]]:
        """Compute raw log-odds scores for each discrete mood state."""
        raw_scores: Dict[MoodState, float] = {}
        reasons: List[str] = []

        # AWAY: sigmoid on no-motion duration
        last_motion = features.get("last_motion_ts")
        if last_motion:
            no_motion_min = (now - last_motion).total_seconds() / 60
        elif not features["motion_recent"]:
            no_motion_min = zone_cfg.away_no_motion_minutes + 10
        else:
            no_motion_min = 0.0

        away_score = _sigmoid(no_motion_min, k=0.15, x0=zone_cfg.away_no_motion_minutes)
        raw_scores[MoodState.AWAY] = away_score * 3.0
        if away_score > 0.5:
            reasons.append(f"No motion for {no_motion_min:.0f} min")

        # NIGHT: quiet hours + darkness
        night_signal = 0.0
        if features["quiet_hours"]:
            night_signal += 0.6
        if features["ambient_dark"]:
            night_signal += 0.4
        if features["media_playing"]:
            night_signal -= 0.2
        raw_scores[MoodState.NIGHT] = night_signal * 3.0
        if night_signal > 0.5:
            reasons.append("Quiet hours/dark environment")

        # RELAX: media + low energy + comfort
        relax_signal = 0.0
        if features["media_playing"]:
            relax_signal += 0.5
        if features["ambient_dark"]:
            relax_signal += 0.2
        relax_signal += (1.0 - dims.energy) * 0.2
        relax_signal += dims.comfort * 0.1
        raw_scores[MoodState.RELAX] = relax_signal * 3.0
        if relax_signal > 0.4:
            reasons.append("Media/low-energy environment")

        # FOCUS: motion + no media + daylight + low stress
        focus_signal = 0.0
        if features["motion_recent"] and not features["media_playing"]:
            focus_signal += 0.5
        if not features["ambient_dark"]:
            focus_signal += 0.2
        if not features["quiet_hours"]:
            focus_signal += 0.15
        focus_signal += (1.0 - dims.stress) * 0.15
        raw_scores[MoodState.FOCUS] = focus_signal * 3.0
        if focus_signal > 0.5:
            reasons.append("Active presence, daylight, no media")

        # ACTIVE: strong motion + bright + high energy
        active_signal = 0.0
        if features["motion_recent"]:
            active_signal += 0.4
        if not features["ambient_dark"]:
            active_signal += 0.2
        active_signal += dims.energy * 0.3
        if features["quiet_hours"]:
            active_signal -= 0.3
        raw_scores[MoodState.ACTIVE] = active_signal * 3.0
        if active_signal > 0.5:
            reasons.append("High activity with good lighting")

        # NEUTRAL: baseline
        raw_scores[MoodState.NEUTRAL] = 0.5

        # User override dominates
        if features["user_override"]:
            raw_scores = {m: 0.0 for m in MoodState}
            raw_scores[MoodState.NEUTRAL] = 5.0
            reasons = ["User manual override"]

        return raw_scores, reasons

    # ── Softmax ─────────────────────────────────────────────────────────

    @staticmethod
    def _softmax(
        scores: Dict[MoodState, float], temperature: float = 1.0
    ) -> Dict[MoodState, float]:
        """Numerically stable softmax over mood states."""
        if not scores:
            return {MoodState.NEUTRAL: 1.0}
        max_score = max(scores.values())
        exp_scores = {}
        for state, score in scores.items():
            exp_scores[state] = math.exp((score - max_score) / max(0.01, temperature))
        total = sum(exp_scores.values()) or 1.0
        return {state: val / total for state, val in exp_scores.items()}

    # ── Hysteresis ──────────────────────────────────────────────────────

    def _apply_hysteresis(
        self,
        zone_name: str,
        new_state: MoodState,
        raw_confidence: float,
        reasons: List[str],
        now: datetime,
    ) -> tuple[MoodState, float, List[str]]:
        """Apply EMA smoothing and dwell-time gating."""
        prev = self._profiles.get(zone_name)

        if prev and prev.state != new_state:
            alpha = self.config.ema_alpha
            ema_conf = alpha * raw_confidence + (1 - alpha) * prev.confidence

            dwell_start = self._dwell_start.get(zone_name, now)
            dwell_sec = (now - dwell_start).total_seconds()

            if dwell_sec < self.config.min_dwell_time_seconds:
                reasons.append(
                    f"Hysteresis: keeping {prev.state.value} "
                    f"(dwell {dwell_sec:.0f}s/{self.config.min_dwell_time_seconds}s)"
                )
                return prev.state, ema_conf, reasons
            else:
                self._dwell_start[zone_name] = now
                return new_state, ema_conf, reasons
        else:
            if zone_name not in self._dwell_start:
                self._dwell_start[zone_name] = now
            return new_state, raw_confidence, reasons

    # ── Helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _classify_time_of_day(dt: datetime) -> str:
        hour = dt.hour
        if 5 <= hour < 11:
            return "morning"
        elif 11 <= hour < 17:
            return "afternoon"
        elif 17 <= hour < 22:
            return "evening"
        else:
            return "night"

    @staticmethod
    def _is_night_hours(dt: datetime, zone_cfg: ZoneConfig) -> bool:
        hour = dt.hour
        return hour < 7 or hour > 22

    @staticmethod
    def _is_quiet_hours(dt: datetime, zone_cfg: ZoneConfig) -> bool:
        try:
            start_h, start_m = map(int, zone_cfg.quiet_hours_start.split(":"))
            end_h, end_m = map(int, zone_cfg.quiet_hours_end.split(":"))
            current = dt.hour * 60 + dt.minute
            start = start_h * 60 + start_m
            end = end_h * 60 + end_m
            if start > end:
                return current >= start or current <= end
            return start <= current <= end
        except (ValueError, IndexError):
            return False

    @staticmethod
    def _get_contributing_entities(
        zone_cfg: ZoneConfig, sensor_data: Dict[str, Any]
    ) -> List[str]:
        """Return entity IDs that actually contributed data."""
        all_ids = zone_cfg.get_all_entity_ids()
        return [eid for eid in all_ids if eid in sensor_data]


# ── Module-level helpers ────────────────────────────────────────────────


def _sigmoid(x: float, k: float = 1.0, x0: float = 0.0) -> float:
    """Standard sigmoid: 1 / (1 + exp(-k * (x - x0)))."""
    z = -k * (x - x0)
    if z > 500:
        return 0.0
    if z < -500:
        return 1.0
    return 1.0 / (1.0 + math.exp(z))


def _get_state_str(sensor_data: Dict[str, Any], entity_id: str) -> str:
    """Safely extract state string from sensor_data."""
    entry = sensor_data.get(entity_id)
    if entry is None:
        return ""
    if isinstance(entry, dict):
        return str(entry.get("state", "")).lower().strip()
    return str(entry).lower().strip()


def _get_attrs(sensor_data: Dict[str, Any], entity_id: str) -> Dict[str, Any]:
    """Safely extract attributes dict from sensor_data."""
    entry = sensor_data.get(entity_id)
    if isinstance(entry, dict):
        return entry.get("attributes", {})
    return {}


def _get_attr(
    sensor_data: Dict[str, Any], entity_id: str, attr_name: str
) -> Optional[str]:
    """Safely extract a single attribute value."""
    attrs = _get_attrs(sensor_data, entity_id)
    val = attrs.get(attr_name)
    return str(val) if val is not None else None


def _parse_last_changed(
    sensor_data: Dict[str, Any], entity_id: str
) -> Optional[datetime]:
    """Parse last_changed from sensor_data entry."""
    entry = sensor_data.get(entity_id)
    if not isinstance(entry, dict):
        return None
    lc = entry.get("last_changed")
    if lc is None:
        return None
    if isinstance(lc, datetime):
        return lc
    if isinstance(lc, str):
        try:
            return datetime.fromisoformat(lc.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None
    if isinstance(lc, (int, float)):
        try:
            return datetime.fromtimestamp(lc, tz=timezone.utc)
        except (ValueError, OSError):
            return None
    return None


# ── Backwards compatibility aliases ─────────────────────────────────────
# Keep old imports working during migration

MoodEngine = UnifiedMoodEngine
MoodConfig = MoodSystemConfig
MoodResult = ZoneMoodProfile  # orchestrator / actions compat

# Old dataclass stubs — redirect to models.py
from .models import MoodState, ZoneConfig, MoodDimensions  # noqa: F811, E402
