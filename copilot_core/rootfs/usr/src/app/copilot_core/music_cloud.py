"""Music Cloud Service -- Sonos zone-following via motion sensors.

Builds on MediaZoneManager to provide automatic speaker grouping/ungrouping
when users move between Habitus zones, detected via motion-sensor webhook
events from Home Assistant.

Flow:
  1. HA fires a motion-sensor event (via webhook to Core add-on)
  2. MusicCloudService checks if any zone has active playback
  3. If yes, groups the new zone's speakers with the source coordinator
  4. When the zone becomes idle (no motion for ``follow_timeout_sec``),
     the zone's speakers are ungrouped

Extended (v10.0.0):
  - **Coordinator Handoff**: When the coordinator zone becomes idle but other
    zones are still active, the coordinator role is handed off to the next
    active zone instead of dissolving the group.
  - **Volume Presets**: Time-of-day dependent volume presets (morning/day/
    evening/night) per zone.
  - **Sonos Favorites**: First 15 Sonos favorites exposed for dashboard quick-select.
  - **Overtime**: Configurable delay before ungrouping after leaving a zone.
  - **Override Mode Integration**: Respects override modes (party/sleep/etc.)

Persistence: zone-player mappings are delegated to MediaZoneManager (SQLite).
Music Cloud config (follow settings, favorites) stored in /data/music_cloud.json.

All HA service calls go through the Supervisor API:
  POST http://supervisor/core/api/services/media_player/join
  POST http://supervisor/core/api/services/media_player/unjoin
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

_LOGGER = logging.getLogger(__name__)

CONFIG_PATH = os.environ.get("MUSIC_CLOUD_CONFIG", "/data/music_cloud.json")
DEFAULT_FOLLOW_TIMEOUT = 300  # 5 minutes


# ---------------------------------------------------------------------------
# Volume Presets (time-of-day dependent)
# ---------------------------------------------------------------------------

@dataclass
class VolumePreset:
    """Time-of-day volume preset."""
    morning: float = 0.25     # 06:00-10:00
    day: float = 0.40         # 10:00-17:00
    evening: float = 0.35     # 17:00-22:00
    night: float = 0.15       # 22:00-06:00

    def get_current(self, hour: float | None = None) -> float:
        """Return volume level for the current time of day."""
        if hour is None:
            hour = datetime.now(tz=timezone.utc).hour + datetime.now(tz=timezone.utc).minute / 60.0
        if 6.0 <= hour < 10.0:
            return self.morning
        elif 10.0 <= hour < 17.0:
            return self.day
        elif 17.0 <= hour < 22.0:
            return self.evening
        else:
            return self.night

    def to_dict(self) -> dict[str, float]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VolumePreset:
        known = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {}
        for k, v in data.items():
            if k in known:
                try:
                    filtered[k] = max(0.0, min(1.0, float(v)))
                except (TypeError, ValueError):
                    pass
        return cls(**filtered)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ZonePresence:
    """Tracks motion/presence state for a single zone."""

    zone_id: str
    active: bool = False
    last_motion_ts: float = 0.0
    person_ids: list[str] = field(default_factory=list)


@dataclass
class ActiveGroup:
    """An active speaker group created by music following."""

    group_id: str
    source_zone: str
    coordinator_entity: str
    coordinator_zone: str = ""  # Current coordinator zone (may differ from source after handoff)
    grouped_zones: list[str] = field(default_factory=list)
    grouped_entities: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_updated: float = field(default_factory=time.time)


@dataclass
class MusicCloudConfig:
    """Persisted configuration for the Music Cloud feature."""

    enabled: bool = True
    follow_timeout_sec: int = DEFAULT_FOLLOW_TIMEOUT
    auto_follow_on_motion: bool = True
    auto_ungroup_on_idle: bool = True
    # Overtime: extra seconds after zone goes idle before ungrouping
    overtime_sec: int = 60
    # Coordinator handoff: when coordinator leaves, pass to next active zone
    coordinator_handoff: bool = True
    # Per-zone overrides: zone_id -> {"timeout": int, "enabled": bool, "overtime_sec": int}
    zone_overrides: dict[str, dict[str, Any]] = field(default_factory=dict)
    # Per-zone favorites: zone_id -> [favorite_name, ...]
    zone_favorites: dict[str, list[str]] = field(default_factory=dict)
    # Default favorite to play when Musikwolke activates but no room has playback
    default_favorite: str = ""
    # Volume presets: global and per-zone
    volume_presets: dict[str, Any] = field(default_factory=lambda: VolumePreset().to_dict())
    zone_volume_presets: dict[str, dict[str, Any]] = field(default_factory=dict)
    # Max favorites shown in dashboard
    max_dashboard_favorites: int = 15


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class MusicCloudService:
    """Automatic Sonos/media_player zone following driven by motion sensors.

    This service sits on top of ``MediaZoneManager`` and adds:
    - Motion-event driven automatic grouping
    - Configurable idle timeout for ungrouping
    - Zone-level playback status tracking
    - Favorites/playlist management per zone
    - Manual group/ungroup controls

    Thread-safety: all mutable state is protected by ``_lock``.
    """

    def __init__(
        self,
        media_zone_manager: Any = None,
        config_path: str | None = None,
        override_modes_service: Any = None,
    ) -> None:
        self._media_mgr = media_zone_manager
        self._config_path = config_path or CONFIG_PATH
        self._override_modes = override_modes_service
        self._lock = threading.Lock()

        # In-memory state
        self._config = MusicCloudConfig()
        self._zone_presence: dict[str, ZonePresence] = {}
        self._active_groups: dict[str, ActiveGroup] = {}
        self._group_counter = 0
        self._event_log: list[dict[str, Any]] = []  # ring buffer, max 200
        # Sonos favorites cache (refreshed periodically)
        self._favorites_cache: list[dict[str, str]] = []
        self._favorites_cache_ts: float = 0.0

        # Load persisted config
        self._load_config()

        _LOGGER.info(
            "MusicCloudService initialized (enabled=%s, timeout=%ds, overtime=%ds)",
            self._config.enabled,
            self._config.follow_timeout_sec,
            self._config.overtime_sec,
        )

    # ------------------------------------------------------------------
    # Config persistence
    # ------------------------------------------------------------------

    def _load_config(self) -> None:
        """Load config from JSON file, falling back to defaults."""
        try:
            with open(self._config_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                self._config = MusicCloudConfig(
                    enabled=bool(data.get("enabled", True)),
                    follow_timeout_sec=max(
                        30,
                        min(3600, int(data.get("follow_timeout_sec", DEFAULT_FOLLOW_TIMEOUT))),
                    ),
                    auto_follow_on_motion=bool(data.get("auto_follow_on_motion", True)),
                    auto_ungroup_on_idle=bool(data.get("auto_ungroup_on_idle", True)),
                    overtime_sec=max(0, min(600, int(data.get("overtime_sec", 60)))),
                    coordinator_handoff=bool(data.get("coordinator_handoff", True)),
                    zone_overrides=data.get("zone_overrides", {}),
                    zone_favorites=data.get("zone_favorites", {}),
                    default_favorite=str(data.get("default_favorite", "")),
                    volume_presets=data.get("volume_presets", VolumePreset().to_dict()),
                    zone_volume_presets=data.get("zone_volume_presets", {}),
                    max_dashboard_favorites=max(1, min(30, int(data.get("max_dashboard_favorites", 15)))),
                )
                _LOGGER.info("Music Cloud config loaded from %s", self._config_path)
        except FileNotFoundError:
            _LOGGER.debug("No music cloud config at %s, using defaults", self._config_path)
        except Exception:
            _LOGGER.exception("Failed to load music cloud config from %s", self._config_path)

    def _save_config(self) -> None:
        """Persist config to JSON file."""
        try:
            data = asdict(self._config)
            os.makedirs(os.path.dirname(self._config_path) or "/data", exist_ok=True)
            with open(self._config_path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)
            _LOGGER.debug("Music Cloud config saved to %s", self._config_path)
        except Exception:
            _LOGGER.exception("Failed to save music cloud config")

    # ------------------------------------------------------------------
    # Configuration API
    # ------------------------------------------------------------------

    def get_config(self) -> dict[str, Any]:
        """Return current config as a dict."""
        with self._lock:
            return asdict(self._config)

    def update_config(self, **kwargs: Any) -> dict[str, Any]:
        """Update config fields and persist."""
        with self._lock:
            if "enabled" in kwargs:
                self._config.enabled = bool(kwargs["enabled"])
            if "follow_timeout_sec" in kwargs:
                try:
                    self._config.follow_timeout_sec = max(
                        30, min(3600, int(kwargs["follow_timeout_sec"]))
                    )
                except (TypeError, ValueError):
                    pass
            if "auto_follow_on_motion" in kwargs:
                self._config.auto_follow_on_motion = bool(kwargs["auto_follow_on_motion"])
            if "auto_ungroup_on_idle" in kwargs:
                self._config.auto_ungroup_on_idle = bool(kwargs["auto_ungroup_on_idle"])
            if "overtime_sec" in kwargs:
                try:
                    self._config.overtime_sec = max(0, min(600, int(kwargs["overtime_sec"])))
                except (TypeError, ValueError):
                    pass
            if "coordinator_handoff" in kwargs:
                self._config.coordinator_handoff = bool(kwargs["coordinator_handoff"])
            if "zone_overrides" in kwargs and isinstance(kwargs["zone_overrides"], dict):
                self._config.zone_overrides = kwargs["zone_overrides"]
            if "default_favorite" in kwargs:
                self._config.default_favorite = str(kwargs["default_favorite"]).strip()
            if "volume_presets" in kwargs and isinstance(kwargs["volume_presets"], dict):
                self._config.volume_presets = kwargs["volume_presets"]
            if "zone_volume_presets" in kwargs and isinstance(kwargs["zone_volume_presets"], dict):
                self._config.zone_volume_presets = kwargs["zone_volume_presets"]
            if "max_dashboard_favorites" in kwargs:
                try:
                    self._config.max_dashboard_favorites = max(1, min(30, int(kwargs["max_dashboard_favorites"])))
                except (TypeError, ValueError):
                    pass
            self._save_config()
            return asdict(self._config)

    def set_follow_enabled(self, enabled: bool) -> dict[str, Any]:
        """Enable or disable the music following feature."""
        return self.update_config(enabled=enabled)

    # ------------------------------------------------------------------
    # Zone presence tracking
    # ------------------------------------------------------------------

    def _get_zone_timeout(self, zone_id: str) -> int:
        """Return the follow timeout for a zone (zone override or global)."""
        override = self._config.zone_overrides.get(zone_id, {})
        return int(override.get("timeout", self._config.follow_timeout_sec))

    def _is_zone_follow_enabled(self, zone_id: str) -> bool:
        """Check if follow is enabled for a specific zone."""
        if not self._config.enabled:
            return False
        override = self._config.zone_overrides.get(zone_id, {})
        return bool(override.get("enabled", True))

    def on_motion_detected(
        self,
        zone_id: str,
        person_id: str = "",
        sensor_entity_id: str = "",
    ) -> dict[str, Any]:
        """Handle motion detected in a zone.

        This is the main entry point called when HA fires a motion sensor
        event via webhook. It:
        1. Updates zone presence state
        2. Checks for active playback in other zones
        3. If found, groups this zone's speakers with the source coordinator
        4. Returns the action taken

        Parameters
        ----------
        zone_id : str
            The Habitus zone where motion was detected.
        person_id : str, optional
            The person detected (if known from presence tracking).
        sensor_entity_id : str, optional
            The binary_sensor entity that triggered.

        Returns
        -------
        dict
            Action result with keys: ok, action, details.
        """
        if not zone_id:
            return {"ok": False, "error": "Missing zone_id"}

        now = time.time()

        with self._lock:
            # Update presence state
            if zone_id not in self._zone_presence:
                self._zone_presence[zone_id] = ZonePresence(zone_id=zone_id)
            presence = self._zone_presence[zone_id]
            presence.active = True
            presence.last_motion_ts = now
            if person_id and person_id not in presence.person_ids:
                presence.person_ids.append(person_id)

            self._log_event("motion_detected", zone_id, {
                "person_id": person_id,
                "sensor": sensor_entity_id,
            })

            # Check if follow is enabled
            if not self._config.auto_follow_on_motion:
                return {"ok": True, "action": "none", "reason": "auto_follow_disabled"}

            if not self._is_zone_follow_enabled(zone_id):
                return {"ok": True, "action": "none", "reason": "zone_follow_disabled"}

        # Check override modes (outside lock -- may call external service)
        if not self._is_music_allowed(zone_id):
            return {"ok": True, "action": "none", "reason": "music_suppressed_by_override"}

        with self._lock:
            # Check if this zone is already grouped
            for group in self._active_groups.values():
                if zone_id in group.grouped_zones:
                    group.last_updated = now
                    return {
                        "ok": True,
                        "action": "already_grouped",
                        "group_id": group.group_id,
                    }

            # Find zones with active playback
            source_zone, coordinator = self._find_active_playback_source(zone_id)

            if not source_zone or not coordinator:
                # No active playback -- check if default favorite should start
                if self._config.default_favorite and self._config.enabled:
                    return self.start_default_playback(zone_id)
                return {
                    "ok": True,
                    "action": "no_active_playback",
                    "reason": "No zone with active playback found",
                }

            # Group this zone's speakers with the source coordinator
            result = self._group_zone_to_source(zone_id, source_zone, coordinator)

            # Apply volume preset to the newly joined zone
            if result.get("ok") and result.get("action") == "grouped":
                try:
                    self.apply_volume_preset(zone_id)
                except Exception:
                    _LOGGER.debug("Failed to apply volume preset after grouping")

            return result

    def on_zone_idle(self, zone_id: str) -> dict[str, Any]:
        """Handle a zone becoming idle (no motion for timeout period).

        Called either by a timer/scheduler or explicitly by a webhook event
        indicating the zone's occupancy sensor cleared.

        With coordinator handoff: if the idle zone is the coordinator and
        other zones are still active, the coordinator role is handed off.

        Parameters
        ----------
        zone_id : str
            The zone that became idle.

        Returns
        -------
        dict
            Action result.
        """
        if not zone_id:
            return {"ok": False, "error": "Missing zone_id"}

        with self._lock:
            # Update presence state
            if zone_id in self._zone_presence:
                self._zone_presence[zone_id].active = False
                self._zone_presence[zone_id].person_ids.clear()

            self._log_event("zone_idle", zone_id, {})

            if not self._config.auto_ungroup_on_idle:
                return {"ok": True, "action": "none", "reason": "auto_ungroup_disabled"}

            # Check overtime: delay ungrouping by overtime_sec
            override = self._config.zone_overrides.get(zone_id, {})
            overtime = int(override.get("overtime_sec", self._config.overtime_sec))
            presence = self._zone_presence.get(zone_id)
            if presence and overtime > 0:
                elapsed = time.time() - presence.last_motion_ts
                if elapsed < overtime:
                    return {
                        "ok": True,
                        "action": "overtime",
                        "reason": f"Overtime active ({overtime - int(elapsed)}s remaining)",
                        "overtime_remaining_s": overtime - int(elapsed),
                    }

            # Check if coordinator handoff is needed
            if self._config.coordinator_handoff:
                handoff_result = self._try_coordinator_handoff(zone_id)
                if handoff_result:
                    return handoff_result

            # Find and remove this zone from any active groups
            result = self._ungroup_zone(zone_id)
            return result

    def check_idle_zones(self) -> list[dict[str, Any]]:
        """Check all zones for idle timeout and ungroup as needed.

        This should be called periodically (e.g. every 30 seconds) by a
        background timer.

        Returns
        -------
        list[dict]
            List of ungroup actions taken.
        """
        now = time.time()
        actions = []

        with self._lock:
            for zone_id, presence in list(self._zone_presence.items()):
                if not presence.active:
                    continue
                timeout = self._get_zone_timeout(zone_id)
                if (now - presence.last_motion_ts) > timeout:
                    presence.active = False
                    presence.person_ids.clear()
                    self._log_event("idle_timeout", zone_id, {"timeout": timeout})
                    if self._config.auto_ungroup_on_idle:
                        result = self._ungroup_zone(zone_id)
                        actions.append(result)

        return actions

    # ------------------------------------------------------------------
    # Playback discovery
    # ------------------------------------------------------------------

    def _find_active_playback_source(
        self, exclude_zone: str = "",
    ) -> tuple[str | None, str | None]:
        """Find a zone with active playback and return (zone_id, coordinator_entity).

        First checks existing active groups (returns the group's coordinator).
        Then queries MediaZoneManager for zones with 'playing' state.
        """
        # Check existing groups first (reuse existing coordinator)
        for group in self._active_groups.values():
            return group.source_zone, group.coordinator_entity

        # Query MediaZoneManager for all zones with playback
        if not self._media_mgr:
            return None, None

        try:
            all_assignments = self._media_mgr.get_all_assignments()
        except Exception:
            _LOGGER.debug("Failed to get zone assignments", exc_info=True)
            return None, None

        for zone_id, players in all_assignments.items():
            if zone_id == exclude_zone:
                continue
            try:
                state = self._media_mgr.get_zone_media_state(zone_id)
                if isinstance(state, dict) and state.get("state") == "playing":
                    # Find the first playing player as coordinator
                    for p in state.get("players", []):
                        if isinstance(p, dict) and p.get("state") == "playing":
                            return zone_id, p.get("entity_id")
                    # Fallback: use first assigned player
                    if players:
                        entity_id = (
                            players[0].get("entity_id")
                            if isinstance(players[0], dict) else str(players[0])
                        )
                        return zone_id, entity_id
            except Exception:
                _LOGGER.debug("Failed to query state for zone %s", zone_id, exc_info=True)

        return None, None

    # ------------------------------------------------------------------
    # Grouping / ungrouping
    # ------------------------------------------------------------------

    def _group_zone_to_source(
        self,
        target_zone: str,
        source_zone: str,
        coordinator_entity: str,
    ) -> dict[str, Any]:
        """Group a target zone's speakers with the source zone's coordinator.

        Uses MediaZoneManager._join_players if available, otherwise calls
        HA Supervisor API directly.
        """
        if not self._media_mgr:
            return {"ok": False, "error": "MediaZoneManager not available"}

        # Get target zone players
        try:
            target_players = self._media_mgr.get_zone_players(target_zone)
        except Exception:
            return {"ok": False, "error": f"Failed to get players for zone {target_zone}"}

        if not target_players:
            return {"ok": False, "error": f"No players assigned to zone {target_zone}"}

        target_entity_ids = [
            p["entity_id"] for p in target_players
            if isinstance(p, dict) and p.get("entity_id")
        ]

        if not target_entity_ids:
            return {"ok": False, "error": f"No valid entity IDs in zone {target_zone}"}

        # Perform the join
        try:
            join_result = self._media_mgr._join_players(coordinator_entity, target_entity_ids)
        except Exception as exc:
            _LOGGER.exception("Failed to join players in zone %s", target_zone)
            return {"ok": False, "error": str(exc)}

        # Track the group
        group = self._find_or_create_group(source_zone, coordinator_entity)
        if target_zone not in group.grouped_zones:
            group.grouped_zones.append(target_zone)
        group.grouped_entities = list(
            set(group.grouped_entities) | set(target_entity_ids)
        )
        group.last_updated = time.time()

        self._log_event("zone_grouped", target_zone, {
            "source_zone": source_zone,
            "coordinator": coordinator_entity,
            "joined_entities": target_entity_ids,
        })

        _LOGGER.info(
            "Music Cloud: grouped zone '%s' -> coordinator '%s' (source zone: '%s')",
            target_zone, coordinator_entity, source_zone,
        )

        return {
            "ok": True,
            "action": "grouped",
            "group_id": group.group_id,
            "source_zone": source_zone,
            "target_zone": target_zone,
            "coordinator": coordinator_entity,
            "joined_entities": target_entity_ids,
            "join_result": join_result if isinstance(join_result, dict) else {},
        }

    def _ungroup_zone(self, zone_id: str) -> dict[str, Any]:
        """Ungroup a zone's speakers from any active group."""
        if not self._media_mgr:
            return {"ok": False, "error": "MediaZoneManager not available"}

        ungrouped_entities: list[str] = []
        removed_from_group = ""

        for group_id, group in list(self._active_groups.items()):
            if zone_id not in group.grouped_zones:
                continue

            # Get this zone's players
            try:
                zone_players = self._media_mgr.get_zone_players(zone_id)
            except Exception:
                zone_players = []

            zone_entity_ids = [
                p["entity_id"] for p in zone_players
                if isinstance(p, dict) and p.get("entity_id")
            ]

            # Don't unjoin the coordinator
            members_to_unjoin = [
                e for e in zone_entity_ids if e != group.coordinator_entity
            ]

            if members_to_unjoin:
                try:
                    self._media_mgr._unjoin_players(members_to_unjoin)
                    ungrouped_entities.extend(members_to_unjoin)
                except Exception:
                    _LOGGER.exception("Failed to unjoin players from zone %s", zone_id)

            # Update group state
            group.grouped_zones = [z for z in group.grouped_zones if z != zone_id]
            group.grouped_entities = [
                e for e in group.grouped_entities if e not in zone_entity_ids
            ]
            removed_from_group = group_id

            # If no more grouped zones, remove the group
            if not group.grouped_zones:
                del self._active_groups[group_id]

            break  # A zone can only be in one group

        if ungrouped_entities:
            self._log_event("zone_ungrouped", zone_id, {
                "ungrouped_entities": ungrouped_entities,
                "group_id": removed_from_group,
            })
            _LOGGER.info(
                "Music Cloud: ungrouped zone '%s' (%d entities)",
                zone_id, len(ungrouped_entities),
            )

        return {
            "ok": True,
            "action": "ungrouped" if ungrouped_entities else "not_grouped",
            "zone_id": zone_id,
            "ungrouped_entities": ungrouped_entities,
            "group_id": removed_from_group or None,
        }

    def _find_or_create_group(
        self, source_zone: str, coordinator_entity: str,
    ) -> ActiveGroup:
        """Find an existing group for this source or create a new one."""
        for group in self._active_groups.values():
            if group.source_zone == source_zone and group.coordinator_entity == coordinator_entity:
                return group

        self._group_counter += 1
        group_id = f"mcg_{self._group_counter}"
        group = ActiveGroup(
            group_id=group_id,
            source_zone=source_zone,
            coordinator_entity=coordinator_entity,
        )
        self._active_groups[group_id] = group
        return group

    # ------------------------------------------------------------------
    # Manual group / ungroup
    # ------------------------------------------------------------------

    def manual_group(
        self,
        source_zone: str,
        target_zones: list[str],
        coordinator_entity: str | None = None,
    ) -> dict[str, Any]:
        """Manually group target zones' speakers with the source zone.

        Parameters
        ----------
        source_zone : str
            The zone providing the audio source.
        target_zones : list[str]
            Zones to add to the group.
        coordinator_entity : str, optional
            Specific coordinator entity. Auto-detected if not given.

        Returns
        -------
        dict
            Group result.
        """
        if not self._media_mgr:
            return {"ok": False, "error": "MediaZoneManager not available"}

        if not source_zone:
            return {"ok": False, "error": "Missing source_zone"}
        if not target_zones:
            return {"ok": False, "error": "Missing target_zones"}

        # Determine coordinator
        if not coordinator_entity:
            try:
                source_players = self._media_mgr.get_zone_players(source_zone)
                if source_players:
                    coordinator_entity = source_players[0].get("entity_id", "")
            except Exception:
                pass

        if not coordinator_entity:
            return {"ok": False, "error": f"No coordinator found for zone {source_zone}"}

        results = []
        with self._lock:
            for tz in target_zones:
                r = self._group_zone_to_source(tz, source_zone, coordinator_entity)
                results.append(r)

        return {
            "ok": True,
            "source_zone": source_zone,
            "coordinator": coordinator_entity,
            "results": results,
        }

    def manual_ungroup(self, zone_ids: list[str]) -> dict[str, Any]:
        """Manually ungroup specified zones.

        Parameters
        ----------
        zone_ids : list[str]
            Zones to ungroup.

        Returns
        -------
        dict
            Ungroup result.
        """
        if not zone_ids:
            return {"ok": False, "error": "Missing zone_ids"}

        results = []
        with self._lock:
            for zone_id in zone_ids:
                r = self._ungroup_zone(zone_id)
                results.append(r)

        return {"ok": True, "results": results}

    # ------------------------------------------------------------------
    # Zone status & query
    # ------------------------------------------------------------------

    def get_zones_status(self) -> dict[str, Any]:
        """Return current status for all known zones.

        Combines zone-player assignments, presence state, group state,
        and playback state.
        """
        zones: dict[str, dict[str, Any]] = {}

        # Get all zone assignments
        if self._media_mgr:
            try:
                all_assignments = self._media_mgr.get_all_assignments()
                for zone_id, players in all_assignments.items():
                    zones[zone_id] = {
                        "zone_id": zone_id,
                        "players": players,
                        "presence": None,
                        "group": None,
                        "playback_state": "unknown",
                    }
            except Exception:
                _LOGGER.debug("Failed to get zone assignments", exc_info=True)

        with self._lock:
            # Add presence state
            for zone_id, presence in self._zone_presence.items():
                if zone_id not in zones:
                    zones[zone_id] = {
                        "zone_id": zone_id,
                        "players": [],
                        "presence": None,
                        "group": None,
                        "playback_state": "unknown",
                    }
                zones[zone_id]["presence"] = {
                    "active": presence.active,
                    "last_motion_ts": presence.last_motion_ts,
                    "person_ids": list(presence.person_ids),
                }

            # Add group state
            for group in self._active_groups.values():
                for gz in group.grouped_zones:
                    if gz in zones:
                        zones[gz]["group"] = {
                            "group_id": group.group_id,
                            "source_zone": group.source_zone,
                            "coordinator": group.coordinator_entity,
                            "role": "member",
                        }
                if group.source_zone in zones:
                    zones[group.source_zone]["group"] = {
                        "group_id": group.group_id,
                        "source_zone": group.source_zone,
                        "coordinator": group.coordinator_entity,
                        "role": "source",
                    }

        # Get playback state per zone
        if self._media_mgr:
            for zone_id in list(zones.keys()):
                try:
                    state = self._media_mgr.get_zone_media_state(zone_id)
                    if isinstance(state, dict):
                        zones[zone_id]["playback_state"] = state.get("state", "unknown")
                except Exception:
                    pass

        return {
            "ok": True,
            "zones": zones,
            "config": asdict(self._config),
            "active_groups": len(self._active_groups),
        }

    def get_playback_status(self) -> dict[str, Any]:
        """Return current playback status per zone."""
        zone_states: dict[str, dict[str, Any]] = {}

        if self._media_mgr:
            try:
                all_assignments = self._media_mgr.get_all_assignments()
                for zone_id in all_assignments:
                    try:
                        state = self._media_mgr.get_zone_media_state(zone_id)
                        zone_states[zone_id] = state if isinstance(state, dict) else {}
                    except Exception:
                        zone_states[zone_id] = {"state": "error"}
            except Exception:
                _LOGGER.debug("Failed to query playback status", exc_info=True)

        with self._lock:
            groups = [
                {
                    "group_id": g.group_id,
                    "source_zone": g.source_zone,
                    "coordinator": g.coordinator_entity,
                    "grouped_zones": list(g.grouped_zones),
                    "grouped_entities": list(g.grouped_entities),
                    "created_at": g.created_at,
                }
                for g in self._active_groups.values()
            ]

        return {
            "ok": True,
            "zone_states": zone_states,
            "active_groups": groups,
            "follow_enabled": self._config.enabled,
        }

    def get_active_groups(self) -> list[dict[str, Any]]:
        """Return list of active speaker groups."""
        with self._lock:
            return [
                {
                    "group_id": g.group_id,
                    "source_zone": g.source_zone,
                    "coordinator": g.coordinator_entity,
                    "grouped_zones": list(g.grouped_zones),
                    "grouped_entities": list(g.grouped_entities),
                    "created_at": g.created_at,
                    "last_updated": g.last_updated,
                }
                for g in self._active_groups.values()
            ]

    # ------------------------------------------------------------------
    # Favorites management
    # ------------------------------------------------------------------

    def get_zone_favorites(self, zone_id: str) -> dict[str, Any]:
        """Get favorites/playlists for a zone.

        Combines locally stored favorites with HA entity source_list.
        """
        favorites: list[str] = []

        # Local favorites from config
        with self._lock:
            local_favs = list(self._config.zone_favorites.get(zone_id, []))

        # HA favorites from entity
        ha_favs: list[str] = []
        if self._media_mgr:
            try:
                result = self._media_mgr.get_zone_favorites(zone_id)
                if isinstance(result, dict) and result.get("ok"):
                    ha_favs = result.get("favorites", [])
            except Exception:
                pass

        # Merge, local first, deduplicated
        seen: set[str] = set()
        for name in local_favs + ha_favs:
            name = str(name).strip()
            if name and name not in seen:
                seen.add(name)
                favorites.append(name)

        return {
            "ok": True,
            "zone_id": zone_id,
            "favorites": favorites,
            "local_count": len(local_favs),
            "ha_count": len(ha_favs),
        }

    def set_zone_favorites(self, zone_id: str, favorites: list[str]) -> dict[str, Any]:
        """Set locally stored favorites for a zone."""
        clean = [str(f).strip() for f in favorites if str(f).strip()]
        with self._lock:
            self._config.zone_favorites[zone_id] = clean
            self._save_config()
        return {"ok": True, "zone_id": zone_id, "favorites": clean}

    def get_all_favorites(self) -> dict[str, Any]:
        """Return favorites for all zones."""
        zones: dict[str, list[str]] = {}

        if self._media_mgr:
            try:
                all_assignments = self._media_mgr.get_all_assignments()
                for zone_id in all_assignments:
                    result = self.get_zone_favorites(zone_id)
                    zones[zone_id] = result.get("favorites", [])
            except Exception:
                pass

        # Also include zones that have local favorites but no assigned players
        with self._lock:
            for zone_id, favs in self._config.zone_favorites.items():
                if zone_id not in zones:
                    zones[zone_id] = list(favs)

        return {"ok": True, "zones": zones}

    # ------------------------------------------------------------------
    # Coordinator handoff
    # ------------------------------------------------------------------

    def _try_coordinator_handoff(self, leaving_zone: str) -> dict[str, Any] | None:
        """Try to hand off coordinator role when the coordinator zone goes idle.

        If the leaving zone is the current coordinator of any group and other
        zones are still active, pick the next active zone as the new coordinator.

        Returns
        -------
        dict or None
            Handoff result if performed, None if no handoff needed.
        """
        for group_id, group in list(self._active_groups.items()):
            coordinator_zone = group.coordinator_zone or group.source_zone
            if coordinator_zone != leaving_zone:
                continue

            # This zone is the coordinator -- find next active zone
            remaining_zones = [z for z in group.grouped_zones if z != leaving_zone]
            next_coordinator_zone = None

            for candidate_zone in remaining_zones:
                presence = self._zone_presence.get(candidate_zone)
                if presence and presence.active:
                    next_coordinator_zone = candidate_zone
                    break

            if not next_coordinator_zone:
                # No active zones remaining -- dissolve group normally
                return None

            # Perform handoff: unjoin leaving zone, set new coordinator
            if self._media_mgr:
                try:
                    leaving_players = self._media_mgr.get_zone_players(leaving_zone)
                    leaving_ids = [
                        p["entity_id"] for p in leaving_players
                        if isinstance(p, dict) and p.get("entity_id")
                        and p["entity_id"] != group.coordinator_entity
                    ]
                    if leaving_ids:
                        self._media_mgr._unjoin_players(leaving_ids)
                except Exception:
                    _LOGGER.debug("Failed to unjoin leaving coordinator zone %s", leaving_zone)

                # Find new coordinator entity
                try:
                    new_players = self._media_mgr.get_zone_players(next_coordinator_zone)
                    if new_players:
                        new_coordinator_entity = new_players[0].get("entity_id", "")
                        if new_coordinator_entity:
                            # Regroup around new coordinator
                            all_remaining_entities = []
                            for z in remaining_zones:
                                try:
                                    zp = self._media_mgr.get_zone_players(z)
                                    for p in zp:
                                        eid = p.get("entity_id", "")
                                        if eid and eid != new_coordinator_entity:
                                            all_remaining_entities.append(eid)
                                except Exception:
                                    pass

                            if all_remaining_entities:
                                self._media_mgr._join_players(new_coordinator_entity, all_remaining_entities)

                            group.coordinator_entity = new_coordinator_entity
                            group.coordinator_zone = next_coordinator_zone
                            group.grouped_zones = remaining_zones
                            group.grouped_entities = [new_coordinator_entity] + all_remaining_entities
                            group.last_updated = time.time()

                            self._log_event("coordinator_handoff", leaving_zone, {
                                "new_coordinator_zone": next_coordinator_zone,
                                "new_coordinator_entity": new_coordinator_entity,
                                "group_id": group_id,
                            })

                            _LOGGER.info(
                                "Music Cloud: coordinator handoff %s -> %s (group %s)",
                                leaving_zone, next_coordinator_zone, group_id,
                            )

                            return {
                                "ok": True,
                                "action": "coordinator_handoff",
                                "leaving_zone": leaving_zone,
                                "new_coordinator_zone": next_coordinator_zone,
                                "new_coordinator_entity": new_coordinator_entity,
                                "group_id": group_id,
                                "remaining_zones": remaining_zones,
                            }
                except Exception:
                    _LOGGER.exception("Coordinator handoff failed for zone %s", leaving_zone)

        return None

    # ------------------------------------------------------------------
    # Override mode check
    # ------------------------------------------------------------------

    def _is_music_allowed(self, zone_id: str) -> bool:
        """Check if music automation is allowed for a zone (override modes)."""
        if self._override_modes is None:
            return True
        try:
            consequences = self._override_modes.get_effective_consequences(zone_id)
            return bool(consequences.get("music_allowed", True))
        except Exception:
            return True

    # ------------------------------------------------------------------
    # Volume presets
    # ------------------------------------------------------------------

    def get_volume_preset(self, zone_id: str = "", hour: float | None = None) -> dict[str, Any]:
        """Get the current volume preset for a zone or globally.

        Parameters
        ----------
        zone_id : str
            Zone to check. Empty = global preset.
        hour : float, optional
            Override hour of day (for testing).

        Returns
        -------
        dict
            Volume preset info with current_volume, time_period, and preset values.
        """
        # Zone-specific preset takes precedence
        preset_data = None
        if zone_id and zone_id in self._config.zone_volume_presets:
            preset_data = self._config.zone_volume_presets[zone_id]

        if preset_data is None:
            preset_data = self._config.volume_presets

        preset = VolumePreset.from_dict(preset_data) if isinstance(preset_data, dict) else VolumePreset()
        current_volume = preset.get_current(hour)

        if hour is None:
            now = datetime.now(tz=timezone.utc)
            hour = now.hour + now.minute / 60.0

        if 6.0 <= hour < 10.0:
            period = "morning"
        elif 10.0 <= hour < 17.0:
            period = "day"
        elif 17.0 <= hour < 22.0:
            period = "evening"
        else:
            period = "night"

        return {
            "zone_id": zone_id or "global",
            "current_volume": current_volume,
            "time_period": period,
            "presets": preset.to_dict(),
        }

    def set_volume_preset(
        self, zone_id: str = "", presets: dict[str, float] | None = None
    ) -> dict[str, Any]:
        """Set volume presets for a zone or globally.

        Parameters
        ----------
        zone_id : str
            Zone to set. Empty = global preset.
        presets : dict
            Keys: morning, day, evening, night. Values: 0.0-1.0.
        """
        if presets is None:
            return {"ok": False, "error": "Missing presets"}

        validated = {}
        for key in ("morning", "day", "evening", "night"):
            if key in presets:
                try:
                    validated[key] = max(0.0, min(1.0, float(presets[key])))
                except (TypeError, ValueError):
                    pass

        with self._lock:
            if zone_id:
                existing = self._config.zone_volume_presets.get(zone_id, VolumePreset().to_dict())
                existing.update(validated)
                self._config.zone_volume_presets[zone_id] = existing
            else:
                self._config.volume_presets.update(validated)
            self._save_config()

        return {"ok": True, "zone_id": zone_id or "global", "presets": validated}

    def apply_volume_preset(self, zone_id: str) -> dict[str, Any]:
        """Apply the current time-of-day volume preset to a zone's speakers."""
        preset = self.get_volume_preset(zone_id)
        volume = preset["current_volume"]

        if not self._media_mgr:
            return {"ok": False, "error": "MediaZoneManager not available"}

        result = self._media_mgr.set_zone_volume(zone_id, volume)
        return {
            "ok": True,
            "zone_id": zone_id,
            "volume_applied": volume,
            "time_period": preset["time_period"],
            "result": result,
        }

    # ------------------------------------------------------------------
    # Sonos favorites (dashboard)
    # ------------------------------------------------------------------

    def get_sonos_favorites(self, limit: int = 0) -> dict[str, Any]:
        """Get Sonos favorites from the sensor.sonos_favorites entity.

        Returns up to ``max_dashboard_favorites`` favorites for dashboard display.
        """
        if limit <= 0:
            limit = self._config.max_dashboard_favorites

        favorites: list[dict[str, str]] = []

        if self._media_mgr:
            try:
                all_assignments = self._media_mgr.get_all_assignments()
                for zone_id, players in all_assignments.items():
                    zone_favs = self._media_mgr.get_zone_favorites(zone_id)
                    if isinstance(zone_favs, dict) and zone_favs.get("ok"):
                        for name in zone_favs.get("favorites", []):
                            if not any(f["name"] == name for f in favorites):
                                favorites.append({"name": name, "zone_source": zone_id})
                    if len(favorites) >= limit:
                        break
            except Exception:
                _LOGGER.debug("Failed to fetch Sonos favorites", exc_info=True)

        return {
            "ok": True,
            "favorites": favorites[:limit],
            "total": len(favorites),
            "max_dashboard": self._config.max_dashboard_favorites,
        }

    def play_favorite_with_musikwolke(
        self,
        zone_id: str,
        favorite_name: str,
    ) -> dict[str, Any]:
        """Play a Sonos favorite and activate Musikwolke in the zone.

        If no other room has playback, this zone becomes the coordinator.
        """
        if not self._is_music_allowed(zone_id):
            return {"ok": False, "error": "Music suppressed by override mode"}

        if not self._media_mgr:
            return {"ok": False, "error": "MediaZoneManager not available"}

        # Play the favorite
        play_result = self._media_mgr.play_zone_favorite(zone_id, favorite_name)

        # Apply volume preset
        self.apply_volume_preset(zone_id)

        # Mark this zone as the coordinator
        with self._lock:
            leader = self._media_mgr._pick_zone_leader(zone_id)
            if leader:
                group = self._find_or_create_group(zone_id, leader)
                group.coordinator_zone = zone_id

                self._log_event("favorite_play_musikwolke", zone_id, {
                    "favorite": favorite_name,
                    "coordinator": leader,
                })

        return {
            "ok": True,
            "zone_id": zone_id,
            "favorite": favorite_name,
            "play_result": play_result,
            "musikwolke_active": True,
        }

    def start_default_playback(self, zone_id: str) -> dict[str, Any]:
        """Start playback of the default favorite when Musikwolke activates
        but no room has active playback.
        """
        default = self._config.default_favorite
        if not default:
            return {"ok": False, "error": "No default favorite configured"}

        return self.play_favorite_with_musikwolke(zone_id, default)

    # ------------------------------------------------------------------
    # Event log
    # ------------------------------------------------------------------

    def _log_event(self, event_type: str, zone_id: str, data: dict[str, Any]) -> None:
        """Append to the in-memory event ring buffer."""
        entry = {
            "event_type": event_type,
            "zone_id": zone_id,
            "timestamp": time.time(),
            **data,
        }
        self._event_log.append(entry)
        # Keep last 200 events
        if len(self._event_log) > 200:
            self._event_log = self._event_log[-200:]

    def get_event_log(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return recent events (newest first)."""
        with self._lock:
            return list(reversed(self._event_log[-limit:]))
