"""
Auth API - PilotSuite v7.38
"""

from flask import Blueprint, jsonify
from copilot_core.api.security import require_token

auth_bp = Blueprint("auth", __name__, url_prefix="/api/v1/auth")

@auth_bp.route("", methods=["GET"])
@require_token
def auth_status():
    return jsonify({"ok": True, "auth": "enabled"})
