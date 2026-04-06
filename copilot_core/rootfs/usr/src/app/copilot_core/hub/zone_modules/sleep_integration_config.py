"""Sleep Integration Module — Musikwolke ↔ Sonnenwecker Integration.

Automatically pauses Musikwolke when sleep mode activates (Sonnenwecker/Sunset),
and resumes playback after wake-up (Sunrise alarm).

Features:
- Auto-Pause: Musikwolke pausieren wenn Schlaf-Modus aktiv
- Auto-Resume: Musikwolke reaktivieren nach Wake-Up
- Config-Option pro Zone: enable/disable integration
- Status-Indicator: "Schlaf-Modus aktiv" in Lovelace
"""
from __future__ import annotations

from .base import ZoneModuleConfig, ZoneModuleFieldSpec
from .registry import zone_module


@zone_module
class SleepIntegrationModuleConfig(ZoneModuleConfig):
    """Per-zone Schlaf-Modus Integration für Musikwolke."""

    MODULE_ID = "sleep_integration"
    MODULE_NAME_DE = "Schlaf-Modus Integration"
    MODULE_ICON = "mdi:sleep"
    MODULE_COLOR = "#7c3aed"  # Purple for sleep
    RELEVANT_ROLES = ["media", "lights"]
    RELEVANT_TAGS = ["medien", "schlaf"]
    RELEVANT_DOMAINS = ["media_player", "light"]

    @classmethod
    def get_field_specs(cls) -> list[ZoneModuleFieldSpec]:
        return [
            ZoneModuleFieldSpec(
                key="enabled",
                field_type="bool",
                default=False,
                label_de="Schlaf-Modus Integration",
                icon="mdi:sleep",
                ha_platform="switch",
            ),
            ZoneModuleFieldSpec(
                key="auto_pause_on_sleep",
                field_type="bool",
                default=True,
                label_de="Auto-Pause bei Schlaf",
                icon="mdi:pause-circle",
                ha_platform="switch",
            ),
            ZoneModuleFieldSpec(
                key="auto_resume_on_wake",
                field_type="bool",
                default=True,
                label_de="Auto-Resume nach Aufwachen",
                icon="mdi:play-circle",
                ha_platform="switch",
            ),
            ZoneModuleFieldSpec(
                key="pause_delay_s",
                field_type="int",
                default=0,
                label_de="Pause Verzögerung",
                icon="mdi:timer-outline",
                min_value=0,
                max_value=300,
                step=10,
                unit="s",
            ),
            ZoneModuleFieldSpec(
                key="resume_delay_s",
                field_type="int",
                default=60,
                label_de="Resume Verzögerung",
                icon="mdi:timer-play-outline",
                min_value=0,
                max_value=600,
                step=10,
                unit="s",
            ),
            ZoneModuleFieldSpec(
                key="volume_restore_pct",
                field_type="int",
                default=100,
                label_de="Lautstärke nach Resume",
                icon="mdi:volume-high",
                min_value=0,
                max_value=100,
                step=5,
                unit="%",
            ),
            ZoneModuleFieldSpec(
                key="show_status_indicator",
                field_type="bool",
                default=True,
                label_de="Status-Indicator anzeigen",
                icon="mdi:information-outline",
                ha_platform="switch",
            ),
        ]
