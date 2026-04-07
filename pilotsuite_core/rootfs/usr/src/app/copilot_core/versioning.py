"""Runtime version resolution helpers for PilotSuite Core."""

from __future__ import annotations

import os
from pathlib import Path


def get_runtime_version(default: str = "0.0.0") -> str:
    """Resolve runtime version from env with stable file fallback.

    Priority:
    1) ``COPILOT_VERSION``
    2) ``BUILD_VERSION``
    3) ``/usr/src/app/VERSION`` (packaged fallback)
    """
    for key in ("COPILOT_VERSION", "BUILD_VERSION"):
        value = str(os.environ.get(key, "") or "").strip()
        if value:
            return value

    version_file = Path(__file__).resolve().parents[1] / "VERSION"
    try:
        value = version_file.read_text(encoding="utf-8").strip()
        if value:
            return value
    except Exception:
        pass

    return default
