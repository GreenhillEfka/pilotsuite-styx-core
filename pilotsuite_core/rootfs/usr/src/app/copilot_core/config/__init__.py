"""Central configuration layer for Copilot Core.

Provides unified configuration management across modules:
- cross_module: Cross-module zone configuration and conflict detection
"""
from .cross_module import (
    CrossModuleConfig,
    ZoneConfig,
    SonosConfig,
    LightConfig,
    PresenceConfig,
    AlarmConfig,
    MoodConfig,
    Conflict,
    async_get_cross_module_config,
)

__all__ = [
    "CrossModuleConfig",
    "ZoneConfig",
    "SonosConfig",
    "LightConfig",
    "PresenceConfig",
    "AlarmConfig",
    "MoodConfig",
    "Conflict",
    "async_get_cross_module_config",
]
