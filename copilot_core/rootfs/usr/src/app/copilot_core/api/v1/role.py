from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
role_bp = Blueprint("role", __name__, url_prefix="/api/v1/role")
@role_bp.route("", methods=["GET"])
@require_token
def role(): return jsonify({"ok": True})
