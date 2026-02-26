"""Zone Automation Controller -- Orchestrates presence, light, brightness, and
media automation per Habitus zone.

The controller is the central coordination point that ties together:
    - PresenceEngine (multi-sensor Bayesian presence detection)
    - BrightnessManager (indoor/outdoor lux tracking and light-need calculation)
    - LightModuleService (adaptive circadian/brightness-ratio light control)
    - MusicCloudService (zone-following media playback)
    - EventBus (inter-module communication)

Per-zone automation configs are persisted to /data/zone_automation.json.

Thread-safety: all mutable state is protected by ``_lock``.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from copilot_core.zone_automation.presence_engine import (
    PresenceEngine,
    SensorConfig,
    ZonePresenceState,
)
from copilot_core.zone_automation.brightness_manager import (
    BrightnessManager,
    ZoneBrightnessState,
)

_LOGGER = logging.getLogger(__name__)

# Persistence path (HA add-on volume mount)
_DATA_DIR = Path(os.environ.get("ZONE_AUTOMATION_DATA_DIR", "/data"))
_CONFIG_FILE = _DATA_DIR / "zone_automation.json"


# ---- Data Models -----------------------------------------------------------


@dataclass
class ZoneAutomationConfig:
    """Automation configuration for a single Habitus zone."""

    zone_id: str
    enabled: bool = True

    # Presence
    presence_sensors: list[str] = field(default_factory=list)
    presence_timeout_s: int = 300
    presence_mode: str = "any"  # any, all, bayesian

    # Light
    light_entities: list[str] = field(default_factory=list)
    light_mode: str = "auto"  # auto, manual, circadian, presence_only
    min_brightness_pct: int = 10
    max_brightness_pct: int = 100
    color_temp_min_k: int = 2200
    color_temp_max_k: int = 5500

    # Brightness
    indoor_brightness_sensors: list[str] = field(default_factory=list)
    outdoor_brightness_sensor: str = ""
    target_lux: float = 300.0

    # Mood
    mood_scene_override: str = ""  # scene_id to force, empty = auto

    # Media
    media_players: list[str] = field(default_factory=list)
    media_follow_presence: bool = True

    # Tags (auto-generated from entity domains)
    auto_tags: dict[str, list[str]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ZoneAutomationConfig:
        """Create a config from a dict, ignoring unknown keys."""
        known = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {}
        for k, v in data.items():
            if k in known:
                filtered[k] = v
        return cls(**filtered)


@dataclass
class ZoneEvaluation:
    """Result of evaluating a zone's automation state."""

    zone_id: str
    timestamp: float = 0.0
    enabled: bool = True

    # Presence
    presence_state: str = "vacant"  # occupied, vacant, grace_period
    presence_confidence: float = 0.0
    active_sensors: list[str] = field(default_factory=list)

    # Light
    light_action: str = "none"  # turn_on, turn_off, adjust, none
    light_brightness_pct: int = 0
    light_color_temp_k: int = 4000
    light_reason: str = ""
    light_entities: list[str] = field(default_factory=list)

    # Brightness
    indoor_lux: float = 0.0
    outdoor_lux: float = 0.0
    brightness_ratio: float = 0.0
    artificial_light_needed: bool = False
    deficit_lux: float = 0.0

    # Media
    media_action: str = "none"  # follow, unfollow, none
    media_players: list[str] = field(default_factory=list)

    # Heating/Climate
    heating_action: str = "none"  # set_temp, none
    heating_target_temp_c: float = 0.0
    climate_entities: list[str] = field(default_factory=list)

    # Mood
    mood_override: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ZoneStatus:
    """Current runtime status for a zone."""

    zone_id: str
    enabled: bool = True
    config_present: bool = False
    presence: dict[str, Any] = field(default_factory=dict)
    brightness: dict[str, Any] = field(default_factory=dict)
    last_evaluation: dict[str, Any] = field(default_factory=dict)
    last_sensor_update_ts: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---- Sensor type inference -------------------------------------------------


_SENSOR_TYPE_MAP: dict[str, str] = {
    "binary_sensor": "motion",
    "sensor": "presence",
    "device_tracker": "device_tracker",
    "media_player": "media_activity",
}


