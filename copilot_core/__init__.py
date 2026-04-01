"""Top-level package bridge for the real runtime implementation.

This repository keeps the Home Assistant add-on/runtime Python package under
``copilot_core/rootfs/usr/src/app/copilot_core`` while a subset of modules also
exists at the repository root for packaging/docs/tests.

Top-level pytest runs should resolve both trees through the same package name.
"""

from __future__ import annotations

from pathlib import Path
from pkgutil import extend_path


__path__ = extend_path(__path__, __name__)  # type: ignore[name-defined]

_pkg_dir = Path(__file__).resolve().parent
_runtime_pkg_dir = _pkg_dir / "rootfs" / "usr" / "src" / "app" / "copilot_core"
_runtime_pkg_path = str(_runtime_pkg_dir)

if _runtime_pkg_dir.is_dir() and _runtime_pkg_path not in __path__:
    __path__.append(_runtime_pkg_path)
