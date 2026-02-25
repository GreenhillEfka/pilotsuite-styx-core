from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
vnc_bp = Blueprint("vnc", __name__, url_prefix="/api/v1/vnc")
@vnc_bp.route("", methods=["GET"])
@require_token
def vnc(): return jsonify({"ok": True})
