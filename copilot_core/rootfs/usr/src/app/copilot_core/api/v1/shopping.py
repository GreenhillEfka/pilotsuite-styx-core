from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
shopping_bp = Blueprint("shopping", __name__, url_prefix="/api/v1/shopping")
@shopping_bp.route("", methods=["GET"])
@require_token
def shopping(): return jsonify({"ok": True})
