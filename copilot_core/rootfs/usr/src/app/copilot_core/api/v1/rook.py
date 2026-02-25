from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
rook_bp = Blueprint("rook", __name__, url_prefix="/api/v1/rook")
@rook_bp.route("", methods=["GET"])
@require_token
def rook(): return jsonify({"ok": True})
