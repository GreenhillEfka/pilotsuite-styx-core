"""Music module — migrated from ZoneMusicConfig."""
from __future__ import annotations

from .base import ZoneModuleConfig, ZoneModuleFieldSpec
from .registry import zone_module


@zone_module
class MusicModuleConfig(ZoneModuleConfig):
    """Per-zone Musikwolke automation configuration."""

    MODULE_ID = "music"
    MODULE_NAME_DE = "Musiksteuerung"
    MODULE_ICON = "mdi:music"
    MODULE_COLOR = "#60a5fa"
    RELEVANT_ROLES = ["media"]
    RELEVANT_TAGS = ["medien"]
    RELEVANT_DOMAINS = ["media_player"]

    @classmethod
    def get_field_specs(cls) -> list[ZoneModuleFieldSpec]:
        return [
            ZoneModuleFieldSpec(
                key="enabled", field_type="bool", default=True,
                label_de="Musik Automatik", icon="mdi:music-circle",
                ha_platform="switch",
            ),
            ZoneModuleFieldSpec(
                key="presence_auto_play", field_type="bool", default=False,
                label_de="Musik Auto-Play", icon="mdi:music-note-plus",
                ha_platform="switch",
            ),
            ZoneModuleFieldSpec(
                key="presence_delay_s", field_type="int", default=10,
                label_de="Musik Einschaltverzögerung", icon="mdi:timer-music-outline",
                min_value=0, max_value=120, step=5, unit="s",
            ),
            ZoneModuleFieldSpec(
                key="absence_pause_s", field_type="int", default=300,
                label_de="Musik Pausenverzögerung", icon="mdi:timer-music",
                min_value=0, max_value=600, step=10, unit="s",
            ),
            ZoneModuleFieldSpec(
                key="follow_mode", field_type="bool", default=True,
                label_de="Musik Follow", icon="mdi:walk",
                ha_platform="switch",
            ),
            ZoneModuleFieldSpec(
                key="default_volume_pct", field_type="int", default=30,
                label_de="Musiklautstärke", icon="mdi:volume-medium",
                min_value=0, max_value=100, step=5, unit="%",
            ),
            ZoneModuleFieldSpec(
                key="fade_duration_s", field_type="int", default=3,
                label_de="Überblendung", icon="mdi:swap-horizontal",
                min_value=0, max_value=30, step=1, unit="s",
            ),
        ]
