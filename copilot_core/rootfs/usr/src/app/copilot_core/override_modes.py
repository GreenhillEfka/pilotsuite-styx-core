"""Override Modes System -- House-wide and per-zone automation overrides.

Provides named override modes (Party, Vacation, Sleep, Eco, Guest, etc.)
that modify the behavior of all automation subsystems:

- **Party Mode**: Manual light/music control, fixed heating temp, no auto-dimming
- **Vacation Mode**: Lower heating, alarm on presence detection, simulate occupancy
- **Sleep Mode**: Per-zone (children/adults), suppress music, dim lights, lower heating
- **Eco Mode**: Minimize energy, aggressive standby, lower heating
- **Guest Mode**: Simplified automations, privacy-aware

Each mode has:
- Priority (higher priority overrides lower)
- Per-zone applicability (some modes affect specific zones only)
- Subsystem consequences (what each mode does to light/music/heating/presence)
- Timeout (optional auto-deactivation)

Persistence: /data/override_modes.json
Thread-safety: all mutable state protected by _lock.
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
from typing import Any, Callable, Optional

_LOGGER = logging.getLogger(__name__)

_DATA_DIR = Path(os.environ.get("OVERRIDE_MODES_DATA_DIR", "/data"))
_CONFIG_FILE = _DATA_DIR / "override_modes.json"


# ---- Built-in Mode Definitions ------------------------------------------------

@dataclass
class ModeConsequence:
    """What a mode does to a specific subsystem."""
    music_auto: bool = True           # Allow automatic music control
    music_manual_override: bool = False  # User controls music manually
    music_mute: bool = False          # Mute all music in affected zones
    light_auto: bool = True           # Allow automatic light control
    light_manual_override: bool = False  # User controls lights manually
    light_max_brightness_pct: int = 100  # Cap brightness
    light_color_temp_override_k: int = 0  # 0 = no override
    heating_auto: bool = True         # Allow automatic heating
    heating_target_temp_c: float = 0.0  # 0 = no override, >0 = fixed temp
    presence_auto: bool = True        # Allow presence-based automations
    presence_alarm: bool = False      # Trigger alarm on presence detection
    presence_simulate: bool = False   # Simulate occupancy (lights/blinds)
    notify_on_presence: bool = False  # Send notification on presence

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ModeConsequence:
        known = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


@dataclass
class ModeDefinition:
    """Definition of an override mode."""
    mode_id: str
    name: str
    description: str = ""
    icon: str = "mdi:toggle-switch"
    priority: int = 50  # 0=lowest, 100=highest
    consequences: ModeConsequence = field(default_factory=ModeConsequence)
    builtin: bool = False
    # Zone applicability: empty = all zones, otherwise specific zone_ids
    applicable_zones: list[str] = field(default_factory=list)
    # Auto-timeout in seconds (0 = no timeout)
    auto_timeout_s: int = 0
    # Conflict rules: list of mode_ids that this mode overrides
    overrides_modes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ModeDefinition:
        known = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {}
        for k, v in data.items():
            if k in known:
                if k == "consequences" and isinstance(v, dict):
                    filtered[k] = ModeConsequence.from_dict(v)
                else:
                    filtered[k] = v
        return cls(**filtered)


@dataclass
class ActiveMode:
    """Runtime state of an active override mode."""
    mode_id: str
    activated_at: float = 0.0
    activated_by: str = ""  # "user", "automation", "schedule"
    expires_at: float = 0.0  # 0 = no expiry
    zone_ids: list[str] = field(default_factory=list)  # empty = all zones

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ActiveMode:
        known = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


# ---- Built-in mode presets ---------------------------------------------------

_BUILTIN_MODES: list[ModeDefinition] = [
    ModeDefinition(
        mode_id="party",
        name="Partymodus",
        description="Manuelle Licht- und Musiksteuerung, feste Heizungstemperatur",
        icon="mdi:party-popper",
        priority=80,
        builtin=True,
        consequences=ModeConsequence(
            music_auto=False,
            music_manual_override=True,
            light_auto=False,
            light_manual_override=True,
            heating_auto=False,
            heating_target_temp_c=22.0,
            presence_auto=False,
        ),
        overrides_modes=["sleep", "eco"],
    ),
    ModeDefinition(
        mode_id="vacation",
        name="Urlaubsmodus",
        description="Heizung absenken, Alarm bei Präsenz, Anwesenheitssimulation",
        icon="mdi:airplane",
        priority=90,
        builtin=True,
        consequences=ModeConsequence(
            music_auto=False,
            music_mute=True,
            light_auto=False,
            heating_auto=False,
            heating_target_temp_c=16.0,
            presence_alarm=True,
            presence_simulate=True,
            notify_on_presence=True,
        ),
        overrides_modes=["party", "sleep", "eco", "guest"],
    ),
    ModeDefinition(
        mode_id="sleep",
        name="Schlafmodus",
        description="Keine Musik, gedimmtes Licht, abgesenkte Heizung",
        icon="mdi:sleep",
        priority=70,
        builtin=True,
        consequences=ModeConsequence(
            music_auto=False,
            music_mute=True,
            light_auto=True,
            light_max_brightness_pct=20,
            light_color_temp_override_k=2200,
            heating_auto=False,
            heating_target_temp_c=18.0,
        ),
    ),
    ModeDefinition(
        mode_id="children_sleep",
        name="Kinder schlafen",
        description="Kein Musikwolke in Kinderzimmern, leise im ganzen Haus",
        icon="mdi:baby-face-outline",
        priority=75,
        builtin=True,
        consequences=ModeConsequence(
            music_auto=False,
            music_mute=True,
            light_auto=True,
            light_max_brightness_pct=30,
            light_color_temp_override_k=2400,
        ),
        # Zone-specific: only applicable zones will be set when activated
    ),
    ModeDefinition(
        mode_id="eco",
        name="Eco-Modus",
        description="Energiesparen: niedrigere Heizung, Standby reduzieren",
        icon="mdi:leaf",
        priority=40,
        builtin=True,
        consequences=ModeConsequence(
            music_auto=True,
            light_auto=True,
            light_max_brightness_pct=70,
            heating_auto=False,
            heating_target_temp_c=19.0,
        ),
    ),
    ModeDefinition(
        mode_id="guest",
        name="Gästemodus",
        description="Vereinfachte Automatisierungen, Privatsphäre",
        icon="mdi:account-group",
        priority=50,
        builtin=True,
        consequences=ModeConsequence(
            music_auto=True,
            light_auto=True,
            presence_auto=True,
        ),
    ),
]


# ---- Service -----------------------------------------------------------------

class OverrideModesService:
    """Manages house-wide and per-zone override modes.

    Thread-safe, persistent, with EventBus integration.
    """

    def __init__(
        self,
        event_bus: Any = None,
        data_dir: str | None = None,
    ) -> None:
        self._lock = threading.Lock()
        self._event_bus = event_bus

        if data_dir is not None:
            self._data_dir = Path(data_dir)
        else:
            self._data_dir = _DATA_DIR
        self._config_file = self._data_dir / "override_modes.json"

        # Mode definitions: mode_id -> ModeDefinition
        self._definitions: dict[str, ModeDefinition] = {}

        # Active modes: mode_id -> ActiveMode
        self._active_modes: dict[str, ActiveMode] = {}

        # Mode change callbacks
        self._callbacks: list[Callable] = []

        # Load built-in modes
        for m in _BUILTIN_MODES:
            self._definitions[m.mode_id] = m

        # Load persisted state
        self._load()

        _LOGGER.info(
            "OverrideModesService initialized (%d definitions, %d active)",
            len(self._definitions),
            len(self._active_modes),
        )

    # ---- Persistence -------------------------------------------------------

    def _load(self) -> None:
        try:
            if self._config_file.exists():
                with open(self._config_file, "r", encoding="utf-8") as fh:
                    data = json.load(fh)

                # Load custom mode definitions
                for md_data in data.get("custom_definitions", []):
                    try:
                        md = ModeDefinition.from_dict(md_data)
                        md.builtin = False
                        self._definitions[md.mode_id] = md
                    except Exception:
                        _LOGGER.exception("Failed to load custom mode: %s", md_data)

                # Restore active modes
                for am_data in data.get("active_modes", []):
                    try:
                        am = ActiveMode.from_dict(am_data)
                        # Check if expired
                        if am.expires_at > 0 and am.expires_at < time.time():
                            continue
                        if am.mode_id in self._definitions:
                            self._active_modes[am.mode_id] = am
                    except Exception:
                        _LOGGER.exception("Failed to restore active mode: %s", am_data)

                _LOGGER.info(
                    "Loaded override modes: %d custom defs, %d active",
                    len(data.get("custom_definitions", [])),
                    len(self._active_modes),
                )
        except FileNotFoundError:
            pass
        except Exception:
            _LOGGER.exception("Failed to load override modes from %s", self._config_file)

    def _save(self) -> None:
        try:
            self._data_dir.mkdir(parents=True, exist_ok=True)
            custom_defs = [
                d.to_dict() for d in self._definitions.values()
                if not d.builtin
            ]
            active = [am.to_dict() for am in self._active_modes.values()]

            data = {
                "custom_definitions": custom_defs,
                "active_modes": active,
                "saved_at": time.time(),
            }
            with open(self._config_file, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, ensure_ascii=False)
        except Exception:
            _LOGGER.exception("Failed to save override modes")

    # ---- Mode definitions --------------------------------------------------

    def get_all_definitions(self) -> list[dict[str, Any]]:
        with self._lock:
            return [d.to_dict() for d in self._definitions.values()]

    def get_definition(self, mode_id: str) -> dict[str, Any] | None:
        with self._lock:
            d = self._definitions.get(mode_id)
            return d.to_dict() if d else None

    def create_custom_mode(self, data: dict[str, Any]) -> dict[str, Any]:
        mode_id = str(data.get("mode_id", "")).strip()
        if not mode_id:
            return {"ok": False, "error": "Missing mode_id"}
        if mode_id in self._definitions and self._definitions[mode_id].builtin:
            return {"ok": False, "error": f"Cannot overwrite built-in mode '{mode_id}'"}

        with self._lock:
            md = ModeDefinition.from_dict(data)
            md.builtin = False
            self._definitions[md.mode_id] = md
            self._save()

        return {"ok": True, "mode": md.to_dict()}

    def delete_custom_mode(self, mode_id: str) -> dict[str, Any]:
        with self._lock:
            d = self._definitions.get(mode_id)
            if d is None:
                return {"ok": False, "error": f"Mode '{mode_id}' not found"}
            if d.builtin:
                return {"ok": False, "error": f"Cannot delete built-in mode '{mode_id}'"}
            del self._definitions[mode_id]
            self._active_modes.pop(mode_id, None)
            self._save()
        return {"ok": True}

    # ---- Activate / Deactivate --------------------------------------------

    def activate_mode(
        self,
        mode_id: str,
        zone_ids: list[str] | None = None,
        activated_by: str = "user",
        timeout_s: int = 0,
    ) -> dict[str, Any]:
        now = time.time()
        with self._lock:
            definition = self._definitions.get(mode_id)
            if definition is None:
                return {"ok": False, "error": f"Unknown mode '{mode_id}'"}

            # Deactivate modes that this one overrides
            for override_id in definition.overrides_modes:
                if override_id in self._active_modes:
                    self._active_modes.pop(override_id)
                    _LOGGER.info("Mode '%s' deactivated by '%s' (priority override)", override_id, mode_id)

            # Check for higher-priority conflicts
            for active_id, active_mode in list(self._active_modes.items()):
                active_def = self._definitions.get(active_id)
                if active_def and active_def.priority > definition.priority:
                    if mode_id in active_def.overrides_modes:
                        return {
                            "ok": False,
                            "error": f"Mode '{active_id}' (priority {active_def.priority}) blocks '{mode_id}' (priority {definition.priority})",
                        }

            # Determine effective timeout
            effective_timeout = timeout_s or definition.auto_timeout_s
            expires_at = (now + effective_timeout) if effective_timeout > 0 else 0.0

            # Determine effective zones
            effective_zones = zone_ids if zone_ids else list(definition.applicable_zones)

            am = ActiveMode(
                mode_id=mode_id,
                activated_at=now,
                activated_by=activated_by,
                expires_at=expires_at,
                zone_ids=effective_zones,
            )
            self._active_modes[mode_id] = am
            self._save()

        # Publish event
        self._publish_event("override_mode.activated", {
            "mode_id": mode_id,
            "name": definition.name,
            "priority": definition.priority,
            "zone_ids": effective_zones,
            "activated_by": activated_by,
            "expires_at": expires_at,
        })

        # Fire callbacks
        self._fire_callbacks(mode_id, "activated")

        _LOGGER.info(
            "Override mode '%s' activated (by=%s, zones=%s, expires=%s)",
            mode_id, activated_by,
            effective_zones or "all",
            datetime.fromtimestamp(expires_at, tz=timezone.utc).isoformat() if expires_at else "never",
        )

        return {"ok": True, "mode": am.to_dict(), "definition": definition.to_dict()}

    def deactivate_mode(self, mode_id: str) -> dict[str, Any]:
        with self._lock:
            am = self._active_modes.pop(mode_id, None)
            if am is None:
                return {"ok": False, "error": f"Mode '{mode_id}' is not active"}
            self._save()

        self._publish_event("override_mode.deactivated", {
            "mode_id": mode_id,
        })
        self._fire_callbacks(mode_id, "deactivated")

        _LOGGER.info("Override mode '%s' deactivated", mode_id)
        return {"ok": True, "mode_id": mode_id}

    def toggle_mode(
        self,
        mode_id: str,
        zone_ids: list[str] | None = None,
        activated_by: str = "user",
    ) -> dict[str, Any]:
        with self._lock:
            is_active = mode_id in self._active_modes

        if is_active:
            return self.deactivate_mode(mode_id)
        else:
            return self.activate_mode(mode_id, zone_ids=zone_ids, activated_by=activated_by)

    # ---- Query active modes ------------------------------------------------

    def get_active_modes(self) -> list[dict[str, Any]]:
        now = time.time()
        expired = []
        result = []

        with self._lock:
            for mode_id, am in self._active_modes.items():
                if am.expires_at > 0 and am.expires_at < now:
                    expired.append(mode_id)
                    continue
                definition = self._definitions.get(mode_id)
                result.append({
                    **am.to_dict(),
                    "definition": definition.to_dict() if definition else {},
                })

        # Clean up expired modes
        if expired:
            with self._lock:
                for mid in expired:
                    self._active_modes.pop(mid, None)
                self._save()
            for mid in expired:
                self._publish_event("override_mode.expired", {"mode_id": mid})
                self._fire_callbacks(mid, "expired")
                _LOGGER.info("Override mode '%s' expired", mid)

        return result

    def is_mode_active(self, mode_id: str) -> bool:
        with self._lock:
            am = self._active_modes.get(mode_id)
            if am is None:
                return False
            if am.expires_at > 0 and am.expires_at < time.time():
                return False
            return True

    def get_effective_consequences(self, zone_id: str = "") -> dict[str, Any]:
        """Get the merged consequences for a zone from all active modes.

        Higher-priority modes override lower-priority ones.
        Zone-specific modes only apply to their configured zones.

        Parameters
        ----------
        zone_id : str
            Zone to check. Empty string = house-wide.

        Returns
        -------
        dict
            Merged consequence values from all active modes.
        """
        now = time.time()
        applicable_modes: list[tuple[int, ModeDefinition, ActiveMode]] = []

        with self._lock:
            for mode_id, am in self._active_modes.items():
                if am.expires_at > 0 and am.expires_at < now:
                    continue
                definition = self._definitions.get(mode_id)
                if definition is None:
                    continue

                # Check zone applicability
                if am.zone_ids and zone_id and zone_id not in am.zone_ids:
                    continue

                applicable_modes.append((definition.priority, definition, am))

        # Sort by priority (lowest first, highest last = highest wins)
        applicable_modes.sort(key=lambda x: x[0])

        # Merge consequences
        merged = ModeConsequence()
        active_mode_ids: list[str] = []
        highest_priority_mode = ""

        for _prio, definition, _am in applicable_modes:
            cons = definition.consequences
            # Apply: higher priority modes overwrite
            if not cons.music_auto:
                merged.music_auto = False
            if cons.music_manual_override:
                merged.music_manual_override = True
            if cons.music_mute:
                merged.music_mute = True
            if not cons.light_auto:
                merged.light_auto = False
            if cons.light_manual_override:
                merged.light_manual_override = True
            if cons.light_max_brightness_pct < merged.light_max_brightness_pct:
                merged.light_max_brightness_pct = cons.light_max_brightness_pct
            if cons.light_color_temp_override_k > 0:
                merged.light_color_temp_override_k = cons.light_color_temp_override_k
            if not cons.heating_auto:
                merged.heating_auto = False
            if cons.heating_target_temp_c > 0:
                merged.heating_target_temp_c = cons.heating_target_temp_c
            if not cons.presence_auto:
                merged.presence_auto = False
            if cons.presence_alarm:
                merged.presence_alarm = True
            if cons.presence_simulate:
                merged.presence_simulate = True
            if cons.notify_on_presence:
                merged.notify_on_presence = True

            active_mode_ids.append(definition.mode_id)
            highest_priority_mode = definition.mode_id

        return {
            "zone_id": zone_id,
            "active_modes": active_mode_ids,
            "highest_priority_mode": highest_priority_mode,
            "consequences": merged.to_dict(),
            "music_allowed": merged.music_auto and not merged.music_mute,
            "light_allowed": merged.light_auto,
            "heating_allowed": merged.heating_auto,
            "presence_automation_allowed": merged.presence_auto,
        }

    # ---- Callbacks ---------------------------------------------------------

    def on_mode_change(self, callback: Callable) -> None:
        self._callbacks.append(callback)

    def _fire_callbacks(self, mode_id: str, action: str) -> None:
        for cb in self._callbacks:
            try:
                cb(mode_id, action)
            except Exception:
                _LOGGER.debug("Mode change callback failed for %s/%s", mode_id, action)

    # ---- EventBus ----------------------------------------------------------

    def _publish_event(self, topic: str, data: dict[str, Any]) -> None:
        if self._event_bus is not None:
            try:
                self._event_bus.publish(topic, data, source="override_modes")
            except Exception:
                _LOGGER.debug("Failed to publish event %s", topic)

    # ---- Status ------------------------------------------------------------

    def get_status(self) -> dict[str, Any]:
        active = self.get_active_modes()
        return {
            "ok": True,
            "active_modes": active,
            "active_count": len(active),
            "total_definitions": len(self._definitions),
            "definitions": self.get_all_definitions(),
        }


__all__ = [
    "OverrideModesService",
    "ModeDefinition",
    "ModeConsequence",
    "ActiveMode",
]
