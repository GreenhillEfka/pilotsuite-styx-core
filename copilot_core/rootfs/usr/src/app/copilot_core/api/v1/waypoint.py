from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
waypoint_bp = Blueprint("waypoint", __name__, url_prefix="/api/v1/waypoint")
@waypoint_bp.route("", methods=["GET"])
@require_token
def waypoint(): return jsonify({"ok": True})
