from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
vnc2_bp = Blueprint("vnc2", __name__, url_prefix="/api/v1/vnc2")
@vnc2_bp.route("", methods=["GET"])
@require_token
def vnc2(): return jsonify({"ok": True})
