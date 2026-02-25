"""
Panel API - PilotSuite v7.46
"""

from flask import Blueprint, jsonify
from copilot_core.api.security import require_token

panel_bp = Blueprint("panel", __name__, url_prefix="/api/v1/panel")

@panel_bp.route("", methods=["GET"])
@require_token
def panel_info():
    return jsonify({"ok": True, "panels": []})
