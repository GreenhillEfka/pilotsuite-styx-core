"""Adaptive Light Module Service — Presence, Brightness Ratio, Circadian (v1.0.0).

Computes ideal light settings per Habitus zone based on three inputs:

1. **Presence**: Motion detected in a zone -> turn on lights at appropriate brightness.
2. **Brightness ratio**: Compare outdoor lux to indoor lux -> adjust brightness.
   - High outdoor brightness -> lower indoor brightness (natural light sufficient).
   - Low outdoor brightness -> increase indoor brightness.
3. **Circadian**: Warm colors (2200-2700K) in evening, cool colors (4500-5500K) during day.
   Color temperature follows a smooth curve throughout the day.

Each Habitus zone has its own light profile (light entities, sensors, thresholds).
Profiles are persisted to /data/light_module.json.
"""

from __future__ import annotations

import json
import logging
import math
import os
import time
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Persistence path (HA add-on volume mount)
_DATA_DIR = Path(os.environ.get("LIGHT_MODULE_DATA_DIR", "/data"))
_PROFILES_FILE = _DATA_DIR / "light_module.json"

# Default global configuration
_DEFAULT_GLOBAL_CONFIG: dict[str, Any] = {
    "enabled": True,
    "circadian_enabled": True,
    "brightness_ratio_enabled": True,
    "presence_enabled": True,
    "default_presence_timeout_s": 300,
    "default_min_brightness_pct": 10,
    "default_max_brightness_pct": 100,
    "default_color_temp_min_k": 2200,
    "default_color_temp_max_k": 5500,
    "outdoor_lux_bright_threshold": 10000,
    "outdoor_lux_dark_threshold": 100,
}


# ---- Data Models ---------------------------------------------------------


@dataclass
class ZoneLightProfile:
    """Light profile configuration for a single Habitus zone."""

    zone_id: str
    enabled: bool = True
    lights: list[str] = field(default_factory=list)
    motion_sensor: str = ""
    brightness_sensor: str = ""
    outdoor_brightness_sensor: str = "sensor.outdoor_lux"
    min_brightness_pct: int = 10
    max_brightness_pct: int = 100
    color_temp_min_k: int = 2200
    color_temp_max_k: int = 5500
    presence_timeout_s: int = 300
    mode: str = "auto"  # auto, manual, circadian, presence_only

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ZoneLightProfile:
        """Create a profile from a dict, ignoring unknown keys."""
        known = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


@dataclass
class ZoneLightState:
    """Current computed light state for a zone."""

    zone_id: str
    brightness_pct: int = 0
    color_temp_k: int = 4000
    should_be_on: bool = False
    reason: str = "idle"
    presence_detected: bool = False
    last_motion_ts: float = 0.0
    indoor_lux: float = 0.0
    outdoor_lux: float = 0.0
    mode: str = "auto"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LightEvaluation:
    """Result of evaluating light settings for a zone."""

    brightness_pct: int = 0
    color_temp_k: int = 4000
    should_be_on: bool = False
    reason: str = "idle"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---- Circadian Curve -----------------------------------------------------


def circadian_color_temp(
    hour: float,
    min_k: int = 2200,
    max_k: int = 5500,
) -> int:
    """Compute circadian color temperature for a given hour of day.

    Uses a smooth cosine curve:
    - Peak cool (max_k) around 12:00 (noon)
    - Warmest (min_k) around 22:00-04:00 (night)

    Args:
        hour: Hour of day as float (0.0-24.0), e.g. 14.5 = 14:30.
        min_k: Minimum (warmest) color temperature in Kelvin.
        max_k: Maximum (coolest) color temperature in Kelvin.

    Returns:
        Color temperature in Kelvin.
    """
    # Shift so that the peak (max_k) is at hour 12
    # and the trough (min_k) is at hour 0/24
    # cosine: 1 at 0, -1 at pi, 1 at 2pi
    # We want: 1 at noon (hour=12), -1 at midnight (hour=0/24)
    angle = 2 * math.pi * (hour - 12) / 24.0
    # normalized 0..1: 0 at midnight, 1 at noon
    t = (math.cos(angle) + 1.0) / 2.0
    return int(min_k + t * (max_k - min_k))


