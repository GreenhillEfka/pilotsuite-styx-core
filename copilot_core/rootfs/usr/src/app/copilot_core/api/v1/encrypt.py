from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
encrypt_bp = Blueprint("encrypt", __name__, url_prefix="/api/v1/encrypt")
@encrypt_bp.route("", methods=["GET"])
@require_token
def encrypt(): return jsonify({"ok": True})
