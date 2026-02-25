from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
llamacpp_bp = Blueprint("llamacpp", __name__, url_prefix="/api/v1/llamacpp")
@llamacpp_bp.route("", methods=["GET"])
@require_token
def llamacpp(): return jsonify({"ok": True})
