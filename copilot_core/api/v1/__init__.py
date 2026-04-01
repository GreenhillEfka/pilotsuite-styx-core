"""Bridge package for v1 API modules shared between repo root and runtime tree."""

from __future__ import annotations

from pathlib import Path
from pkgutil import extend_path


__path__ = extend_path(__path__, __name__)  # type: ignore[name-defined]

_pkg_dir = Path(__file__).resolve().parent
_runtime_pkg_dir = (
    _pkg_dir.parents[1] / "rootfs" / "usr" / "src" / "app" / "copilot_core" / "api" / "v1"
)
_runtime_pkg_path = str(_runtime_pkg_dir)

if _runtime_pkg_dir.is_dir() and _runtime_pkg_path not in __path__:
    __path__.append(_runtime_pkg_path)
