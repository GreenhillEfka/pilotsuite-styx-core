from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
touchscreen_bp = Blueprint("touchscreen", __name__, url_prefix="/api/v1/touchscreen")
@touchscreen_bp.route("", methods=["GET"])
@require_token
def touchscreen(): return jsonify({"ok": True})
