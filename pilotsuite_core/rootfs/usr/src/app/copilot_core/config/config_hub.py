"""Compatibility config facade for integration tests."""
from __future__ import annotations

from typing import Any, Dict


class ConfigHub:
    """Small validation facade expected by legacy tests."""

    _REQUIRED_KEYS = {
        "presence": {"zone_id", "off_delay_seconds"},
        "light": {"zone_id", "default_brightness"},
        "climate": {"zone_id", "target_temp_celsius"},
        "humidity": {"zone_id", "target_humidity_percent"},
        "energy": {"zone_id", "daily_budget_kwh"},
    }

    def __init__(self, zone_registry: Any = None):
        self.zone_registry = zone_registry

    def validate_module_config(self, module_name: str, config: Dict[str, Any]) -> bool:
        required = self._REQUIRED_KEYS.get(module_name)
        if not required:
            raise KeyError(f"unknown module: {module_name}")
        missing = sorted(key for key in required if key not in config)
        if missing:
            raise ValueError(f"invalid {module_name} config, missing: {', '.join(missing)}")
        return True
