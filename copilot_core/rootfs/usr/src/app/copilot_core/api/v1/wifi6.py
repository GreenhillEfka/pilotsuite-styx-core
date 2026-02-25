from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
wifi6_bp = Blueprint("wifi6", __name__, url_prefix="/api/v1/wifi6")
@wifi6_bp.route("", methods=["GET"])
@require_token
def wifi6(): return jsonify({"ok": True})
