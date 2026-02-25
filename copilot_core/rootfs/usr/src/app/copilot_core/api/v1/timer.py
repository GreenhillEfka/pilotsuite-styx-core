from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
timer_bp = Blueprint("timer", __name__, url_prefix="/api/v1/timer")
@timer_bp.route("", methods=["GET"])
@require_token
def timer(): return jsonify({"ok": True})
