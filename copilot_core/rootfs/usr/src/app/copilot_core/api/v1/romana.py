from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
romana_bp = Blueprint("romana", __name__, url_prefix="/api/v1/romana")
@romana_bp.route("", methods=["GET"])
@require_token
def romana(): return jsonify({"ok": True})
