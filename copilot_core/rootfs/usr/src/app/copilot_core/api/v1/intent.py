from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
intent_bp = Blueprint("intent", __name__, url_prefix="/api/v1/intent")
@intent_bp.route("", methods=["GET"])
@require_token
def intent(): return jsonify({"ok": True})
