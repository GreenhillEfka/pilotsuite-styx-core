from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
conversation_bp = Blueprint("conversation", __name__, url_prefix="/api/v1/conversation")
@conversation_bp.route("", methods=["GET"])
@require_token
def conversation(): return jsonify({"ok": True})
