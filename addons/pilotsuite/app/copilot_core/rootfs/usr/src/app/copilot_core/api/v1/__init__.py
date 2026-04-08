"""
API v1 endpoints for PilotSuite Core.

This package provides the REST API for the Core Add-on.
"""

from flask import Blueprint

api_v1_bp = Blueprint("api_v1", __name__)

# Import submodules to register routes
from copilot_core.api.v1 import error_status as error_status_module

# Re-export for convenience
from copilot_core.error_status import (
    get_error_status,
    get_error_history,
    get_module_errors,
    register_error,
)
