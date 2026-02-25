from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
autogpt_bp = Blueprint("autogpt", __name__, url_prefix="/api/v1/autogpt")
@autogpt_bp.route("", methods=["GET"])
@require_token
def autogpt(): return jsonify({"ok": True})
