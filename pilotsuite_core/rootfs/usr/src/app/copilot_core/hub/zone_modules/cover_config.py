"""Cover module — Rollladen/Jalousien pro Zone."""
from __future__ import annotations

from .base import ZoneModuleConfig, ZoneModuleFieldSpec
from .registry import zone_module


@zone_module
class CoverModuleConfig(ZoneModuleConfig):
    """Per-zone cover/blinds automation configuration."""

    MODULE_ID = "cover"
    MODULE_NAME_DE = "Beschattung"
    MODULE_ICON = "mdi:blinds"
    MODULE_COLOR = "#fb923c"
    RELEVANT_ROLES = ["cover"]
    RELEVANT_TAGS = ["rollladen"]
    RELEVANT_DOMAINS = ["cover"]

    @classmethod
    def get_field_specs(cls) -> list[ZoneModuleFieldSpec]:
        return [
            ZoneModuleFieldSpec(
                key="enabled", field_type="bool", default=True,
                label_de="Beschattung Automatik", icon="mdi:blinds",
                ha_platform="switch",
            ),
            ZoneModuleFieldSpec(
                key="sun_protection", field_type="bool", default=True,
                label_de="Sonnenschutz", icon="mdi:weather-sunny-alert",
                ha_platform="switch",
            ),
            ZoneModuleFieldSpec(
                key="sun_threshold_lux", field_type="int", default=40000,
                label_de="Sonnenschutz ab (Lux)", icon="mdi:white-balance-sunny",
                min_value=10000, max_value=100000, step=5000, unit="lx",
            ),
            ZoneModuleFieldSpec(
                key="night_close", field_type="bool", default=True,
                label_de="Nachts schließen", icon="mdi:blinds-horizontal-closed",
                ha_platform="switch",
            ),
            ZoneModuleFieldSpec(
                key="default_position_pct", field_type="int", default=100,
                label_de="Standard-Position", icon="mdi:blinds-open",
                min_value=0, max_value=100, step=10, unit="%",
            ),
        ]