def circadian_brightness_factor(hour: float) -> float:
    """Return a brightness scaling factor (0.0-1.0) based on time of day.

    Lower brightness in evening/night, higher during the day.
    - Full brightness from 08:00-17:00
    - Gradual ramp down from 17:00-22:00
    - Minimum from 22:00-06:00
    - Gradual ramp up from 06:00-08:00
    """
    if 8.0 <= hour <= 17.0:
        return 1.0
    elif 22.0 <= hour or hour < 6.0:
        return 0.3
    elif 17.0 < hour < 22.0:
        # Linear ramp down: 1.0 at 17:00 -> 0.3 at 22:00
        return 1.0 - 0.7 * ((hour - 17.0) / 5.0)
    else:
        # 6:00-8:00: Linear ramp up: 0.3 at 6:00 -> 1.0 at 8:00
        return 0.3 + 0.7 * ((hour - 6.0) / 2.0)


# ---- Brightness Ratio Logic ----------------------------------------------


def brightness_ratio_adjustment(
    outdoor_lux: float,
    indoor_lux: float,
    min_brightness_pct: int,
    max_brightness_pct: int,
    bright_threshold: float = 10000.0,
    dark_threshold: float = 100.0,
) -> int:
    """Compute target brightness % based on indoor/outdoor brightness ratio.

    When outdoor brightness is high and indoor brightness is also reasonable,
    artificial lighting should be reduced. When outdoor is dark, full
    artificial lighting is needed.

    Args:
        outdoor_lux: Current outdoor illuminance in lux.
        indoor_lux: Current indoor illuminance in lux.
        min_brightness_pct: Floor brightness percentage.
        max_brightness_pct: Ceiling brightness percentage.
        bright_threshold: Outdoor lux above which natural light is abundant.
        dark_threshold: Outdoor lux below which it is considered dark.

    Returns:
        Target brightness percentage.
    """
    if outdoor_lux <= 0:
        return max_brightness_pct

    # Natural light factor: how much of the indoor illumination comes from outside
    # A ratio close to or above 1 means natural light is plentiful
    natural_ratio = indoor_lux / max(outdoor_lux, 1.0)

    if outdoor_lux >= bright_threshold and natural_ratio > 0.3:
        # Lots of natural light reaching indoors -- minimal artificial light
        return min_brightness_pct

    if outdoor_lux <= dark_threshold:
        # Dark outside -- full artificial light needed
        return max_brightness_pct

    # Interpolate between dark and bright thresholds on a log scale
    # log range: dark_threshold .. bright_threshold
    log_range = math.log(max(bright_threshold, 1)) - math.log(max(dark_threshold, 1))
    if log_range <= 0:
        return max_brightness_pct

    log_outdoor = math.log(max(outdoor_lux, 1))
    log_dark = math.log(max(dark_threshold, 1))
    t = min(1.0, max(0.0, (log_outdoor - log_dark) / log_range))

    # As outdoor gets brighter, reduce artificial light
    pct_range = max_brightness_pct - min_brightness_pct
    target = max_brightness_pct - int(t * pct_range)
    return max(min_brightness_pct, min(max_brightness_pct, target))


# ---- Service Class -------------------------------------------------------


