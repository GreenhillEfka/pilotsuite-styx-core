"""Security module — Sicherheit pro Zone (Schloss, Tür, Fenster)."""
from __future__ import annotations

from .base import ZoneModuleConfig, ZoneModuleFieldSpec
from .registry import zone_module


@zone_module
class SecurityModuleConfig(ZoneModuleConfig):
    """Per-zone security configuration."""

    MODULE_ID = "security"
    MODULE_NAME_DE = "Sicherheit"
    MODULE_ICON = "mdi:shield-home"
    MODULE_COLOR = "#ef4444"
    RELEVANT_ROLES = ["lock", "door", "window"]
    RELEVANT_TAGS = ["schloss", "tuer", "fenster", "sicherheit"]
    RELEVANT_DOMAINS = ["lock", "alarm_control_panel"]

    @classmethod
    def get_field_specs(cls) -> list[ZoneModuleFieldSpec]:
        return [
            ZoneModuleFieldSpec(
                key="enabled", field_type="bool", default=True,
                label_de="Sicherheit aktiv", icon="mdi:shield-home",
                ha_platform="switch",
            ),
            ZoneModuleFieldSpec(
                key="auto_lock", field_type="bool", default=False,
                label_de="Auto-Verriegelung", icon="mdi:lock-clock",
                ha_platform="switch",
            ),
            ZoneModuleFieldSpec(
                key="auto_lock_delay_min", field_type="int", default=10,
                label_de="Verriegelung nach", icon="mdi:timer-lock-outline",
                min_value=1, max_value=60, step=1, unit="min",
            ),
            ZoneModuleFieldSpec(
                key="alert_open_window", field_type="bool", default=True,
                label_de="Fenster-offen Alarm", icon="mdi:window-open",
                ha_platform="switch",
            ),
        ]
