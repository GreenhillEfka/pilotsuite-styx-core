"""Bridge package for configuration engine modules."""

from __future__ import annotations

from pathlib import Path
from pkgutil import extend_path


__path__ = extend_path(__path__, __name__)  # type: ignore[name-defined]

_pkg_dir = Path(__file__).resolve().parent
_runtime_pkg_dir = (
    _pkg_dir.parent / "rootfs" / "usr" / "src" / "app" / "copilot_core" / "config"
)
_runtime_pkg_path = str(_runtime_pkg_dir)

if _runtime_pkg_dir.is_dir() and _runtime_pkg_path not in __path__:
    __path__.append(_runtime_pkg_path)

from .engine import (
    ConfigurationEngine,
    ConfigType,
    ConfigSource,
    ConfigSchema,
    ConfigEntry,
    ConfigChange,
    create_configuration_engine,
)

__all__ = [
    "ConfigurationEngine",
    "ConfigType",
    "ConfigSource",
    "ConfigSchema",
    "ConfigEntry",
    "ConfigChange",
    "create_configuration_engine",
]