class LightModuleService:
    """Adaptive Light Module service.

    Manages zone light profiles, computes ideal settings, and persists state.
    """

    def __init__(self, data_dir: str | None = None) -> None:
        self._lock = threading.Lock()

        # Persistence
        if data_dir is not None:
            self._data_dir = Path(data_dir)
        else:
            self._data_dir = _DATA_DIR
        self._profiles_file = self._data_dir / "light_module.json"

        # Zone profiles: zone_id -> ZoneLightProfile
        self._profiles: dict[str, ZoneLightProfile] = {}

        # Runtime state: zone_id -> ZoneLightState
        self._states: dict[str, ZoneLightState] = {}

        # Global config
        self._global_config: dict[str, Any] = dict(_DEFAULT_GLOBAL_CONFIG)

        # Load persisted profiles
        self._load()
        logger.info(
            "LightModuleService initialized (%d zone profiles loaded)",
            len(self._profiles),
        )

    # ---- Persistence -------------------------------------------------------

    def _load(self) -> None:
        """Load profiles and global config from disk."""
        try:
            if self._profiles_file.exists():
                with open(self._profiles_file, "r", encoding="utf-8") as fh:
                    data = json.load(fh)

                # Load global config
                if "global_config" in data:
                    self._global_config.update(data["global_config"])

                # Load zone profiles
                for zp_data in data.get("profiles", []):
                    try:
                        profile = ZoneLightProfile.from_dict(zp_data)
                        self._profiles[profile.zone_id] = profile
                        # Initialize runtime state
                        self._states[profile.zone_id] = ZoneLightState(
                            zone_id=profile.zone_id,
                            mode=profile.mode,
                        )
                    except Exception:
                        logger.exception("Failed to load zone profile: %s", zp_data)

                logger.info(
                    "Loaded %d light module profiles from %s",
                    len(self._profiles),
                    self._profiles_file,
                )
        except FileNotFoundError:
            logger.debug("No light module data file at %s", self._profiles_file)
        except Exception:
            logger.exception("Failed to load light module data from %s", self._profiles_file)

    def _save(self) -> None:
        """Persist profiles and global config to disk."""
        try:
            self._data_dir.mkdir(parents=True, exist_ok=True)
            data = {
                "global_config": self._global_config,
                "profiles": [p.to_dict() for p in self._profiles.values()],
                "saved_at": time.time(),
            }
            with open(self._profiles_file, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, ensure_ascii=False)
        except Exception:
            logger.exception("Failed to save light module data to %s", self._profiles_file)

    # ---- Global Config -----------------------------------------------------

    def get_global_config(self) -> dict[str, Any]:
        """Return current global configuration."""
        return dict(self._global_config)

    def update_global_config(self, updates: dict[str, Any]) -> dict[str, Any]:
        """Update global configuration (partial update)."""
        with self._lock:
            for key, value in updates.items():
                if key in _DEFAULT_GLOBAL_CONFIG:
                    self._global_config[key] = value
            self._save()
        return self.get_global_config()

    # ---- Zone Profile Management -------------------------------------------

    def get_zone_profiles(self) -> list[dict[str, Any]]:
        """Return all zone light profiles."""
        return [p.to_dict() for p in self._profiles.values()]

    def get_zone_profile(self, zone_id: str) -> dict[str, Any] | None:
        """Return a single zone profile or None."""
        p = self._profiles.get(zone_id)
        return p.to_dict() if p else None

    def upsert_zone_profile(self, zone_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """Create or update a zone light profile.

        Args:
            zone_id: The zone identifier (e.g. "zone:wohnbereich").
            data: Profile fields to set/update. Unknown keys are ignored.

        Returns:
            The updated profile as dict.
        """
        with self._lock:
            existing = self._profiles.get(zone_id)
            if existing:
                # Partial update
                known = {f.name for f in ZoneLightProfile.__dataclass_fields__.values()}
                for key, value in data.items():
                    if key in known and key != "zone_id":
                        setattr(existing, key, value)
                profile = existing
            else:
                # Create new
                data["zone_id"] = zone_id
                profile = ZoneLightProfile.from_dict(data)
                self._profiles[zone_id] = profile

            # Ensure runtime state exists
            if zone_id not in self._states:
                self._states[zone_id] = ZoneLightState(
                    zone_id=zone_id,
                    mode=profile.mode,
                )

            self._save()
        return profile.to_dict()

    def delete_zone_profile(self, zone_id: str) -> bool:
        """Delete a zone profile. Returns True if it existed."""
        with self._lock:
            existed = zone_id in self._profiles
            self._profiles.pop(zone_id, None)
            self._states.pop(zone_id, None)
            if existed:
                self._save()
        return existed

    # ---- Runtime State Updates ---------------------------------------------

    def update_presence(self, zone_id: str, detected: bool) -> None:
        """Update motion/presence state for a zone."""
        state = self._states.get(zone_id)
        if state is None:
            state = ZoneLightState(zone_id=zone_id)
            self._states[zone_id] = state

        state.presence_detected = detected
        if detected:
            state.last_motion_ts = time.time()

    def update_brightness(
        self,
        zone_id: str,
        indoor_lux: float | None = None,
        outdoor_lux: float | None = None,
    ) -> None:
        """Update brightness sensor readings for a zone."""
        state = self._states.get(zone_id)
        if state is None:
            state = ZoneLightState(zone_id=zone_id)
            self._states[zone_id] = state

        if indoor_lux is not None:
            state.indoor_lux = indoor_lux
        if outdoor_lux is not None:
            state.outdoor_lux = outdoor_lux

    # ---- Evaluation --------------------------------------------------------

    def evaluate(
        self,
        zone_id: str,
        now: datetime | None = None,
    ) -> LightEvaluation:
        """Evaluate and compute ideal light settings for a zone.

        Combines three factors:
        1. Presence check (is someone in the zone?)
        2. Brightness ratio (outdoor vs indoor lux)
        3. Circadian curve (time-of-day color temperature)

        Args:
            zone_id: Zone to evaluate.
            now: Override current time (for testing). Defaults to UTC now.

        Returns:
            LightEvaluation with computed brightness_pct, color_temp_k,
            should_be_on, and reason.
        """
        if now is None:
            now = datetime.now(tz=timezone.utc)

        hour = now.hour + now.minute / 60.0

        profile = self._profiles.get(zone_id)
        state = self._states.get(zone_id)

        # No profile configured for this zone
        if profile is None:
            return LightEvaluation(
                brightness_pct=0,
                color_temp_k=4000,
                should_be_on=False,
                reason="no_profile",
            )

        # Profile disabled
        if not profile.enabled:
            return LightEvaluation(
                brightness_pct=0,
                color_temp_k=4000,
                should_be_on=False,
                reason="profile_disabled",
            )

        # Global module disabled
        if not self._global_config.get("enabled", True):
            return LightEvaluation(
                brightness_pct=0,
                color_temp_k=4000,
                should_be_on=False,
                reason="module_disabled",
            )

        # Manual mode: do nothing (user controls lights)
        if profile.mode == "manual":
            return LightEvaluation(
                brightness_pct=0,
                color_temp_k=4000,
                should_be_on=False,
                reason="manual_mode",
            )

        # Initialize state if missing
        if state is None:
            state = ZoneLightState(zone_id=zone_id, mode=profile.mode)
            self._states[zone_id] = state

        # ---- Step 1: Presence check ----
        presence_active = self._is_presence_active(zone_id)

        if profile.mode == "presence_only" or (
            profile.mode == "auto"
            and self._global_config.get("presence_enabled", True)
        ):
            if not presence_active:
                return LightEvaluation(
                    brightness_pct=0,
                    color_temp_k=circadian_color_temp(
                        hour, profile.color_temp_min_k, profile.color_temp_max_k
                    ),
                    should_be_on=False,
                    reason="no_presence",
                )

        # ---- Step 2: Circadian color temperature ----
        color_temp_k = circadian_color_temp(
            hour, profile.color_temp_min_k, profile.color_temp_max_k
        )

        # ---- Step 3: Brightness computation ----
        if profile.mode == "circadian":
            # Pure circadian mode: brightness follows time-of-day curve only
            circ_factor = circadian_brightness_factor(hour)
            pct_range = profile.max_brightness_pct - profile.min_brightness_pct
            brightness_pct = profile.min_brightness_pct + int(circ_factor * pct_range)
            reason = "circadian"
        elif self._global_config.get("brightness_ratio_enabled", True):
            # Auto mode with brightness ratio
            outdoor_lux = state.outdoor_lux
            indoor_lux = state.indoor_lux

            # Get base brightness from ratio
            base_brightness = brightness_ratio_adjustment(
                outdoor_lux=outdoor_lux,
                indoor_lux=indoor_lux,
                min_brightness_pct=profile.min_brightness_pct,
                max_brightness_pct=profile.max_brightness_pct,
                bright_threshold=self._global_config.get("outdoor_lux_bright_threshold", 10000.0),
                dark_threshold=self._global_config.get("outdoor_lux_dark_threshold", 100.0),
            )

            # Apply circadian factor to modulate brightness
            circ_factor = circadian_brightness_factor(hour)
            brightness_pct = max(
                profile.min_brightness_pct,
                min(profile.max_brightness_pct, int(base_brightness * circ_factor)),
            )

            if outdoor_lux >= self._global_config.get("outdoor_lux_bright_threshold", 10000.0):
                reason = "bright_outdoor"
            elif outdoor_lux <= self._global_config.get("outdoor_lux_dark_threshold", 100.0):
                reason = "dark_outdoor"
            else:
                reason = "brightness_ratio"
        else:
            # Fallback: pure circadian
            circ_factor = circadian_brightness_factor(hour)
            pct_range = profile.max_brightness_pct - profile.min_brightness_pct
            brightness_pct = profile.min_brightness_pct + int(circ_factor * pct_range)
            reason = "circadian_fallback"

        should_be_on = brightness_pct > 0

        # Update runtime state
        state.brightness_pct = brightness_pct
        state.color_temp_k = color_temp_k
        state.should_be_on = should_be_on
        state.reason = reason
        state.mode = profile.mode

        return LightEvaluation(
            brightness_pct=brightness_pct,
            color_temp_k=color_temp_k,
            should_be_on=should_be_on,
            reason=reason,
        )

    def _is_presence_active(self, zone_id: str) -> bool:
        """Check if presence is active for a zone, including timeout grace period."""
        state = self._states.get(zone_id)
        if state is None:
            return False

        if state.presence_detected:
            return True

        # Check timeout grace period
        if state.last_motion_ts <= 0:
            return False

        profile = self._profiles.get(zone_id)
        timeout = (
            profile.presence_timeout_s
            if profile
            else self._global_config.get("default_presence_timeout_s", 300)
        )

        elapsed = time.time() - state.last_motion_ts
        return elapsed <= timeout

    # ---- Status Aggregation ------------------------------------------------

    def get_zone_status(self, zone_id: str) -> dict[str, Any] | None:
        """Get current light state for a single zone."""
        state = self._states.get(zone_id)
        if state is None:
            return None
        return state.to_dict()

    def get_all_status(self) -> list[dict[str, Any]]:
        """Get current light state for all zones."""
        return [s.to_dict() for s in self._states.values()]

    def evaluate_all(self, now: datetime | None = None) -> list[dict[str, Any]]:
        """Evaluate all configured zones and return results."""
        results = []
        for zone_id in self._profiles:
            evaluation = self.evaluate(zone_id, now=now)
            results.append({
                "zone_id": zone_id,
                **evaluation.to_dict(),
            })
        return results

    # ---- Brightness Threshold Configuration --------------------------------

    def set_brightness_threshold(
        self,
        zone_id: str,
        min_brightness_pct: int | None = None,
        max_brightness_pct: int | None = None,
        outdoor_lux_bright_threshold: float | None = None,
        outdoor_lux_dark_threshold: float | None = None,
    ) -> dict[str, Any]:
        """Set the brightness threshold parameters for a zone.

        This controls when automatic lighting kicks in based on the ratio
        of outdoor to indoor illumination.

        Parameters
        ----------
        zone_id : str
            Zone to configure.
        min_brightness_pct : int, optional
            Minimum brightness when lights are on (slider: 1-100).
        max_brightness_pct : int, optional
            Maximum brightness (slider: 1-100).
        outdoor_lux_bright_threshold : float, optional
            Lux above which natural light is abundant (slider: 1000-50000).
        outdoor_lux_dark_threshold : float, optional
            Lux below which it's dark (slider: 10-1000).
        """
        updates: dict[str, Any] = {}

        if min_brightness_pct is not None:
            updates["min_brightness_pct"] = max(1, min(100, int(min_brightness_pct)))
        if max_brightness_pct is not None:
            updates["max_brightness_pct"] = max(1, min(100, int(max_brightness_pct)))
        if outdoor_lux_bright_threshold is not None:
            self._global_config["outdoor_lux_bright_threshold"] = max(
                100, min(100000, float(outdoor_lux_bright_threshold))
            )
        if outdoor_lux_dark_threshold is not None:
            self._global_config["outdoor_lux_dark_threshold"] = max(
                1, min(10000, float(outdoor_lux_dark_threshold))
            )

        if updates:
            self.upsert_zone_profile(zone_id, updates)

        if outdoor_lux_bright_threshold is not None or outdoor_lux_dark_threshold is not None:
            with self._lock:
                self._save()

        return {
            "ok": True,
            "zone_id": zone_id,
            "profile": self.get_zone_profile(zone_id),
            "global_thresholds": {
                "outdoor_lux_bright_threshold": self._global_config.get("outdoor_lux_bright_threshold", 10000),
                "outdoor_lux_dark_threshold": self._global_config.get("outdoor_lux_dark_threshold", 100),
            },
        }

    def get_brightness_info(self, zone_id: str) -> dict[str, Any]:
        """Get comprehensive brightness information for a zone.

        Returns current indoor/outdoor lux, computed ratio, and whether
        artificial light is needed at the current illumination levels.
        """
        profile = self._profiles.get(zone_id)
        state = self._states.get(zone_id)

        if profile is None:
            return {"ok": False, "error": f"No profile for zone {zone_id}"}

        outdoor = state.outdoor_lux if state else 0.0
        indoor = state.indoor_lux if state else 0.0

        bright_thresh = self._global_config.get("outdoor_lux_bright_threshold", 10000)
        dark_thresh = self._global_config.get("outdoor_lux_dark_threshold", 100)

        # Compute the target brightness at current conditions
        target_brightness = brightness_ratio_adjustment(
            outdoor_lux=outdoor,
            indoor_lux=indoor,
            min_brightness_pct=profile.min_brightness_pct,
            max_brightness_pct=profile.max_brightness_pct,
            bright_threshold=bright_thresh,
            dark_threshold=dark_thresh,
        )

        ratio = indoor / max(outdoor, 1.0) if outdoor > 0 else 0.0

        return {
            "ok": True,
            "zone_id": zone_id,
            "indoor_lux": indoor,
            "outdoor_lux": outdoor,
            "brightness_ratio": round(ratio, 4),
            "target_brightness_pct": target_brightness,
            "natural_light_sufficient": outdoor >= bright_thresh and ratio > 0.3,
            "config": {
                "min_brightness_pct": profile.min_brightness_pct,
                "max_brightness_pct": profile.max_brightness_pct,
                "outdoor_lux_bright_threshold": bright_thresh,
                "outdoor_lux_dark_threshold": dark_thresh,
            },
        }

    # ---- Light Presets (time/color) ----------------------------------------

    def get_time_color_presets(self) -> dict[str, Any]:
        """Return the circadian time/color presets configuration."""
        return {
            "ok": True,
            "circadian_enabled": self._global_config.get("circadian_enabled", True),
            "default_color_temp_min_k": self._global_config.get("default_color_temp_min_k", 2200),
            "default_color_temp_max_k": self._global_config.get("default_color_temp_max_k", 5500),
            "presets": {
                "warm_night": {"color_temp_k": 2200, "brightness_pct": 15, "label": "Warmes Nachtlicht"},
                "evening": {"color_temp_k": 2700, "brightness_pct": 60, "label": "Gemütlicher Abend"},
                "day": {"color_temp_k": 4500, "brightness_pct": 100, "label": "Tageslicht"},
                "focus": {"color_temp_k": 5500, "brightness_pct": 100, "label": "Konzentration"},
                "movie": {"color_temp_k": 2400, "brightness_pct": 10, "label": "Filmmodus"},
                "relax": {"color_temp_k": 3000, "brightness_pct": 40, "label": "Entspannung"},
            },
        }

    def apply_preset_to_zone(
        self,
        zone_id: str,
        preset_name: str,
    ) -> dict[str, Any]:
        """Apply a named light preset to a zone.

        Parameters
        ----------
        zone_id : str
            The zone to apply the preset to.
        preset_name : str
            One of: warm_night, evening, day, focus, movie, relax.
        """
        presets = self.get_time_color_presets()["presets"]
        preset = presets.get(preset_name)
        if preset is None:
            return {"ok": False, "error": f"Unknown preset '{preset_name}'"}

        profile = self._profiles.get(zone_id)
        if profile is None:
            return {"ok": False, "error": f"No profile for zone {zone_id}"}

        # Update state to reflect preset
        state = self._states.get(zone_id)
        if state is not None:
            state.brightness_pct = preset["color_temp_k"]  # Will be overridden
            state.color_temp_k = preset["color_temp_k"]
            state.should_be_on = True
            state.reason = f"preset:{preset_name}"

        return {
            "ok": True,
            "zone_id": zone_id,
            "preset": preset_name,
            "brightness_pct": preset["brightness_pct"],
            "color_temp_k": preset["color_temp_k"],
            "label": preset["label"],
        }
