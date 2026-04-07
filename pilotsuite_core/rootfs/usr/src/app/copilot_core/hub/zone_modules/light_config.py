"""Light module — migrated from ZoneLightConfig."""
from __future__ import annotations

from .base import ZoneModuleConfig, ZoneModuleFieldSpec
from .registry import zone_module


@zone_module
class LightModuleConfig(ZoneModuleConfig):
    """Per-zone light automation configuration."""

    MODULE_ID = "light"
    MODULE_NAME_DE = "Lichtsteuerung"
    MODULE_ICON = "mdi:lightbulb"
    MODULE_COLOR = "#fbbf24"
    RELEVANT_ROLES = ["lights"]
    RELEVANT_TAGS = ["licht"]
    RELEVANT_DOMAINS = ["light"]

    @classmethod
    def get_field_specs(cls) -> list[ZoneModuleFieldSpec]:
        return [
            ZoneModuleFieldSpec(
                key="enabled", field_type="bool", default=True,
                label_de="Licht Automatik", icon="mdi:lightbulb-auto",
                ha_platform="switch",
            ),
            ZoneModuleFieldSpec(
                key="presence_delay_s", field_type="int", default=5,
                label_de="Einschaltverzögerung", icon="mdi:timer-outline",
                min_value=0, max_value=120, step=5, unit="s",
            ),
            ZoneModuleFieldSpec(
                key="absence_delay_s", field_type="int", default=120,
                label_de="Abschaltverzögerung", icon="mdi:timer-off-outline",
                min_value=0, max_value=600, step=10, unit="s",
            ),
            ZoneModuleFieldSpec(
                key="brightness_target_pct", field_type="int", default=80,
                label_de="Ziel-Helligkeit", icon="mdi:brightness-7",
                min_value=0, max_value=100, step=5, unit="%",
            ),
            ZoneModuleFieldSpec(
                key="brightness_min_pct", field_type="int", default=0,
                label_de="Min. Helligkeit", icon="mdi:brightness-4",
                min_value=0, max_value=100, step=5, unit="%",
            ),
            ZoneModuleFieldSpec(
                key="dampening_band_pct", field_type="int", default=10,
                label_de="Dämpfungsband", icon="mdi:sine-wave",
                min_value=0, max_value=50, step=5, unit="%",
            ),
            ZoneModuleFieldSpec(
                key="lux_indoor_target", field_type="float", default=300.0,
                label_de="Soll-Lux Innen", icon="mdi:brightness-5",
                min_value=0, max_value=2000, step=50, unit="lx",
            ),
            ZoneModuleFieldSpec(
                key="lux_outdoor_compensation", field_type="bool", default=True,
                label_de="Außenlicht-Kompensation", icon="mdi:weather-sunny",
                ha_platform="switch",
            ),
            ZoneModuleFieldSpec(
                key="color_temp_auto", field_type="bool", default=True,
                label_de="Farbtemperatur Auto", icon="mdi:theme-light-dark",
                ha_platform="switch",
            ),
            ZoneModuleFieldSpec(
                key="color_temp_k", field_type="int", default=4000,
                label_de="Farbtemperatur", icon="mdi:thermometer-lines",
                min_value=2200, max_value=6500, step=100, unit="K",
            ),
            ZoneModuleFieldSpec(
                key="mood_aware_enabled", field_type="bool", default=True,
                label_de="Stimmungsanpassung", icon="mdi:emoticon-outline",
                ha_platform="switch",
            ),
        ]
