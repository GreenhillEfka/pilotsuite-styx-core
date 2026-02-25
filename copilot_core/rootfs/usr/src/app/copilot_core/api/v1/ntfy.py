from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
ntfy_bp = Blueprint("ntfy", __name__, url_prefix="/api/v1/ntfy")
@ntfy_bp.route("", methods=["GET"])
@require_token
def ntfy(): return jsonify({"ok": True})
