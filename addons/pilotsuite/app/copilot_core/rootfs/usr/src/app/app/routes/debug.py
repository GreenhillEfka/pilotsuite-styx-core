"""Debug mode API endpoints."""
from flask import Blueprint, jsonify, request

from copilot_core.debug import get_debug, set_debug

bp = Blueprint("debug", __name__, url_prefix="/api/v1")


@bp.route("/debug", methods=["GET"])
def get_debug_status():
    """Get debug mode status."""
    return jsonify({"debug_mode": get_debug()}), 200


@bp.route("/debug", methods=["POST"])
def set_debug_status():
    """Set debug mode status."""
    data = request.get_json()
    if data is None or "enabled" not in data or not isinstance(data["enabled"], bool):
        return (
            jsonify(
                {
                    "error": "Invalid request. 'enabled' must be a boolean (true/false)."
                }
            ),
            400,
        )
    set_debug(data["enabled"])
    return jsonify({"enabled": data["enabled"]}), 200
