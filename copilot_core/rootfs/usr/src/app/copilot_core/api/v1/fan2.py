from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
fan_bp = Blueprint("fan2", __name__, url_prefix="/api/v1/fan2")
@fan_bp.route("", methods=["GET"])
@require_token
def fan2(): return jsonify({"ok": True})