def _infer_sensor_type(entity_id: str) -> str:
    """Infer the sensor type from the entity ID domain."""
    domain = entity_id.split(".")[0] if "." in entity_id else ""
    return _SENSOR_TYPE_MAP.get(domain, "motion")


def _infer_entity_role(entity_id: str) -> str:
    """Infer an auto-tag role from the entity ID domain."""
    domain = entity_id.split(".")[0] if "." in entity_id else ""
    role_map = {
        "light": "light",
        "binary_sensor": "presence_sensor",
        "sensor": "brightness_sensor",
        "media_player": "media_player",
        "device_tracker": "device_tracker",
        "switch": "switch",
        "climate": "climate",
        "cover": "cover",
    }
    return role_map.get(domain, "unknown")


# ---- Controller ------------------------------------------------------------


class ZoneAutomationController:
    """Central controller for per-zone automation.

    Coordinates PresenceEngine, BrightnessManager, and external services
    (LightModuleService, MusicCloudService) to provide unified zone-level
    automation.

    Parameters
    ----------
    event_bus : EventBus, optional
        EventBus instance for inter-module communication.
    light_module_service : LightModuleService, optional
        Adaptive light service for circadian/brightness-ratio control.
    music_cloud_service : MusicCloudService, optional
        Zone-following media playback service.
    data_dir : str, optional
        Override the persistence directory (default: /data).
    """

    def __init__(
        self,
        event_bus: Any = None,
        light_module_service: Any = None,
        music_cloud_service: Any = None,
        override_modes_service: Any = None,
        data_dir: str | None = None,
    ) -> None:
        self._lock = threading.Lock()
        self._event_bus = event_bus
        self._light_module = light_module_service
        self._music_cloud = music_cloud_service
        self._override_modes = override_modes_service

        # Persistence
        if data_dir is not None:
            self._data_dir = Path(data_dir)
        else:
            self._data_dir = _DATA_DIR
        self._config_file = self._data_dir / "zone_automation.json"

        # Sub-engines
        self._presence_engine = PresenceEngine()
        self._brightness_manager = BrightnessManager()

        # Zone configs: zone_id -> ZoneAutomationConfig
        self._configs: dict[str, ZoneAutomationConfig] = {}

        # Runtime tracking
        self._last_evaluations: dict[str, ZoneEvaluation] = {}
        self._last_sensor_update: dict[str, float] = {}

        # Load persisted configs
        self._load()

        _LOGGER.info(
            "ZoneAutomationController initialized (%d zone configs loaded)",
            len(self._configs),
        )

    # ---- Persistence -------------------------------------------------------

    def _load(self) -> None:
        """Load zone automation configs from disk."""
        try:
            if self._config_file.exists():
                with open(self._config_file, "r", encoding="utf-8") as fh:
                    data = json.load(fh)

                for cfg_data in data.get("configs", []):
                    try:
                        config = ZoneAutomationConfig.from_dict(cfg_data)
                        self._configs[config.zone_id] = config
                        self._apply_config_to_engines(config)
                    except Exception:
                        _LOGGER.exception(
                            "Failed to load zone automation config: %s", cfg_data
                        )

                _LOGGER.info(
                    "Loaded %d zone automation configs from %s",
                    len(self._configs),
                    self._config_file,
                )
        except FileNotFoundError:
            _LOGGER.debug("No zone automation config at %s", self._config_file)
        except Exception:
            _LOGGER.exception(
                "Failed to load zone automation configs from %s", self._config_file
            )

    def _save(self) -> None:
        """Persist all zone automation configs to disk."""
        try:
            self._data_dir.mkdir(parents=True, exist_ok=True)
            data = {
                "configs": [c.to_dict() for c in self._configs.values()],
                "saved_at": time.time(),
                "version": "1.0.0",
            }
            with open(self._config_file, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, ensure_ascii=False)
        except Exception:
            _LOGGER.exception(
                "Failed to save zone automation configs to %s", self._config_file
            )

    # ---- Config management -------------------------------------------------

    def _apply_config_to_engines(self, config: ZoneAutomationConfig) -> None:
        """Propagate a zone config to the sub-engines."""
        zone_id = config.zone_id

        # Register presence sensors
        for sid in config.presence_sensors:
            sensor_type = _infer_sensor_type(sid)
            self._presence_engine.register_sensor(
                zone_id,
                SensorConfig(
                    entity_id=sid,
                    sensor_type=sensor_type,
                    decay_s=config.presence_timeout_s,
                ),
            )
        self._presence_engine.set_zone_timeout(zone_id, config.presence_timeout_s)

        # Configure brightness manager
        self._brightness_manager.configure_zone(
            zone_id,
            target_lux=config.target_lux,
            indoor_sensors=config.indoor_brightness_sensors or None,
            outdoor_sensor=config.outdoor_brightness_sensor,
        )

        # Forward to light module service if available
        if self._light_module is not None:
            try:
                self._light_module.upsert_zone_profile(
                    zone_id,
                    {
                        "enabled": config.enabled,
                        "lights": config.light_entities,
                        "min_brightness_pct": config.min_brightness_pct,
                        "max_brightness_pct": config.max_brightness_pct,
                        "color_temp_min_k": config.color_temp_min_k,
                        "color_temp_max_k": config.color_temp_max_k,
                        "presence_timeout_s": config.presence_timeout_s,
                        "mode": config.light_mode,
                        "outdoor_brightness_sensor": config.outdoor_brightness_sensor,
                    },
                )
            except Exception:
                _LOGGER.debug("Failed to sync config to LightModuleService for %s", zone_id)

    def update_zone_config(
        self, zone_id: str, config_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Create or update a zone automation config.

        Parameters
        ----------
        zone_id : str
            The zone identifier.
        config_data : dict
            Partial or full config fields.  Unknown keys are ignored.

        Returns
        -------
        dict
            The updated config as a dict.
        """
        with self._lock:
            existing = self._configs.get(zone_id)
            if existing:
                # Partial update
                known = {f.name for f in ZoneAutomationConfig.__dataclass_fields__.values()}
                for key, value in config_data.items():
                    if key in known and key != "zone_id":
                        setattr(existing, key, value)
                config = existing
            else:
                config_data["zone_id"] = zone_id
                config = ZoneAutomationConfig.from_dict(config_data)
                self._configs[zone_id] = config

            # Auto-generate tags from entity domains
            config.auto_tags = self._generate_auto_tags(config)

            # Apply to sub-engines
            self._apply_config_to_engines(config)

            self._save()

        self._publish_event("zone_automation.config_updated", {
            "zone_id": zone_id,
            "enabled": config.enabled,
        })

        return config.to_dict()

    def delete_zone_config(self, zone_id: str) -> bool:
        """Delete a zone automation config.  Returns True if it existed."""
        with self._lock:
            existed = zone_id in self._configs
            self._configs.pop(zone_id, None)
            self._last_evaluations.pop(zone_id, None)
            self._last_sensor_update.pop(zone_id, None)

            if existed:
                self._presence_engine.clear_zone(zone_id)
                self._brightness_manager.remove_zone(zone_id)
                self._save()

        if existed:
            self._publish_event("zone_automation.config_deleted", {
                "zone_id": zone_id,
            })

        return existed

    def get_zone_config(self, zone_id: str) -> dict[str, Any] | None:
        """Return a single zone config or None."""
        with self._lock:
            config = self._configs.get(zone_id)
            return config.to_dict() if config else None

    def get_all_configs(self) -> list[dict[str, Any]]:
        """Return all zone configs."""
        with self._lock:
            return [c.to_dict() for c in self._configs.values()]

    # ---- Auto-tagging ------------------------------------------------------

    def _generate_auto_tags(self, config: ZoneAutomationConfig) -> dict[str, list[str]]:
        """Auto-generate role tags from the entity IDs in a config."""
        tags: dict[str, list[str]] = {}
        all_entities = (
            config.presence_sensors
            + config.light_entities
            + config.indoor_brightness_sensors
            + config.media_players
        )
        if config.outdoor_brightness_sensor:
            all_entities.append(config.outdoor_brightness_sensor)

        for entity_id in all_entities:
            role = _infer_entity_role(entity_id)
            if role not in tags:
                tags[role] = []
            if entity_id not in tags[role]:
                tags[role].append(entity_id)

        return tags

    # ---- Sensor updates from HA --------------------------------------------

    def process_sensor_update(
        self,
        entity_id: str,
        new_state: str,
        attributes: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Process a sensor state update pushed from HA.

        Routes the update to the appropriate sub-engine based on entity domain
        and zone configuration.

        Parameters
        ----------
        entity_id : str
            The HA entity that changed.
        new_state : str
            The new state value (e.g. "on", "off", "23.5", "home").
        attributes : dict, optional
            Entity attributes (unit_of_measurement, device_class, etc.).

        Returns
        -------
        list[dict]
            List of zone evaluations triggered by this update.
        """
        attributes = attributes or {}
        domain = entity_id.split(".")[0] if "." in entity_id else ""
        now = time.time()

        affected_zones: list[str] = []

        with self._lock:
            configs_snapshot = dict(self._configs)

        # Find all zones that reference this entity
        for zone_id, config in configs_snapshot.items():
            if not config.enabled:
                continue

            # Check presence sensors
            if entity_id in config.presence_sensors:
                active = self._state_is_active(new_state, domain)
                sensor_type = _infer_sensor_type(entity_id)
                self._presence_engine.update_sensor(
                    zone_id, entity_id, active, sensor_type
                )
                self._last_sensor_update[zone_id] = now

                # Publish presence change event
                presence_state = self._presence_engine.evaluate_presence(zone_id)
                self._publish_event("zone_automation.presence_changed", {
                    "zone_id": zone_id,
                    "entity_id": entity_id,
                    "occupied": presence_state.occupied,
                    "state": presence_state.state,
                    "confidence": presence_state.confidence,
                })

                if zone_id not in affected_zones:
                    affected_zones.append(zone_id)

            # Check indoor brightness sensors
            if entity_id in config.indoor_brightness_sensors:
                try:
                    lux = float(new_state)
                    self._brightness_manager.update_indoor(zone_id, entity_id, lux)
                    self._last_sensor_update[zone_id] = now
                    if zone_id not in affected_zones:
                        affected_zones.append(zone_id)
                except (ValueError, TypeError):
                    pass

            # Check outdoor brightness sensor
            if entity_id == config.outdoor_brightness_sensor:
                try:
                    lux = float(new_state)
                    self._brightness_manager.update_outdoor(entity_id, lux)
                    self._last_sensor_update[zone_id] = now
                    if zone_id not in affected_zones:
                        affected_zones.append(zone_id)
                except (ValueError, TypeError):
                    pass

            # Check media players
            if entity_id in config.media_players:
                # Media player state change can imply presence
                is_playing = new_state in ("playing", "paused", "on")
                if is_playing:
                    self._presence_engine.update_sensor(
                        zone_id, entity_id, True, "media_activity"
                    )
                else:
                    self._presence_engine.update_sensor(
                        zone_id, entity_id, False, "media_activity"
                    )
                self._last_sensor_update[zone_id] = now
                if zone_id not in affected_zones:
                    affected_zones.append(zone_id)

        # Evaluate affected zones
        results: list[dict[str, Any]] = []
        for zone_id in affected_zones:
            evaluation = self.evaluate_zone(zone_id)
            results.append(evaluation.to_dict())

        return results

    def _state_is_active(self, state: str, domain: str) -> bool:
        """Determine if a state value represents "active" / "present"."""
        state_lower = state.lower().strip()
        if domain in ("binary_sensor",):
            return state_lower in ("on", "true", "1", "detected")
        if domain == "device_tracker":
            return state_lower in ("home", "on")
        if domain == "media_player":
            return state_lower in ("playing", "paused", "on")
        # Generic sensor -- non-zero numeric is active
        try:
            return float(state) > 0
        except (ValueError, TypeError):
            return state_lower in ("on", "true", "1", "home", "detected", "active")

    # ---- Zone evaluation ---------------------------------------------------

    def evaluate_zone(self, zone_id: str) -> ZoneEvaluation:
        """Evaluate a single zone and determine automation actions.

        Combines presence, brightness, and mood data to decide:
        - Should lights be on/off/adjusted?
        - Should media follow presence?

        Returns
        -------
        ZoneEvaluation
            The computed evaluation with recommended actions.
        """
        now = time.time()

        with self._lock:
            config = self._configs.get(zone_id)

        if config is None:
            return ZoneEvaluation(
                zone_id=zone_id,
                timestamp=now,
                enabled=False,
                light_reason="no_config",
            )

        if not config.enabled:
            return ZoneEvaluation(
                zone_id=zone_id,
                timestamp=now,
                enabled=False,
                light_reason="disabled",
            )

        # ---- Step 1: Presence evaluation ----
        presence = self._presence_engine.evaluate_presence(zone_id)

        # ---- Step 2: Brightness evaluation ----
        brightness = self._brightness_manager.evaluate(zone_id)

        # ---- Step 3: Light decision ----
        light_action, light_brightness, light_color_k, light_reason = (
            self._compute_light_action(config, presence, brightness, now)
        )

        # ---- Step 4: Media decision ----
        media_action = self._compute_media_action(config, presence)

        # ---- Step 5: Heating/Climate decision ----
        heating_action, heating_target = self._compute_heating_action(config)

        # Collect climate entities from auto_tags
        climate_entities = config.auto_tags.get("climate", [])

        # Build evaluation
        evaluation = ZoneEvaluation(
            zone_id=zone_id,
            timestamp=now,
            enabled=True,
            # Presence
            presence_state=presence.state,
            presence_confidence=presence.confidence,
            active_sensors=list(presence.active_sensors),
            # Light
            light_action=light_action,
            light_brightness_pct=light_brightness,
            light_color_temp_k=light_color_k,
            light_reason=light_reason,
            light_entities=list(config.light_entities),
            # Brightness
            indoor_lux=brightness.indoor_avg_lux,
            outdoor_lux=brightness.outdoor_lux,
            brightness_ratio=brightness.brightness_ratio,
            artificial_light_needed=brightness.artificial_light_needed,
            deficit_lux=brightness.deficit_lux,
            # Media
            media_action=media_action,
            media_players=list(config.media_players),
            # Heating
            heating_action=heating_action,
            heating_target_temp_c=heating_target,
            climate_entities=climate_entities,
            # Mood
            mood_override=config.mood_scene_override,
        )

        with self._lock:
            self._last_evaluations[zone_id] = evaluation

        return evaluation

    def evaluate_all_zones(self) -> list[ZoneEvaluation]:
        """Evaluate all configured zones.

        Returns
        -------
        list[ZoneEvaluation]
            Evaluations for all zones.
        """
        with self._lock:
            zone_ids = list(self._configs.keys())

        evaluations: list[ZoneEvaluation] = []
        for zone_id in zone_ids:
            evaluations.append(self.evaluate_zone(zone_id))
        return evaluations

    def _get_zone_consequences(self, zone_id: str) -> dict[str, Any]:
        """Get merged override mode consequences for a zone."""
        if self._override_modes is None:
            return {}
        try:
            return self._override_modes.get_effective_consequences(zone_id)
        except Exception:
            return {}

    def _compute_light_action(
        self,
        config: ZoneAutomationConfig,
        presence: ZonePresenceState,
        brightness: ZoneBrightnessState,
        now: float,
    ) -> tuple[str, int, int, str]:
        """Compute the light action for a zone.

        Returns (action, brightness_pct, color_temp_k, reason).
        """
        # Check override modes
        consequences = self._get_zone_consequences(config.zone_id)
        if consequences:
            if not consequences.get("light_allowed", True):
                return ("none", 0, 4000, "light_suppressed_by_override")
            cons = consequences.get("consequences", {})
            if cons.get("light_manual_override"):
                return ("none", 0, 4000, "manual_override_mode")

        # If we have a LightModuleService, delegate the full evaluation
        if self._light_module is not None:
            try:
                # Sync presence state
                self._light_module.update_presence(config.zone_id, presence.occupied)
                # Sync brightness readings
                self._light_module.update_brightness(
                    config.zone_id,
                    indoor_lux=brightness.indoor_avg_lux,
                    outdoor_lux=brightness.outdoor_lux,
                )
                # Evaluate via the module
                light_eval = self._light_module.evaluate(config.zone_id)
                if light_eval.should_be_on:
                    action = "turn_on" if not presence.occupied else "adjust"
                    return (
                        action,
                        light_eval.brightness_pct,
                        light_eval.color_temp_k,
                        light_eval.reason,
                    )
                else:
                    return ("turn_off", 0, light_eval.color_temp_k, light_eval.reason)
            except Exception:
                _LOGGER.debug("LightModuleService evaluation failed for %s", config.zone_id)

        # Fallback: built-in light decision logic
        if config.light_mode == "manual":
            return ("none", 0, 4000, "manual_mode")

        # No presence -> turn off
        if not presence.occupied and config.light_mode != "circadian":
            return ("turn_off", 0, 4000, "no_presence")

        # Presence detected -- determine brightness
        if not brightness.artificial_light_needed:
            return ("turn_off", 0, 4000, "sufficient_natural_light")

        # Use brightness manager's suggestion, clamped to config bounds
        suggested = brightness.suggested_brightness_pct
        clamped = max(
            config.min_brightness_pct,
            min(config.max_brightness_pct, suggested),
        )

        # Simple circadian color temp
        hour = datetime.now(tz=timezone.utc).hour + datetime.now(tz=timezone.utc).minute / 60.0
        import math
        angle = 2 * math.pi * (hour - 12) / 24.0
        t = (math.cos(angle) + 1.0) / 2.0
        color_k = int(config.color_temp_min_k + t * (config.color_temp_max_k - config.color_temp_min_k))

        reason = "presence_with_brightness"
        if presence.state == "grace_period":
            reason = "grace_period"

        return ("turn_on", clamped, color_k, reason)

    def _compute_media_action(
        self,
        config: ZoneAutomationConfig,
        presence: ZonePresenceState,
    ) -> str:
        """Compute the media action for a zone."""
        if not config.media_players:
            return "none"
        if not config.media_follow_presence:
            return "none"

        # Check override modes
        consequences = self._get_zone_consequences(config.zone_id)
        if consequences:
            if not consequences.get("music_allowed", True):
                return "none"

        if presence.occupied:
            # Execute: notify MusicCloudService of motion
            if self._music_cloud is not None:
                try:
                    self._music_cloud.on_motion_detected(zone_id=config.zone_id)
                except Exception:
                    _LOGGER.debug("Failed to notify MusicCloud of motion in %s", config.zone_id)
            return "follow"
        elif presence.state == "vacant":
            # Execute: notify MusicCloudService of idle
            if self._music_cloud is not None:
                try:
                    self._music_cloud.on_zone_idle(zone_id=config.zone_id)
                except Exception:
                    _LOGGER.debug("Failed to notify MusicCloud of idle in %s", config.zone_id)
            return "unfollow"

        return "none"

    def _compute_heating_action(
        self,
        config: ZoneAutomationConfig,
    ) -> tuple[str, float]:
        """Compute heating action from override mode consequences.

        Returns (action, target_temp_c).
        """
        consequences = self._get_zone_consequences(config.zone_id)
        if not consequences:
            return "none", 0.0

        target = consequences.get("heating_target_temp_c", 0)
        if target and float(target) > 0:
            return "set_temp", float(target)

        return "none", 0.0

    # ---- Habitus zone sync -------------------------------------------------

    def sync_from_habitus_zones(self, zones_data: list[dict[str, Any]]) -> dict[str, Any]:
        """Auto-create/update zone automation configs from habitus zone data.

        This is called when the HA integration syncs zone definitions.
        Entities are auto-tagged by domain to populate the config.

        Parameters
        ----------
        zones_data : list[dict]
            List of zone dicts from the habitus zones API.  Expected keys:
            ``zone_id``, ``name``, ``entities``.

        Returns
        -------
        dict
            Summary of sync results.
        """
        created = 0
        updated = 0
        skipped = 0

        for zone in zones_data:
            zone_id = zone.get("zone_id", "")
            if not zone_id:
                skipped += 1
                continue

            entities = zone.get("entities", [])
            if isinstance(entities, dict):
                # Flatten dict of role -> entity_ids
                flat: list[str] = []
                for v in entities.values():
                    if isinstance(v, list):
                        flat.extend(v)
                    elif isinstance(v, str):
                        flat.append(v)
                entities = flat

            # Classify entities by domain
            presence_sensors: list[str] = []
            light_entities: list[str] = []
            brightness_sensors: list[str] = []
            media_players: list[str] = []

            for eid in entities:
                if not isinstance(eid, str) or "." not in eid:
                    continue
                domain = eid.split(".")[0]
                eid_lower = eid.lower()

                if domain == "binary_sensor":
                    # Assume motion/occupancy sensors
                    presence_sensors.append(eid)
                elif domain == "device_tracker":
                    presence_sensors.append(eid)
                elif domain == "light":
                    light_entities.append(eid)
                elif domain == "sensor":
                    # Heuristic: lux/brightness/illuminance in the entity name
                    if any(kw in eid_lower for kw in ("lux", "brightness", "illumin", "light_level")):
                        brightness_sensors.append(eid)
                    else:
                        # Other sensors might be presence-relevant
                        presence_sensors.append(eid)
                elif domain == "media_player":
                    media_players.append(eid)

            config_data = {
                "zone_id": zone_id,
                "enabled": True,
                "presence_sensors": presence_sensors,
                "light_entities": light_entities,
                "indoor_brightness_sensors": brightness_sensors,
                "media_players": media_players,
            }

            with self._lock:
                is_new = zone_id not in self._configs

            self.update_zone_config(zone_id, config_data)

            if is_new:
                created += 1
            else:
                updated += 1

        summary = {
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "total_zones": len(self._configs),
        }

        self._publish_event("zone_automation.zones_synced", summary)

        _LOGGER.info(
            "Zone automation sync: created=%d, updated=%d, skipped=%d, total=%d",
            created, updated, skipped, len(self._configs),
        )

        return summary

    # ---- Status ------------------------------------------------------------

    def get_zone_status(self, zone_id: str) -> dict[str, Any] | None:
        """Return current runtime status for a zone."""
        with self._lock:
            config = self._configs.get(zone_id)
            if config is None:
                return None

        presence_state = self._presence_engine.get_zone_state(zone_id)
        brightness_state = self._brightness_manager.get_zone_state(zone_id)

        with self._lock:
            last_eval = self._last_evaluations.get(zone_id)
            last_update = self._last_sensor_update.get(zone_id, 0.0)

        status = ZoneStatus(
            zone_id=zone_id,
            enabled=config.enabled,
            config_present=True,
            presence=presence_state or {},
            brightness=brightness_state or {},
            last_evaluation=last_eval.to_dict() if last_eval else {},
            last_sensor_update_ts=last_update,
        )
        return status.to_dict()

    def get_all_status(self) -> list[dict[str, Any]]:
        """Return runtime status for all configured zones."""
        with self._lock:
            zone_ids = list(self._configs.keys())

        results: list[dict[str, Any]] = []
        for zone_id in zone_ids:
            status = self.get_zone_status(zone_id)
            if status:
                results.append(status)
        return results

    # ---- EventBus ----------------------------------------------------------

    def _publish_event(self, topic: str, data: dict[str, Any]) -> None:
        """Publish an event to the EventBus if available."""
        if self._event_bus is not None:
            try:
                self._event_bus.publish(topic, data, source="zone_automation")
            except Exception:
                _LOGGER.debug("Failed to publish event %s", topic)

    # ---- Properties --------------------------------------------------------

    @property
    def presence_engine(self) -> PresenceEngine:
        """Access the underlying PresenceEngine."""
        return self._presence_engine

    @property
    def brightness_manager(self) -> BrightnessManager:
        """Access the underlying BrightnessManager."""
        return self._brightness_manager


__all__ = [
    "ZoneAutomationController",
    "ZoneAutomationConfig",
    "ZoneEvaluation",
    "ZoneStatus",
]
