"""Debug mode endpoints for PilotSuite Core."""

from flask import Blueprint, jsonify, request

from copilot_core.api.security import validate_token as _validate_token
from copilot_core.debug import get_debug, set_debug

bp = Blueprint("debug", __name__, url_prefix="")


def _json_error(message: str, status: int):
    return jsonify({"error": message}), status


@bp.before_request
def _require_auth():
    if not _validate_token(request):
        return (
            jsonify({"error": "unauthorized", "message": "Valid X-Auth-Token or Bearer token required"}),
            401,
        )


@bp.route("/debug", methods=["GET"])
def get_debug_status():
    """Get debug mode status."""
    try:
        return jsonify({"debug_mode": get_debug()}), 200
    except Exception as exc:
        return _json_error(str(exc), 500)


@bp.route("/debug", methods=["POST"])
def set_debug_status():
    """Set debug mode status."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return _json_error("JSON object required", 400)

    enabled = data.get("enabled")
    if not isinstance(enabled, bool):
        return _json_error("Invalid request. 'enabled' must be a boolean (true/false).", 400)

    try:
        set_debug(enabled)
    except Exception as exc:
        return _json_error(str(exc), 500)
    return jsonify({"enabled": enabled}), 200
