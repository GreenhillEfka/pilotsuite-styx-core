from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
webgl_bp = Blueprint("webgl", __name__, url_prefix="/api/v1/webgl")
@webgl_bp.route("", methods=["GET"])
@require_token
def webgl(): return jsonify({"ok": True})
