"""Scene module — Szenen pro Zone."""
from __future__ import annotations

from .base import ZoneModuleConfig, ZoneModuleFieldSpec
from .registry import zone_module


@zone_module
class SceneModuleConfig(ZoneModuleConfig):
    """Per-zone scene configuration."""

    MODULE_ID = "scene"
    MODULE_NAME_DE = "Szenen"
    MODULE_ICON = "mdi:palette"
    MODULE_COLOR = "#c084fc"
    RELEVANT_ROLES = ["other"]
    RELEVANT_TAGS = ["styx"]
    RELEVANT_DOMAINS = ["scene", "script"]

    @classmethod
    def get_field_specs(cls) -> list[ZoneModuleFieldSpec]:
        return [
            ZoneModuleFieldSpec(
                key="enabled", field_type="bool", default=True,
                label_de="Szenen aktiv", icon="mdi:palette",
                ha_platform="switch",
            ),
            ZoneModuleFieldSpec(
                key="mood_scenes", field_type="bool", default=True,
                label_de="Stimmungsszenen", icon="mdi:emoticon-outline",
                ha_platform="switch",
            ),
            ZoneModuleFieldSpec(
                key="transition_s", field_type="int", default=3,
                label_de="Übergangszeit", icon="mdi:transition",
                min_value=0, max_value=30, step=1, unit="s",
            ),
        ]
