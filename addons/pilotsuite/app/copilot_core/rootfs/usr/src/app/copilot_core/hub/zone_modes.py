"""Zone Modes — Party/Sleep/Custom Quick-Switches (v6.6.0).

Features:
- Predefined zone modes with automation suppression rules
- Timer-based auto-revert (e.g. Party mode for 3 hours)
- Per-zone mode stacking (current + scheduled)
- Quick-toggle switches for common modes
- Kinderschlafmodus, Partymodus, Filmeabend, Gästemodus, etc.
- Mode history for learning common patterns
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)


# ── Data models ─────────────────────────────────────────────────────────────


@dataclass
class ModeDefinition:
    """Definition of a zone mode."""

    mode_id: str
    name_de: str
    name_en: str
    icon: str
    suppress_automations: bool = False
    suppress_lights: bool = False
    suppress_media: bool = False
    suppress_notifications: bool = False
    max_volume_pct: int | None = None  # None = no limit
    min_brightness_pct: int | None = None
    max_brightness_pct: int | None = None
    color_temp_k: int | None = None
    default_duration_min: int | None = None  # None = indefinite
    description_de: str = ""


@dataclass
class ActiveMode:
    """An active mode on a zone."""

    mode_id: str
    zone_id: str
    activated_at: datetime
    expires_at: datetime | None = None
    activated_by: str = "user"  # user, automation, schedule
    priority: int = 0


@dataclass
class ModeEvent:
    """A mode change event for history."""

    zone_id: str
    mode_id: str
    action: str  # activated, deactivated, expired, overridden
    timestamp: datetime
    duration_min: float = 0


@dataclass
class ZoneModeStatus:
    """Current mode status for a zone."""

    zone_id: str
    active_mode: str | None = None
    mode_name_de: str | None = None
    icon: str = "mdi:home"
    expires_at: datetime | None = None
    remaining_min: float | None = None
    suppressed: dict[str, bool] = field(default_factory=dict)
    restrictions: dict[str, Any] = field(default_factory=dict)


@dataclass
class ModeOverview:
    """Overview of all zone modes."""

    total_zones_with_modes: int = 0
    active_modes: list[dict[str, Any]] = field(default_factory=list)
    available_modes: list[dict[str, Any]] = field(default_factory=list)
    recent_events: list[dict[str, Any]] = field(default_factory=list)


# ── Predefined modes ───────────────────────────────────────────────────────

_BUILTIN_MODES: dict[str, ModeDefinition] = {
    "party": ModeDefinition(
        mode_id="party",
        name_de="Partymodus",
        name_en="Party Mode",
        icon="mdi:party-popper",
        suppress_automations=True,
        suppress_lights=False,
        suppress_notifications=True,
        max_volume_pct=None,  # no limit during party
        default_duration_min=180,
        description_de="Alle Automationen pausiert — Licht und Musik bleiben an",
    ),
    "kids_sleep": ModeDefinition(
        mode_id="kids_sleep",
        name_de="Kinderschlafmodus",
        name_en="Kids Sleep Mode",
        icon="mdi:baby-face-outline",
        suppress_automations=True,
        suppress_lights=True,
        suppress_media=True,
        suppress_notifications=True,
        max_volume_pct=20,
        max_brightness_pct=10,
        color_temp_k=2200,
        default_duration_min=None,
        description_de="Licht gedimmt, Medien leise, Automationen pausiert",
    ),
    "movie": ModeDefinition(
        mode_id="movie",
        name_de="Filmeabend",
        name_en="Movie Night",
        icon="mdi:movie-open",
        suppress_automations=True,
        suppress_lights=False,
        suppress_notifications=True,
        max_brightness_pct=15,
        color_temp_k=2500,
        default_duration_min=180,
        description_de="Licht gedimmt, keine Benachrichtigungen",
    ),
    "guest": ModeDefinition(
        mode_id="guest",
        name_de="Gästemodus",
        name_en="Guest Mode",
        icon="mdi:account-group",
        suppress_automations=False,
        suppress_notifications=False,
        default_duration_min=480,
        description_de="Erweiterte Zugriffsrechte für Gäste",
    ),
    "focus": ModeDefinition(
        mode_id="focus",
        name_de="Fokusmodus",
        name_en="Focus Mode",
        icon="mdi:head-lightbulb",
        suppress_automations=True,
        suppress_media=True,
        suppress_notifications=True,
        max_volume_pct=10,
        min_brightness_pct=70,
        color_temp_k=4500,
        default_duration_min=120,
        description_de="Medien aus, Benachrichtigungen stumm, helles Licht",
    ),
    "away": ModeDefinition(
        mode_id="away",
        name_de="Abwesend",
        name_en="Away Mode",
        icon="mdi:home-export-outline",
        suppress_automations=False,
        suppress_lights=True,
        suppress_media=True,
        default_duration_min=None,
        description_de="Licht und Medien aus, Sicherheitsautomationen aktiv",
    ),
    "night": ModeDefinition(
        mode_id="night",
        name_de="Nachtmodus",
        name_en="Night Mode",
        icon="mdi:weather-night",
        suppress_automations=True,
        suppress_lights=True,
        suppress_media=True,
        suppress_notifications=True,
        max_volume_pct=5,
        max_brightness_pct=5,
        color_temp_k=2200,
        default_duration_min=None,
        description_de="Alles aus, minimale Orientierungsbeleuchtung",
    ),
    "romantic": ModeDefinition(
        mode_id="romantic",
        name_de="Romantik",
        name_en="Romantic Mode",
        icon="mdi:heart",
        suppress_automations=True,
        suppress_notifications=True,
        max_brightness_pct=30,
        color_temp_k=2200,
        default_duration_min=120,
        description_de="Warmes gedimmtes Licht, keine Störungen",
    ),
}


# ── Engine ──────────────────────────────────────────────────────────────────


class ZoneModeEngine:
    """Engine for managing zone modes with quick-toggle support."""

    def __init__(self) -> None:
        self._modes: dict[str, ModeDefinition] = dict(_BUILTIN_MODES)
        self._active: dict[str, ActiveMode] = {}  # zone_id -> ActiveMode
        self._history: list[ModeEvent] = []

    # ── Mode activation ─────────────────────────────────────────────────

    def activate_mode(self, zone_id: str, mode_id: str,
                      duration_min: int | None = None,
                      activated_by: str = "user") -> bool:
        """Activate a mode on a zone.

        Args:
            zone_id: The zone to set the mode on.
            mode_id: The mode to activate.
            duration_min: Override duration. None uses mode default.
            activated_by: Who activated it (user, automation, schedule).
        """
        mode_def = self._modes.get(mode_id)
        if not mode_def:
            return False

        now = datetime.now(tz=timezone.utc)

        # Deactivate current mode if any
        if zone_id in self._active:
            self._deactivate_mode(zone_id, "overridden")

        # Calculate expiry
        dur = duration_min if duration_min is not None else mode_def.default_duration_min
        expires = now + timedelta(minutes=dur) if dur else None

        active = ActiveMode(
            mode_id=mode_id,
            zone_id=zone_id,
            activated_at=now,
            expires_at=expires,
            activated_by=activated_by,
        )
        self._active[zone_id] = active

        self._history.append(ModeEvent(
            zone_id=zone_id,
            mode_id=mode_id,
            action="activated",
            timestamp=now,
        ))

        logger.info("Zone '%s' → %s (Dauer: %s)",
                     zone_id, mode_def.name_de,
                     f"{dur} min" if dur else "unbegrenzt")
        return True

    def deactivate_mode(self, zone_id: str) -> bool:
        """Deactivate the current mode on a zone."""
        if zone_id not in self._active:
            return False
        self._deactivate_mode(zone_id, "deactivated")
        return True

    def _deactivate_mode(self, zone_id: str, action: str) -> None:
        """Internal deactivation."""
        active = self._active.pop(zone_id, None)
        if active:
            now = datetime.now(tz=timezone.utc)
            duration = (now - active.activated_at).total_seconds() / 60
            self._history.append(ModeEvent(
                zone_id=zone_id,
                mode_id=active.mode_id,
                action=action,
                timestamp=now,
                duration_min=round(duration, 1),
            ))

    def check_expirations(self) -> list[str]:
        """Check and expire timed-out modes.

        Returns list of zone_ids that expired.
        """
        now = datetime.now(tz=timezone.utc)
        expired = []

        for zone_id in list(self._active.keys()):
            active = self._active[zone_id]
            if active.expires_at and now >= active.expires_at:
                self._deactivate_mode(zone_id, "expired")
                expired.append(zone_id)

        return expired

    # ── Query ───────────────────────────────────────────────────────────

    def get_zone_status(self, zone_id: str) -> ZoneModeStatus:
        """Get current mode status for a zone."""
        active = self._active.get(zone_id)
        if not active:
            return ZoneModeStatus(zone_id=zone_id)

        mode_def = self._modes.get(active.mode_id)
        if not mode_def:
            return ZoneModeStatus(zone_id=zone_id)

        now = datetime.now(tz=timezone.utc)
        remaining = None
        if active.expires_at:
            remaining = max(0, (active.expires_at - now).total_seconds() / 60)

        return ZoneModeStatus(
            zone_id=zone_id,
            active_mode=active.mode_id,
            mode_name_de=mode_def.name_de,
            icon=mode_def.icon,
            expires_at=active.expires_at,
            remaining_min=round(remaining, 1) if remaining is not None else None,
            suppressed={
                "automations": mode_def.suppress_automations,
                "lights": mode_def.suppress_lights,
                "media": mode_def.suppress_media,
                "notifications": mode_def.suppress_notifications,
            },
            restrictions={
                k: v for k, v in {
                    "max_volume_pct": mode_def.max_volume_pct,
                    "min_brightness_pct": mode_def.min_brightness_pct,
                    "max_brightness_pct": mode_def.max_brightness_pct,
                    "color_temp_k": mode_def.color_temp_k,
                }.items() if v is not None
            },
        )

    def is_suppressed(self, zone_id: str, category: str) -> bool:
        """Check if a category is suppressed in a zone.

        Args:
            category: "automations", "lights", "media", "notifications"
        """
        active = self._active.get(zone_id)
        if not active:
            return False
        mode_def = self._modes.get(active.mode_id)
        if not mode_def:
            return False
        return getattr(mode_def, f"suppress_{category}", False)

    def get_restriction(self, zone_id: str, key: str) -> Any:
        """Get a restriction value for a zone (e.g. max_volume_pct)."""
        active = self._active.get(zone_id)
        if not active:
            return None
        mode_def = self._modes.get(active.mode_id)
        if not mode_def:
            return None
        return getattr(mode_def, key, None)

    def get_overview(self) -> ModeOverview:
        """Get overview of all zone modes."""
        active_list = []
        for zone_id, active in self._active.items():
            status = self.get_zone_status(zone_id)
            active_list.append({
                "zone_id": zone_id,
                "mode_id": active.mode_id,
                "mode_name_de": status.mode_name_de,
                "icon": status.icon,
                "remaining_min": status.remaining_min,
                "activated_by": active.activated_by,
            })

        available = [
            {
                "mode_id": m.mode_id,
                "name_de": m.name_de,
                "name_en": m.name_en,
                "icon": m.icon,
                "description_de": m.description_de,
                "default_duration_min": m.default_duration_min,
            }
            for m in self._modes.values()
        ]

        recent = []
        for event in self._history[-20:]:
            recent.append({
                "zone_id": event.zone_id,
                "mode_id": event.mode_id,
                "action": event.action,
                "timestamp": event.timestamp.isoformat(),
                "duration_min": event.duration_min,
            })

        return ModeOverview(
            total_zones_with_modes=len(self._active),
            active_modes=active_list,
            available_modes=available,
            recent_events=list(reversed(recent)),
        )

    def get_available_modes(self) -> list[dict[str, Any]]:
        """Get all available mode definitions."""
        return [
            {
                "mode_id": m.mode_id,
                "name_de": m.name_de,
                "name_en": m.name_en,
                "icon": m.icon,
                "description_de": m.description_de,
                "default_duration_min": m.default_duration_min,
                "suppresses": {
                    "automations": m.suppress_automations,
                    "lights": m.suppress_lights,
                    "media": m.suppress_media,
                    "notifications": m.suppress_notifications,
                },
            }
            for m in self._modes.values()
        ]

    # ── Custom modes ────────────────────────────────────────────────────

    def register_custom_mode(self, mode_id: str, name_de: str, name_en: str = "",
                              icon: str = "mdi:cog", **kwargs: Any) -> bool:
        """Register a custom mode."""
        if mode_id in self._modes:
            return False
        self._modes[mode_id] = ModeDefinition(
            mode_id=mode_id,
            name_de=name_de,
            name_en=name_en or name_de,
            icon=icon,
            **kwargs,
        )
        return True
