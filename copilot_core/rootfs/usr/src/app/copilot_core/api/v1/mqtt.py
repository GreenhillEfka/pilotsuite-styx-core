from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
mqtt_bp = Blueprint("mqtt", __name__, url_prefix="/api/v1/mqtt")
@mqtt_bp.route("", methods=["GET"])
@require_token
def mqtt(): return jsonify({"ok": True})
