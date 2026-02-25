from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
power_bp = Blueprint("power", __name__, url_prefix="/api/v1/power")
@power_bp.route("", methods=["GET"])
@require_token
def power(): return jsonify({"ok": True})
