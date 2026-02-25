from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
octant_bp = Blueprint("octant", __name__, url_prefix="/api/v1/octant")
@octant_bp.route("", methods=["GET"])
@require_token
def octant(): return jsonify({"ok": True})
