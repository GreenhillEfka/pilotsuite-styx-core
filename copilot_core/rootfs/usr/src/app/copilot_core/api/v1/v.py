from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
v_bp = Blueprint("v", __name__, url_prefix="/api/v1/v")
@v_bp.route("", methods=["GET"])
@require_token
def v(): return jsonify({"ok": True})
