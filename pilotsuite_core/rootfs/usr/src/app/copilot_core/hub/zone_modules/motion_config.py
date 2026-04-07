"""Motion module — Bewegung/Präsenz pro Zone."""
from __future__ import annotations

from .base import ZoneModuleConfig, ZoneModuleFieldSpec
from .registry import zone_module


@zone_module
class MotionModuleConfig(ZoneModuleConfig):
    """Per-zone motion/presence detection configuration."""

    MODULE_ID = "motion"
    MODULE_NAME_DE = "Bewegungserkennung"
    MODULE_ICON = "mdi:motion-sensor"
    MODULE_COLOR = "#f472b6"
    RELEVANT_ROLES = ["motion", "presence"]
    RELEVANT_TAGS = ["bewegung", "präsenz"]
    RELEVANT_DOMAINS = ["binary_sensor", "sensor"]

    @classmethod
    def get_field_specs(cls) -> list[ZoneModuleFieldSpec]:
        return [
            ZoneModuleFieldSpec(
                key="enabled", field_type="bool", default=True,
                label_de="Bewegung Automatik", icon="mdi:motion-sensor",
                ha_platform="switch",
            ),
            ZoneModuleFieldSpec(
                key="sensitivity", field_type="int", default=80,
                label_de="Empfindlichkeit", icon="mdi:tune",
                min_value=10, max_value=100, step=5, unit="%",
            ),
            ZoneModuleFieldSpec(
                key="hold_time_s", field_type="int", default=30,
                label_de="Nachlaufzeit", icon="mdi:timer-outline",
                min_value=5, max_value=300, step=5, unit="s",
            ),
            ZoneModuleFieldSpec(
                key="night_mode", field_type="bool", default=True,
                label_de="Nachtmodus", icon="mdi:weather-night",
                ha_platform="switch",
            ),
            ZoneModuleFieldSpec(
                key="night_sensitivity", field_type="int", default=50,
                label_de="Nacht-Empfindlichkeit", icon="mdi:moon-outline",
                min_value=10, max_value=100, step=5, unit="%",
            ),
        ]
