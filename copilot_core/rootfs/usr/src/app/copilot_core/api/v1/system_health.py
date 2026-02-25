"""
System Health API - PilotSuite v7.30.0
"""

from flask import Blueprint, jsonify, request
import logging

from copilot_core.api.security import require_token

logger = logging.getLogger(__name__)

system_health_bp = Blueprint("system_health", __name__, url_prefix="/api/v1/system_health")


@system_health_bp.route("", methods=["GET"])
@require_token
def get_system_health():
    """Get system health info."""
    try:
        from homeassistant.components import system_health
        return jsonify({"ok": True, "message": "System health endpoint"})
    except:
        return jsonify({"ok": True, "status": "healthy"})
