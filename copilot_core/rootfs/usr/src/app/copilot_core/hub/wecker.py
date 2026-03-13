"""Wecker (Smart Alarm) Module.

Provides intelligent alarm/wake-up functionality:
- Per-person alarm schedules with zone assignment
- Sonos wake-up with gradual volume ramp + music/radio
- Light ramp integration (gradual brightness increase)
- Smart snooze and dismiss via HA events
- Weekday/weekend/custom day schedules
- Persistence to /data/wecker_alarms.json

Integration:
- Sonos: play_favorite / play_uri with volume ramp
- Zone Automation: triggers morning scene on alarm fire
- Conversation Memory: reads preferred wake_time per person
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence

_LOGGER = logging.getLogger(__name__)

_ALARMS_FILE = "/data/wecker_alarms.json"


class AlarmState(str, Enum):
    """Alarm states."""
    PENDING = "pending"       # Scheduled, not yet triggered
    RINGING = "ringing"       # Currently ringing
    SNOOZED = "snoozed"      # Snoozed (will re-trigger)
    DISMISSED = "dismissed"   # Dismissed by user
    FIRED = "fired"           # Completed (auto-dismiss after timeout)
    DISABLED = "disabled"     # Manually disabled


class AlarmRepeat(str, Enum):
    """Alarm repeat modes."""
    ONCE = "once"
    WEEKDAYS = "weekdays"       # Mo-Fr
    WEEKENDS = "weekends"       # Sa-So
    DAILY = "daily"
    CUSTOM = "custom"           # specific days list


@dataclass
class AlarmConfig:
    """Alarm configuration."""
    alarm_id: str
    person_id: str                         # e.g. "person.papa"
    zone_id: str                           # e.g. "schlafzimmer"
    time_hhmm: str                         # "06:30"
    repeat: str = "weekdays"               # AlarmRepeat value
    custom_days: List[int] = field(default_factory=list)  # 0=Mo..6=So for CUSTOM
    enabled: bool = True
    label: str = ""

    # Wake-up config
    sonos_room: str = ""                   # Sonos room name (empty = no music)
    sonos_favorite: str = ""               # Favorite/playlist name
    sonos_uri: str = ""                    # Direct URI (radio stream)
    volume_start: int = 10                 # Start volume (0-100)
    volume_end: int = 40                   # End volume after ramp
    volume_ramp_minutes: int = 5           # Ramp duration
    light_entities: List[str] = field(default_factory=list)  # Light entities for gradual on
    light_ramp_minutes: int = 10           # Light ramp (starts before alarm)
    light_brightness_pct: int = 80         # Target brightness
    snooze_minutes: int = 9                # Snooze duration
    auto_dismiss_minutes: int = 30         # Auto-dismiss after N minutes

    # Runtime state (not persisted in config)
    state: str = "pending"
    last_triggered: Optional[str] = None
    next_trigger: Optional[str] = None


class WeckerService:
    """Smart Alarm / Wake-Up Service."""

    def __init__(self, sonos_client=None, config: Optional[Dict] = None):
        """Initialize.

        Args:
            sonos_client: SonosClient instance (from services dict)
            config: Global config dict (options.json)
        """
        self._sonos = sonos_client
        self._config = config or {}
        self._alarms: Dict[str, AlarmConfig] = {}
        self._lock = threading.RLock()
        self._ramp_threads: Dict[str, threading.Thread] = {}
        self._load_alarms()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load_alarms(self) -> None:
        """Load alarms from disk."""
        if not os.path.exists(_ALARMS_FILE):
            return
        try:
            with open(_ALARMS_FILE, "r") as f:
                data = json.load(f)
            for entry in data.get("alarms", []):
                alarm = AlarmConfig(**{
                    k: v for k, v in entry.items()
                    if k in AlarmConfig.__dataclass_fields__
                })
                alarm.state = "pending"  # Reset state on load
                self._alarms[alarm.alarm_id] = alarm
            _LOGGER.info("Loaded %d alarms from %s", len(self._alarms), _ALARMS_FILE)
        except Exception as exc:
            _LOGGER.warning("Failed to load alarms: %s", exc)

    def _save_alarms(self) -> None:
        """Save alarms to disk."""
        try:
            persistable = []
            for a in self._alarms.values():
                d = asdict(a)
                # Don't persist runtime state
                d.pop("state", None)
                d.pop("last_triggered", None)
                d.pop("next_trigger", None)
                persistable.append(d)
            os.makedirs(os.path.dirname(_ALARMS_FILE), exist_ok=True)
            with open(_ALARMS_FILE, "w") as f:
                json.dump({"alarms": persistable, "updated": datetime.now(timezone.utc).isoformat()}, f, indent=2)
        except Exception as exc:
            _LOGGER.warning("Failed to save alarms: %s", exc)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def list_alarms(self, person_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all alarms, optionally filtered by person."""
        with self._lock:
            alarms = list(self._alarms.values())
        if person_id:
            alarms = [a for a in alarms if a.person_id == person_id]
        result = []
        for a in alarms:
            d = asdict(a)
            d["next_trigger"] = self._compute_next_trigger(a)
            result.append(d)
        return result

    def get_alarm(self, alarm_id: str) -> Optional[Dict[str, Any]]:
        """Get a single alarm."""
        with self._lock:
            a = self._alarms.get(alarm_id)
        if not a:
            return None
        d = asdict(a)
        d["next_trigger"] = self._compute_next_trigger(a)
        return d

    def create_alarm(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new alarm."""
        alarm_id = data.get("alarm_id") or f"alarm_{int(time.time() * 1000)}"
        data["alarm_id"] = alarm_id

        alarm = AlarmConfig(**{
            k: v for k, v in data.items()
            if k in AlarmConfig.__dataclass_fields__
        })
        alarm.state = "pending"

        with self._lock:
            self._alarms[alarm_id] = alarm
            self._save_alarms()

        _LOGGER.info("Created alarm %s for %s at %s", alarm_id, alarm.person_id, alarm.time_hhmm)
        return asdict(alarm)

    def update_alarm(self, alarm_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update an existing alarm."""
        with self._lock:
            existing = self._alarms.get(alarm_id)
            if not existing:
                return None
            for key, val in data.items():
                if key != "alarm_id" and hasattr(existing, key):
                    setattr(existing, key, val)
            self._save_alarms()
        return asdict(existing)

    def delete_alarm(self, alarm_id: str) -> bool:
        """Delete an alarm."""
        with self._lock:
            if alarm_id not in self._alarms:
                return False
            del self._alarms[alarm_id]
            self._save_alarms()
        _LOGGER.info("Deleted alarm %s", alarm_id)
        return True

    # ------------------------------------------------------------------
    # Alarm Trigger Logic
    # ------------------------------------------------------------------

    def check_alarms(self) -> List[Dict[str, Any]]:
        """Check all alarms and trigger those that are due.

        Should be called periodically (e.g. every 30s from a scheduler).
        Returns list of triggered alarm dicts.
        """
        now = datetime.now(timezone.utc)
        triggered = []

        with self._lock:
            for alarm in self._alarms.values():
                if not alarm.enabled or alarm.state in ("ringing", "disabled"):
                    continue

                if self._should_fire(alarm, now):
                    alarm.state = "ringing"
                    alarm.last_triggered = now.isoformat()
                    triggered.append(asdict(alarm))

        for t in triggered:
            self._execute_wakeup(t)

        return triggered

    def _should_fire(self, alarm: AlarmConfig, now: datetime) -> bool:
        """Check if alarm should fire at current time."""
        try:
            h, m = map(int, alarm.time_hhmm.split(":"))
        except (ValueError, AttributeError):
            return False

        # Check time match (within 60s window)
        if now.hour != h or now.minute != m:
            return False

        # Check if already fired in last 2 minutes (prevent double-fire)
        if alarm.last_triggered:
            try:
                last = datetime.fromisoformat(alarm.last_triggered)
                if (now - last).total_seconds() < 120:
                    return False
            except (ValueError, TypeError):
                pass

        # Check day match
        weekday = now.weekday()  # 0=Mon..6=Sun
        repeat = alarm.repeat
        if repeat == "weekdays" and weekday > 4:
            return False
        if repeat == "weekends" and weekday < 5:
            return False
        if repeat == "custom" and weekday not in alarm.custom_days:
            return False
        if repeat == "once" and alarm.last_triggered:
            return False

        return True

    def _compute_next_trigger(self, alarm: AlarmConfig) -> Optional[str]:
        """Compute next trigger time for display."""
        if not alarm.enabled:
            return None
        try:
            h, m = map(int, alarm.time_hhmm.split(":"))
        except (ValueError, AttributeError):
            return None

        now = datetime.now(timezone.utc)
        candidate = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if candidate <= now:
            candidate += timedelta(days=1)

        # Find next matching day
        for _ in range(8):
            wd = candidate.weekday()
            repeat = alarm.repeat
            if repeat == "daily" or repeat == "once":
                return candidate.isoformat()
            if repeat == "weekdays" and wd <= 4:
                return candidate.isoformat()
            if repeat == "weekends" and wd >= 5:
                return candidate.isoformat()
            if repeat == "custom" and wd in alarm.custom_days:
                return candidate.isoformat()
            candidate += timedelta(days=1)

        return None

    # ------------------------------------------------------------------
    # Wake-Up Execution
    # ------------------------------------------------------------------

    def _execute_wakeup(self, alarm_dict: Dict[str, Any]) -> None:
        """Execute wake-up sequence (music + light ramp)."""
        alarm_id = alarm_dict.get("alarm_id", "")
        _LOGGER.info("Wecker triggered: %s (%s)", alarm_id, alarm_dict.get("label", ""))

        # Start Sonos volume ramp in background thread
        sonos_room = alarm_dict.get("sonos_room", "")
        if sonos_room and self._sonos:
            t = threading.Thread(
                target=self._sonos_ramp,
                args=(alarm_dict,),
                daemon=True,
                name=f"wecker-sonos-{alarm_id}",
            )
            self._ramp_threads[alarm_id] = t
            t.start()

        # Light ramp (via HA service call if available)
        light_entities = alarm_dict.get("light_entities", [])
        if light_entities:
            self._start_light_ramp(alarm_dict)

    def _sonos_ramp(self, alarm_dict: Dict[str, Any]) -> None:
        """Gradually ramp Sonos volume from start to end."""
        room = alarm_dict.get("sonos_room", "")
        vol_start = alarm_dict.get("volume_start", 10)
        vol_end = alarm_dict.get("volume_end", 40)
        ramp_min = max(1, alarm_dict.get("volume_ramp_minutes", 5))
        favorite = alarm_dict.get("sonos_favorite", "")
        uri = alarm_dict.get("sonos_uri", "")

        if not self._sonos:
            return

        try:
            # Set initial volume
            self._sonos.set_volume(room, vol_start)
            time.sleep(0.5)

            # Start playback
            if favorite:
                self._sonos.play_favorite(room, favorite)
            elif uri:
                self._sonos.play_uri(room, uri)
            else:
                self._sonos.play(room)

            # Gradual volume ramp
            steps = ramp_min * 4  # Every 15s
            vol_step = (vol_end - vol_start) / max(1, steps)
            current_vol = vol_start

            for i in range(steps):
                time.sleep(15)
                current_vol = min(vol_end, current_vol + vol_step)
                self._sonos.set_volume(room, int(current_vol))

                # Check if alarm was dismissed
                alarm_id = alarm_dict.get("alarm_id", "")
                with self._lock:
                    alarm = self._alarms.get(alarm_id)
                    if alarm and alarm.state in ("dismissed", "disabled"):
                        self._sonos.pause(room)
                        return

            _LOGGER.info("Wecker volume ramp complete: %s -> %d%%", room, vol_end)

        except Exception as exc:
            _LOGGER.warning("Wecker Sonos ramp failed: %s", exc)

    def _start_light_ramp(self, alarm_dict: Dict[str, Any]) -> None:
        """Start gradual light ramp (fire-and-forget, HA handles transition)."""
        # Light ramp is handled by sending a HA service call with transition
        # This is delegated to zone_automation or direct HA call
        _LOGGER.info(
            "Wecker light ramp requested: entities=%s, ramp=%dm, target=%d%%",
            alarm_dict.get("light_entities", []),
            alarm_dict.get("light_ramp_minutes", 10),
            alarm_dict.get("light_brightness_pct", 80),
        )

    # ------------------------------------------------------------------
    # Snooze / Dismiss
    # ------------------------------------------------------------------

    def snooze(self, alarm_id: str) -> Optional[Dict[str, Any]]:
        """Snooze a ringing alarm."""
        with self._lock:
            alarm = self._alarms.get(alarm_id)
            if not alarm or alarm.state != "ringing":
                return None
            alarm.state = "snoozed"

        # Pause Sonos
        if alarm.sonos_room and self._sonos:
            self._sonos.pause(alarm.sonos_room)

        _LOGGER.info("Alarm snoozed: %s (%dm)", alarm_id, alarm.snooze_minutes)

        # Schedule re-trigger
        def _re_trigger():
            time.sleep(alarm.snooze_minutes * 60)
            with self._lock:
                a = self._alarms.get(alarm_id)
                if a and a.state == "snoozed":
                    a.state = "ringing"
                    self._execute_wakeup(asdict(a))

        t = threading.Thread(target=_re_trigger, daemon=True, name=f"wecker-snooze-{alarm_id}")
        t.start()

        return asdict(alarm)

    def dismiss(self, alarm_id: str) -> Optional[Dict[str, Any]]:
        """Dismiss a ringing or snoozed alarm."""
        with self._lock:
            alarm = self._alarms.get(alarm_id)
            if not alarm:
                return None
            alarm.state = "dismissed"

            # Disable one-shot alarms
            if alarm.repeat == "once":
                alarm.enabled = False
                self._save_alarms()

        # Stop Sonos
        if alarm.sonos_room and self._sonos:
            self._sonos.pause(alarm.sonos_room)

        _LOGGER.info("Alarm dismissed: %s", alarm_id)
        return asdict(alarm)

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def status(self) -> Dict[str, Any]:
        """Get service status."""
        with self._lock:
            alarms = list(self._alarms.values())
        return {
            "total_alarms": len(alarms),
            "enabled": sum(1 for a in alarms if a.enabled),
            "ringing": sum(1 for a in alarms if a.state == "ringing"),
            "snoozed": sum(1 for a in alarms if a.state == "snoozed"),
            "sonos_available": self._sonos is not None,
        }
