from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
authelia_bp = Blueprint("authelia", __name__, url_prefix="/api/v1/authelia")
@authelia_bp.route("", methods=["GET"])
@require_token
def authelia(): return jsonify({"ok": True})
