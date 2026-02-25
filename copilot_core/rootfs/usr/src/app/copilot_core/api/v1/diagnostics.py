"""
Diagnostics API - PilotSuite v7.36
"""

from flask import Blueprint, jsonify
from copilot_core.api.security import require_token

diagnostics_bp = Blueprint("diagnostics", __name__, url_prefix="/api/v1/diagnostics")

@diagnostics_bp.route("", methods=["GET"])
@require_token
def get_diagnostics():
    return jsonify({
        "ok": True,
        "status": "healthy",
        "uptime": "N/A"
    })
