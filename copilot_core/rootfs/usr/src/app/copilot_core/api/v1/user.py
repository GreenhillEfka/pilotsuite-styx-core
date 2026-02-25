from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
user_bp = Blueprint("user", __name__, url_prefix="/api/v1/user")
@user_bp.route("", methods=["GET"])
@require_token
def user(): return jsonify({"ok": True})
