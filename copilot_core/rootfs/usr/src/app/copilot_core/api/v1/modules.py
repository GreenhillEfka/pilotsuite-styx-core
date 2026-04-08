"""Module Registry API (compat import).

Historically some docs referenced ``copilot_core.api.v1.modules``.
The implementation lives in :mod:`copilot_core.api.v1.module_control`.

This file keeps imports stable without duplicating logic.
"""

from __future__ import annotations

from copilot_core.api.v1.module_control import (  # noqa: F401
    module_control_bp as bp,
    module_control_bp,
    init_module_control_api,
)
