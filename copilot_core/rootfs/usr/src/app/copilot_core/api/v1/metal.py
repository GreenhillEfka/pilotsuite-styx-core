from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
metal_bp = Blueprint("metal", __name__, url_prefix="/api/v1/metal")
@metal_bp.route("", methods=["GET"])
@require_token
def metal(): return jsonify({"ok": True})
