from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
postfix_bp = Blueprint("postfix", __name__, url_prefix="/api/v1/postfix")
@postfix_bp.route("", methods=["GET"])
@require_token
def postfix(): return jsonify({"ok": True})
