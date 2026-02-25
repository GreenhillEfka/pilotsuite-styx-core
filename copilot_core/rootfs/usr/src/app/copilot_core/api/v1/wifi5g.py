from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
wifi5g_bp = Blueprint("wifi5g", __name__, url_prefix="/api/v1/wifi5g")
@wifi5g_bp.route("", methods=["GET"])
@require_token
def wifi5g(): return jsonify({"ok": True})
