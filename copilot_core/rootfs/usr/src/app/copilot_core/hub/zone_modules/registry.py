"""Zone Module Registry — Decorator-based module registration."""
from __future__ import annotations

import logging
from typing import Any

from .base import ZoneModuleConfig

logger = logging.getLogger(__name__)

_REGISTRY: dict[str, type[ZoneModuleConfig]] = {}


def zone_module(cls: type[ZoneModuleConfig]) -> type[ZoneModuleConfig]:
    """Decorator to register a ZoneModuleConfig subclass."""
    module_id = cls.MODULE_ID
    if not module_id:
        raise ValueError(f"{cls.__name__} must define MODULE_ID")
    if module_id in _REGISTRY:
        logger.warning("Overwriting module %r with %s", module_id, cls.__name__)
    _REGISTRY[module_id] = cls
    logger.debug("Registered zone module %r (%s)", module_id, cls.MODULE_NAME_DE)
    return cls


class ZoneModuleRegistry:
    """Central registry for all zone modules."""

    @staticmethod
    def get_all() -> dict[str, type[ZoneModuleConfig]]:
        return dict(_REGISTRY)

    @staticmethod
    def get(module_id: str) -> type[ZoneModuleConfig] | None:
        return _REGISTRY.get(module_id)

    @staticmethod
    def get_all_schemas() -> dict[str, dict[str, Any]]:
        return {mid: cls.get_schema() for mid, cls in _REGISTRY.items()}

    @staticmethod
    def create_defaults() -> dict[str, ZoneModuleConfig]:
        return {mid: cls() for mid, cls in _REGISTRY.items()}

    @staticmethod
    def from_dict(data: dict[str, dict[str, Any]]) -> dict[str, ZoneModuleConfig]:
        result: dict[str, ZoneModuleConfig] = {}
        for mid, cls in _REGISTRY.items():
            if mid in data:
                result[mid] = cls.from_dict(data[mid])
            else:
                result[mid] = cls()
        return result

    @staticmethod
    def ensure_loaded() -> None:
        """Import all module configs to trigger @zone_module decorators."""
        from . import light_config, music_config  # noqa: F401
        from . import climate_config, cover_config  # noqa: F401
        from . import energy_config, scene_config, security_config  # noqa: F401
