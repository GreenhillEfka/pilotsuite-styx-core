from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
battery_bp = Blueprint("battery", __name__, url_prefix="/api/v1/battery")
@battery_bp.route("", methods=["GET"])
@require_token
def battery(): return jsonify({"ok": True})
