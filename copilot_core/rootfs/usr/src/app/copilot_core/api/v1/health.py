"""Health API compatibility bridge for blueprint reconciliation."""

from copilot_core.system_health.api import (
    init_system_health_api,
    system_health_bp as health_bp,
)

__all__ = ["health_bp", "init_system_health_api"]
