from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
singer_bp = Blueprint("singer", __name__, url_prefix="/api/v1/singer")
@singer_bp.route("", methods=["GET"])
@require_token
def singer(): return jsonify({"ok": True})
