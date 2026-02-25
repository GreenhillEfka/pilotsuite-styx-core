from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
julia_bp = Blueprint("julia", __name__, url_prefix="/api/v1/julia")
@julia_bp.route("", methods=["GET"])
@require_token
def julia(): return jsonify({"ok": True})
