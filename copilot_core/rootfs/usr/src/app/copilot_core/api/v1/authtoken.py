from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
authtoken_bp = Blueprint("authtoken", __name__, url_prefix="/api/v1/authtoken")
@authtoken_bp.route("", methods=["GET"])
@require_token
def authtoken(): return jsonify({"ok": True})
