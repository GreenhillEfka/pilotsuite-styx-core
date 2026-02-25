"""
API v1 endpoints for PilotSuite Core.

This package provides the REST API for the Core Add-on.
"""

from flask import Blueprint

api_v1_bp = Blueprint("api_v1", __name__)

# Import submodules to register routes
from copilot_core.api.v1 import error_status as error_status_module
from copilot_core.api.v1 import input_number as input_number_module
from copilot_core.api.v1 import zones as zones_module
from copilot_core.api.v1 import scene_patterns as scene_patterns_module
from copilot_core.api.v1 import routine_patterns as routine_patterns_module
from copilot_core.api.v1 import push_notifications as push_notifications_module

# Re-export for convenience
from copilot_core.error_status import (
    get_error_status,
    get_error_history,
    get_module_errors,
    register_error,
)
