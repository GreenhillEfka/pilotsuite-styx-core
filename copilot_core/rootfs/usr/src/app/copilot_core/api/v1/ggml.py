from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
ggml_bp = Blueprint("ggml", __name__, url_prefix="/api/v1/ggml")
@ggml_bp.route("", methods=["GET"])
@require_token
def ggml(): return jsonify({"ok": True})
