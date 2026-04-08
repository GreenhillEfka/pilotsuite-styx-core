"""Climate module — Heizung/Klima pro Zone."""
from __future__ import annotations

from .base import ZoneModuleConfig, ZoneModuleFieldSpec
from .registry import zone_module


@zone_module
class ClimateModuleConfig(ZoneModuleConfig):
    """Per-zone climate/heating automation configuration."""

    MODULE_ID = "climate"
    MODULE_NAME_DE = "Klimasteuerung"
    MODULE_ICON = "mdi:thermometer"
    MODULE_COLOR = "#34d399"
    RELEVANT_ROLES = ["climate"]
    RELEVANT_TAGS = ["klima"]
    RELEVANT_DOMAINS = ["climate", "fan"]

    @classmethod
    def get_field_specs(cls) -> list[ZoneModuleFieldSpec]:
        return [
            ZoneModuleFieldSpec(
                key="enabled", field_type="bool", default=True,
                label_de="Klima Automatik", icon="mdi:thermostat-auto",
                ha_platform="switch",
            ),
            ZoneModuleFieldSpec(
                key="target_temp_c", field_type="float", default=21.0,
                label_de="Zieltemperatur", icon="mdi:thermometer",
                min_value=15, max_value=30, step=0.5, unit="°C",
            ),
            ZoneModuleFieldSpec(
                key="night_setback_c", field_type="float", default=18.0,
                label_de="Nachtabsenkung", icon="mdi:weather-night",
                min_value=14, max_value=25, step=0.5, unit="°C",
            ),
            ZoneModuleFieldSpec(
                key="presence_boost", field_type="bool", default=True,
                label_de="Anwesenheits-Boost", icon="mdi:radiator",
                ha_platform="switch",
            ),
            ZoneModuleFieldSpec(
                key="window_off", field_type="bool", default=True,
                label_de="Fenster-auf = Heizung aus", icon="mdi:window-open-variant",
                ha_platform="switch",
            ),
        ]
