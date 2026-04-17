"""PilotSuite Core API v1 package.

Extends the repo-root package path with the add-on API v1 tree so tests and
repo-root callers can import active runtime endpoints such as
``copilot_core.api.v1.voice`` without forcing the add-on app path to the front
of ``sys.path``.
"""
from __future__ import annotations

from pathlib import Path


_ADDON_API_V1_PACKAGE = (
    Path(__file__).resolve().parents[3]
    / "addons"
    / "pilotsuite"
    / "app"
    / "copilot_core"
    / "api"
    / "v1"
)
if _ADDON_API_V1_PACKAGE.is_dir():
    addon_package_path = str(_ADDON_API_V1_PACKAGE)
    if addon_package_path not in __path__:
        __path__.append(addon_package_path)
