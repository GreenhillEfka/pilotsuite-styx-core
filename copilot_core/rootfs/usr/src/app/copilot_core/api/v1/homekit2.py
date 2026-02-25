from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
homekit2_bp = Blueprint("homekit2", __name__, url_prefix="/api/v1/homekit2")
@homekit2_bp.route("", methods=["GET"])
@require_token
def homekit2(): return jsonify({"ok": True})
