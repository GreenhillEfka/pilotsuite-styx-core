"""
Error Status API Routes - Error Dashboard Widget für Styx Dashboard
"""

import logging
from flask import Blueprint, jsonify

from copilot_core.error_status import (
    get_error_status,
    get_error_history,
    get_module_errors,
)

_LOGGER = logging.getLogger(__name__)

api_bp = Blueprint("error_status_api", __name__)


@api_bp.route("/api/v1/errors/status", methods=["GET"])
def error_status():
    """Get current error status for the dashboard."""
    try:
        status = get_error_status()
        return jsonify(status), 200
    except Exception as e:
        _LOGGER.exception("Failed to get error status")
        return jsonify({"error": str(e)}), 500


@api_bp.route("/api/v1/errors/history", methods=["GET"])
def error_history():
    """Get error history (last 10 entries)."""
    try:
        limit = int(__import__("flask").request.args.get("limit", 10))
        history = get_error_history(limit)
        return jsonify(history), 200
    except Exception as e:
        _LOGGER.exception("Failed to get error history")
        return jsonify({"error": str(e)}), 500


@api_bp.route("/api/v1/errors/modules", methods=["GET"])
def module_errors():
    """Get errors grouped by module."""
    try:
        module = __import__("flask").request.args.get("module")
        if module:
            errors = get_module_errors(module)
            return jsonify({"module": module, "errors": errors}), 200
        else:
            status = get_error_status()
            return jsonify(status), 200
    except Exception as e:
        _LOGGER.exception("Failed to get module errors")
        return jsonify({"error": str(e)}), 500
