from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
arc_bp = Blueprint("arc", __name__, url_prefix="/api/v1/arc")
@arc_bp.route("", methods=["GET"])
@require_token
def arc(): return jsonify({"ok": True})
