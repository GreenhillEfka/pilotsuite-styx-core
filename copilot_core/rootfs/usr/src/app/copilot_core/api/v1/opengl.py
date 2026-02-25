from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
opengl_bp = Blueprint("opengl", __name__, url_prefix="/api/v1/opengl")
@opengl_bp.route("", methods=["GET"])
@require_token
def opengl(): return jsonify({"ok": True})
