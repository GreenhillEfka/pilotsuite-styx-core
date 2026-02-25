from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
homekit_bp = Blueprint("homekit", __name__, url_prefix="/api/v1/homekit")
@homekit_bp.route("", methods=["GET"])
@require_token
def homekit(): return jsonify({"ok": True})
