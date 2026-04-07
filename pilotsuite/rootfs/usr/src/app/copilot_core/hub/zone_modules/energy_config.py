"""Energy module — Energiemanagement pro Zone."""
from __future__ import annotations

from .base import ZoneModuleConfig, ZoneModuleFieldSpec
from .registry import zone_module


@zone_module
class EnergyModuleConfig(ZoneModuleConfig):
    """Per-zone energy management configuration."""

    MODULE_ID = "energy"
    MODULE_NAME_DE = "Energiemanagement"
    MODULE_ICON = "mdi:flash"
    MODULE_COLOR = "#4ade80"
    RELEVANT_ROLES = ["energy"]
    RELEVANT_TAGS = ["energie"]
    RELEVANT_DOMAINS = ["sensor"]

    @classmethod
    def get_field_specs(cls) -> list[ZoneModuleFieldSpec]:
        return [
            ZoneModuleFieldSpec(
                key="enabled", field_type="bool", default=True,
                label_de="Energieüberwachung", icon="mdi:flash",
                ha_platform="switch",
            ),
            ZoneModuleFieldSpec(
                key="standby_detection", field_type="bool", default=True,
                label_de="Standby-Erkennung", icon="mdi:power-standby",
                ha_platform="switch",
            ),
            ZoneModuleFieldSpec(
                key="standby_threshold_w", field_type="float", default=5.0,
                label_de="Standby-Schwelle", icon="mdi:power-plug-off",
                min_value=1, max_value=50, step=1, unit="W",
            ),
            ZoneModuleFieldSpec(
                key="budget_kwh_day", field_type="float", default=0.0,
                label_de="Tagesbudget", icon="mdi:chart-bar",
                min_value=0, max_value=100, step=1, unit="kWh",
            ),
        ]
