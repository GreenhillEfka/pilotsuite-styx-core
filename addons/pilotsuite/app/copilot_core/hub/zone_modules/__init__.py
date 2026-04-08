"""Zone Modules — Self-describing, per-zone automation module system."""
from __future__ import annotations

from .base import ZoneModuleConfig, ZoneModuleFieldSpec
from .registry import ZoneModuleRegistry, zone_module

__all__ = [
    "ZoneModuleConfig",
    "ZoneModuleFieldSpec",
    "ZoneModuleRegistry",
    "zone_module",
]
