from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
glooeedge_bp = Blueprint("glooeedge", __name__, url_prefix="/api/v1/glooeedge")
@glooeedge_bp.route("", methods=["GET"])
@require_token
def glooeedge(): return jsonify({"ok": True})
