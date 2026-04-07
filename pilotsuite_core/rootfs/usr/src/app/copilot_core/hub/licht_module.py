"""Lichtmodul — Intelligente Lichtsteuerung pro Zone (v1.0.0).

Steuert Lichter basierend auf Praesenz, Tageszeit und Helligkeitssensoren.
Bietet automatische Szenen, Dimmkurven und Override-Management.

Features:
- Praesenzbasiertes Ein-/Ausschalten mit konfigurierbarem Delay
- Tageszeit-adaptive Farbtemperatur und Helligkeit
- Override-Erkennung (manuell > automatisch)
- Gruppierte Lichtsteuerung pro Zone
- LLM-Kontext fuer Sprachsteuerung
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class LightEntity:
    """Tracked light entity."""

    entity_id: str
    zone_id: str = ""
    friendly_name: str = ""
    is_on: bool = False
    brightness_pct: int = 0
    color_temp_k: int = 0
    rgb_color: tuple[int, int, int] | None = None
    last_changed: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    is_override: bool = False


@dataclass
class ZoneLightState:
    """Aggregated light state for a zone."""

    zone_id: str
    zone_name: str = ""
    lights_on: int = 0
    lights_total: int = 0
    avg_brightness_pct: float = 0.0
    any_override: bool = False
    target_brightness_pct: int = 100
    target_color_temp_k: int = 4000
    auto_enabled: bool = True


@dataclass
class LichtDashboard:
    """Complete light module dashboard."""

    zones: list[dict[str, Any]] = field(default_factory=list)
    total_lights: int = 0
    lights_on: int = 0
    overrides_active: int = 0
    auto_mode_zones: int = 0


# Tageszeit-Profile (Stunde -> brightness_pct, color_temp_k)
_TIME_PROFILES: dict[str, tuple[int, int]] = {
    "night": (5, 2200),
    "morning": (60, 3500),
    "day": (100, 5000),
    "evening": (50, 2700),
    "late_evening": (30, 2500),
}


def _get_time_profile(hour: int) -> tuple[int, int]:
    """Get brightness and color temp for current hour."""
    if 6 <= hour < 9:
        return _TIME_PROFILES["morning"]
    elif 9 <= hour < 17:
        return _TIME_PROFILES["day"]
    elif 17 <= hour < 20:
        return _TIME_PROFILES["evening"]
    elif 20 <= hour < 22:
        return _TIME_PROFILES["late_evening"]
    else:
        return _TIME_PROFILES["night"]


class LichtModuleEngine:
    """Lichtmodul Engine — manages light entities per zone."""

    def __init__(self) -> None:
        self._lights: dict[str, LightEntity] = {}
        self._zone_config: dict[str, dict[str, Any]] = {}
        self._zone_names: dict[str, str] = {}

    def register_light(
        self, entity_id: str, zone_id: str, friendly_name: str = ""
    ) -> LightEntity:
        """Register a light entity for tracking."""
        light = LightEntity(
            entity_id=entity_id, zone_id=zone_id,
            friendly_name=friendly_name or entity_id,
        )
        self._lights[entity_id] = light
        logger.debug("Lichtmodul: registered %s in zone %s", entity_id, zone_id)
        return light

    def remove_light(self, entity_id: str) -> bool:
        """Remove a tracked light entity."""
        return self._lights.pop(entity_id, None) is not None

    def configure_zone(
        self, zone_id: str, zone_name: str = "",
        auto_enabled: bool = True,
        presence_delay_s: int = 30, absence_delay_s: int = 300,
    ) -> None:
        """Configure zone light automation."""
        self._zone_config[zone_id] = {
            "auto_enabled": auto_enabled,
            "presence_delay_s": presence_delay_s,
            "absence_delay_s": absence_delay_s,
        }
        if zone_name:
            self._zone_names[zone_id] = zone_name

    def update_light_state(
        self, entity_id: str, is_on: bool,
        brightness_pct: int = 0, color_temp_k: int = 0,
        rgb_color: tuple[int, int, int] | None = None,
    ) -> LightEntity | None:
        """Update the state of a tracked light."""
        light = self._lights.get(entity_id)
        if light is None:
            return None
        light.is_on = is_on
        light.brightness_pct = brightness_pct
        light.color_temp_k = color_temp_k
        light.rgb_color = rgb_color
        light.last_changed = datetime.now(tz=timezone.utc)
        return light

    def set_override(self, entity_id: str, override: bool = True) -> bool:
        """Set manual override for a light."""
        light = self._lights.get(entity_id)
        if light is None:
            return False
        light.is_override = override
        return True

    def clear_zone_overrides(self, zone_id: str) -> int:
        """Clear all overrides in a zone."""
        count = 0
        for light in self._lights.values():
            if light.zone_id == zone_id and light.is_override:
                light.is_override = False
                count += 1
        return count

    def get_zone_lights(self, zone_id: str) -> list[LightEntity]:
        """Get all lights in a zone."""
        return [l for l in self._lights.values() if l.zone_id == zone_id]

    def get_zone_state(self, zone_id: str) -> ZoneLightState:
        """Get aggregated light state for a zone."""
        lights = self.get_zone_lights(zone_id)
        on_lights = [l for l in lights if l.is_on]
        avg_brightness = (
            sum(l.brightness_pct for l in on_lights) / len(on_lights) if on_lights else 0.0
        )
        config = self._zone_config.get(zone_id, {})
        hour = datetime.now(tz=timezone.utc).hour
        target_brightness, target_temp = _get_time_profile(hour)

        return ZoneLightState(
            zone_id=zone_id,
            zone_name=self._zone_names.get(zone_id, zone_id),
            lights_on=len(on_lights), lights_total=len(lights),
            avg_brightness_pct=round(avg_brightness, 1),
            any_override=any(l.is_override for l in lights),
            target_brightness_pct=target_brightness,
            target_color_temp_k=target_temp,
            auto_enabled=config.get("auto_enabled", True),
        )

    def get_target_for_hour(self, hour: int | None = None) -> dict[str, Any]:
        """Get target brightness and color temp for a given hour."""
        if hour is None:
            hour = datetime.now(tz=timezone.utc).hour
        brightness, temp = _get_time_profile(hour)
        return {"brightness_pct": brightness, "color_temp_k": temp}

    def get_dashboard(self) -> LichtDashboard:
        """Get complete Lichtmodul dashboard."""
        zones_data = []
        zone_ids = set(l.zone_id for l in self._lights.values() if l.zone_id)
        for zone_id in sorted(zone_ids):
            state = self.get_zone_state(zone_id)
            zones_data.append({
                "zone_id": zone_id, "zone_name": state.zone_name,
                "lights_on": state.lights_on, "lights_total": state.lights_total,
                "avg_brightness_pct": state.avg_brightness_pct,
                "any_override": state.any_override,
                "auto_enabled": state.auto_enabled,
                "target_brightness_pct": state.target_brightness_pct,
                "target_color_temp_k": state.target_color_temp_k,
            })
        all_lights = list(self._lights.values())
        return LichtDashboard(
            zones=zones_data, total_lights=len(all_lights),
            lights_on=sum(1 for l in all_lights if l.is_on),
            overrides_active=sum(1 for l in all_lights if l.is_override),
            auto_mode_zones=sum(1 for z in zones_data if z["auto_enabled"]),
        )

    def get_summary(self) -> dict[str, Any]:
        """Summary for API responses."""
        d = self.get_dashboard()
        return {
            "total_lights": d.total_lights, "lights_on": d.lights_on,
            "overrides_active": d.overrides_active,
            "auto_mode_zones": d.auto_mode_zones, "zones": d.zones,
        }

    def get_context_for_llm(self) -> str:
        """LLM context injection."""
        d = self.get_dashboard()
        if d.total_lights == 0:
            return ""
        lines = [
            f"Lichtmodul: {d.lights_on}/{d.total_lights} Lichter an, "
            f"{d.overrides_active} Overrides, {d.auto_mode_zones} Auto-Zonen"
        ]
        for z in d.zones:
            lines.append(
                f"  {z['zone_name']}: {z['lights_on']}/{z['lights_total']} an "
                f"({z['avg_brightness_pct']:.0f}%)"
            )
        return "\n".join(lines)
