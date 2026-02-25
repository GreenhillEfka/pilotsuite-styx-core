"""
Info API - PilotSuite v7.39
"""

from flask import Blueprint, jsonify
from copilot_core.api.security import require_token

info_bp = Blueprint("info", __name__, url_prefix="/api/v1/info")

@info_bp.route("", methods=["GET"])
@require_token
def get_info():
    return jsonify({"ok": True, "name": "PilotSuite", "version": "7.39.0"})
