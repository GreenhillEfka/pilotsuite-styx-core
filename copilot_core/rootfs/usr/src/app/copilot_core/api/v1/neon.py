from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
neon_bp = Blueprint("neon", __name__, url_prefix="/api/v1/neon")
@neon_bp.route("", methods=["GET"])
@require_token
def neon(): return jsonify({"ok": True})
