"""
Front Matter API - PilotSuite v7.44
"""

from flask import Blueprint, jsonify
from copilot_core.api.security import require_token

front_bp = Blueprint("front", __name__, url_prefix="/api/v1/front")

@front_bp.route("", methods=["GET"])
@require_token
def front_matter():
    return jsonify({"ok": True, "theme": "default"})
