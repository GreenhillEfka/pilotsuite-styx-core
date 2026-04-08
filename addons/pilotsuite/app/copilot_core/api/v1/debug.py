"""Debug mode endpoints for PilotSuite Core."""
from flask import Blueprint, jsonify, request

from copilot_core.debug import get_debug, set_debug

bp = Blueprint("debug", __name__, url_prefix="")

from copilot_core.api.security import validate_token as _validate_token


@bp.before_request
def _require_auth():
    if not _validate_token(request):
        return jsonify({"error": "unauthorized", "message": "Valid X-Auth-Token or Bearer token required"}), 401


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
