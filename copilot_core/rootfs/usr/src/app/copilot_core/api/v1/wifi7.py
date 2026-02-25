from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
wifi7_bp = Blueprint("wifi7", __name__, url_prefix="/api/v1/wifi7")
@wifi7_bp.route("", methods=["GET"])
@require_token
def wifi7(): return jsonify({"ok": True})
